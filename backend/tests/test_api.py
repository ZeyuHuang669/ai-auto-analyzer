"""API 端到端测试：上传 → 分析 → 历史 → RAG → Planner → 删除。"""

from __future__ import annotations

import io

import pandas as pd
import pytest


@pytest.fixture
def uploaded(client, sales_df):
    buffer = io.BytesIO()
    sales_df.to_csv(buffer, index=False, encoding="utf-8-sig")
    buffer.seek(0)
    resp = client.post(
        "/api/files/upload",
        files={"files": ("sales.csv", buffer.getvalue(), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["files"][0]
    assert item["status"] == "ready"
    yield item
    client.delete(f"/api/files/{item['id']}")


def test_health(client):
    data = client.get("/api/health").json()
    assert data["status"] == "ok"
    assert data["database"] is True


def test_upload_dedup(client, uploaded, sales_df):
    buffer = io.BytesIO()
    sales_df.to_csv(buffer, index=False, encoding="utf-8-sig")
    resp = client.post(
        "/api/files/upload",
        files={"files": ("sales.csv", buffer.getvalue(), "text/csv")},
    )
    item = resp.json()["files"][0]
    assert item["duplicated"] is True
    assert item["id"] == uploaded["id"]


def test_preview(client, uploaded):
    data = client.get(f"/api/files/{uploaded['id']}/preview", params={"rows": 5}).json()
    assert data["total_rows"] == 60
    assert len(data["rows"]) == 5
    assert data["columns"][0]["name"] == "日期"


def test_run_analysis(client, uploaded):
    resp = client.post(f"/api/analysis/{uploaded['id']}/run", params={"use_ai": False})
    assert resp.status_code == 200, resp.text
    run = resp.json()
    assert run["status"] == "succeeded"
    assert run["profile"]["rows"] == 60
    assert run["charts"]
    assert run["insights"]["engine"] == "local"
    assert run["analysis"]["findings"]

    # 历史里能查到
    listing = client.get("/api/analysis/runs", params={"file_id": uploaded["id"]}).json()
    assert listing["total"] >= 1
    detail = client.get(f"/api/analysis/runs/{run['id']}").json()
    assert detail["id"] == run["id"]


def test_rag_ask(client, uploaded):
    client.post(f"/api/analysis/{uploaded['id']}/run", params={"use_ai": False})
    data = client.post(
        "/api/rag/ask", json={"question": "各个地区的销售额情况", "file_id": uploaded["id"]}
    ).json()
    assert data["answer"]
    assert data["sources"]
    assert data["engine"] == "local"


def test_planner(client, uploaded):
    data = client.post(
        "/api/planner/run",
        json={"question": "销售额随时间的变化趋势", "file_id": uploaded["id"]},
    ).json()
    assert data["intent"] == "trend"
    assert data["charts"]
    assert data["answer"]


def test_planner_rank_intent(client, uploaded):
    data = client.post(
        "/api/planner/run",
        json={"question": "各个地区销售额排名", "file_id": uploaded["id"]},
    ).json()
    assert data["intent"] == "rank"
    assert data["file_id"] == uploaded["id"]


def test_stats(client, uploaded):
    data = client.get("/api/stats").json()
    assert data["files"]["total"] >= 1
    assert data["files"]["rows"] >= 60


def test_delete_file_cascades_runs(client, sales_df):
    buffer = io.BytesIO()
    sales_df.to_csv(buffer, index=False, encoding="utf-8-sig")
    item = client.post(
        "/api/files/upload",
        files={"files": ("temp.csv", buffer.getvalue(), "text/csv")},
    ).json()["files"][0]
    run = client.post(
        f"/api/analysis/{item['id']}/run", params={"use_ai": False}
    ).json()
    assert run["status"] == "succeeded"

    assert client.delete(f"/api/files/{item['id']}").json()["ok"] is True
    assert client.get(f"/api/files/{item['id']}").status_code == 404
    # 分析记录必须一并删除，不能留下孤儿
    assert client.get(f"/api/analysis/runs/{run['id']}").status_code == 404
    listing = client.get("/api/analysis/runs", params={"file_id": item["id"]}).json()
    assert listing["total"] == 0


def test_automation_rule_lifecycle(client, tmp_path):
    watch = tmp_path / "watch"
    watch.mkdir()
    rule = client.post(
        "/api/automation/rules",
        json={"name": "测试规则", "watch_dir": str(watch), "pattern": "*.csv"},
    ).json()
    assert rule["enabled"] is True

    df = pd.DataFrame({"地区": ["华东", "华北"], "金额": [1.0, 2.0]})
    df.to_csv(watch / "new.csv", index=False, encoding="utf-8-sig")

    scan = client.post(f"/api/automation/rules/{rule['id']}/scan").json()
    assert scan["processed"] == 1

    # 第二次扫描应跳过已入库的同一内容
    again = client.post(f"/api/automation/rules/{rule['id']}/scan").json()
    assert again["processed"] == 0
    assert again["skipped"] >= 1

    assert client.delete(f"/api/automation/rules/{rule['id']}").json()["ok"] is True

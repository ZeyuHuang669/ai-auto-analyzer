"""后端 API 客户端（Streamlit 前端专用）。"""

from __future__ import annotations

import json
import os
from typing import Any

import requests

DEFAULT_BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
TIMEOUT = float(os.environ.get("API_TIMEOUT", "300"))


class ApiError(RuntimeError):
    """后端调用失败。"""


def base_url() -> str:
    try:
        import streamlit as st

        if "API_BASE_URL" in st.secrets:
            return str(st.secrets["API_BASE_URL"]).rstrip("/")
    except Exception:
        pass
    return DEFAULT_BASE.rstrip("/")


def _request(method: str, path: str, **kwargs) -> Any:
    url = f"{base_url()}{path}"
    kwargs.setdefault("timeout", TIMEOUT)
    try:
        resp = requests.request(method, url, **kwargs)
    except requests.exceptions.ConnectionError as exc:
        raise ApiError(
            f"连不上后端（{url}）。请先在 PyCharm 或终端运行：\n"
            f"uvicorn app.main:app --reload --port 8000"
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise ApiError(f"请求超时：{url}") from exc

    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise ApiError(f"[{resp.status_code}] {detail}")
    if not resp.content:
        return {}
    return resp.json()


# --------------------------------------------------------------------------- #
# 系统
# --------------------------------------------------------------------------- #
def health() -> dict:
    return _request("GET", "/api/health")


def stats() -> dict:
    return _request("GET", "/api/stats")


def config() -> dict:
    return _request("GET", "/api/config")


# --------------------------------------------------------------------------- #
# 文件
# --------------------------------------------------------------------------- #
def list_files(limit: int = 100) -> dict:
    return _request("GET", "/api/files", params={"limit": limit})


def upload_files(payloads: list[tuple[str, bytes, str]], sheet: str | None = None) -> dict:
    files = [("files", (name, data, mime)) for name, data, mime in payloads]
    data = {"sheet": sheet} if sheet else None
    return _request("POST", "/api/files/upload", files=files, data=data)


def preview_file(file_id: str, rows: int = 50) -> dict:
    return _request("GET", f"/api/files/{file_id}/preview", params={"rows": rows})


def delete_file(file_id: str) -> dict:
    return _request("DELETE", f"/api/files/{file_id}")


def get_file(file_id: str) -> dict:
    return _request("GET", f"/api/files/{file_id}")


# --------------------------------------------------------------------------- #
# 分析
# --------------------------------------------------------------------------- #
def run_analysis(file_id: str, use_ai: bool = True, force: bool = False) -> dict:
    return _request(
        "POST",
        f"/api/analysis/{file_id}/run",
        params={"use_ai": use_ai, "force": force},
    )


def list_runs(file_id: str | None = None, limit: int = 30, status: str | None = None) -> dict:
    params: dict[str, Any] = {"limit": limit}
    if file_id:
        params["file_id"] = file_id
    if status:
        params["status"] = status
    return _request("GET", "/api/analysis/runs", params=params)


def get_run(run_id: str) -> dict:
    return _request("GET", f"/api/analysis/runs/{run_id}")


def delete_run(run_id: str) -> dict:
    return _request("DELETE", f"/api/analysis/runs/{run_id}")


# --------------------------------------------------------------------------- #
# RAG / Planner / 自动化
# --------------------------------------------------------------------------- #
def ask(question: str, file_id: str | None = None, k: int = 6) -> dict:
    return _request(
        "POST", "/api/rag/ask", json={"question": question, "file_id": file_id, "k": k}
    )


def reindex(file_id: str) -> dict:
    return _request("POST", f"/api/rag/index/{file_id}")


def planner_run(question: str, file_id: str | None = None) -> dict:
    return _request(
        "POST", "/api/planner/run", json={"question": question, "file_id": file_id}
    )


def list_rules() -> dict:
    return _request("GET", "/api/automation/rules")


def create_rule(payload: dict) -> dict:
    return _request("POST", "/api/automation/rules", json=payload)


def update_rule(rule_id: str, payload: dict) -> dict:
    return _request("PATCH", f"/api/automation/rules/{rule_id}", json=payload)


def delete_rule(rule_id: str) -> dict:
    return _request("DELETE", f"/api/automation/rules/{rule_id}")


def scan_rule(rule_id: str) -> dict:
    return _request("POST", f"/api/automation/rules/{rule_id}/scan")


def scan_all() -> dict:
    return _request("POST", "/api/automation/scan")


def automation_runs(limit: int = 20) -> dict:
    return _request("GET", "/api/automation/runs", params={"limit": limit})


def to_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")

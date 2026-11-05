import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# 测试必须走独立数据库，避免污染 data/app.db
_TMP = Path(tempfile.mkdtemp(prefix="aiauto-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["OPENAI_API_KEY"] = ""
os.environ["EMBEDDING_MODEL"] = ""
os.environ["USE_AI_INSIGHTS"] = "false"
os.environ["AUTOMATION_INTERVAL_SECONDS"] = "3600"


@pytest.fixture(scope="session")
def sales_df() -> pd.DataFrame:
    days = pd.date_range("2024-01-01", periods=60, freq="D")
    regions = ["华东", "华北", "华南", "西南"]
    return pd.DataFrame(
        {
            "日期": days.strftime("%Y-%m-%d"),
            "地区": [regions[i % 4] for i in range(60)],
            "销售额": [100 + i * 5 for i in range(60)],
            "销量": [10 + i for i in range(60)],
            "评分": [4.0 + (i % 5) * 0.1 for i in range(60)],
        }
    )


@pytest.fixture
def csv_path(tmp_path: Path, sales_df: pd.DataFrame) -> Path:
    path = tmp_path / "sales.csv"
    sales_df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


@pytest.fixture
def profiled(csv_path: Path):
    from app.services.loader import load_dataframe
    from app.services.profiler import profile_dataframe
    from app.services.analysis import analyze_dataframe

    result = load_dataframe(csv_path)
    profile = profile_dataframe(result.df, source_name=csv_path.name)
    analysis = analyze_dataframe(result.df, profile)
    return result.df, profile, analysis


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c

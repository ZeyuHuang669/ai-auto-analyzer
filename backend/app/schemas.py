"""请求 / 响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    file_id: str
    use_ai: bool = True
    force: bool = False


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    file_id: str | None = None
    k: int = Field(default=6, ge=1, le=20)


class PlannerRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    file_id: str | None = None


class RuleIn(BaseModel):
    name: str = "新规则"
    watch_dir: str
    pattern: str = "*.csv"
    enabled: bool = True
    use_ai: bool = True
    interval_seconds: int = Field(default=60, ge=10, le=86400)


class RuleUpdate(BaseModel):
    name: str | None = None
    watch_dir: str | None = None
    pattern: str | None = None
    enabled: bool | None = None
    use_ai: bool | None = None
    interval_seconds: int | None = Field(default=None, ge=10, le=86400)


class ApiMessage(BaseModel):
    ok: bool = True
    message: str = ""
    data: Any = None

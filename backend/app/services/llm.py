"""LLM 客户端封装：兼容 OpenAI 的 chat.completions / responses 两种协议。

设计原则：AI 只是增强项，任何调用失败都必须优雅降级，不能拖垮整条流水线。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def extract_json(text: str) -> Any | None:
    """从模型输出里抠出 JSON（容忍 ```json 包裹和前后废话）。"""
    if not text:
        return None
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.S)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start = min(
        [i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1],
        default=-1,
    )
    if start == -1:
        return None
    for end in range(len(cleaned), start, -1):
        candidate = cleaned[start:end]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


class LLMClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.model = self.settings.llm_model
        self._client = None
        self._protocol: str | None = None
        if self.settings.llm_enabled:
            try:
                from openai import OpenAI

                self._client = OpenAI(
                    api_key=self.settings.openai_api_key,
                    base_url=self.settings.openai_base_url or None,
                    timeout=self.settings.llm_timeout,
                    max_retries=self.settings.llm_max_retries,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("初始化 OpenAI 客户端失败：%s", exc)
                self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    # ------------------------------------------------------------------ #
    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1600,
    ) -> str | None:
        if not self._client:
            return None
        if self._protocol in (None, "chat"):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                self._protocol = "chat"
                return (resp.choices[0].message.content or "").strip()
            except Exception as exc:
                logger.info("chat.completions 调用失败，尝试 responses 协议：%s", exc)

        if self._protocol in (None, "responses"):
            try:
                resp = self._client.responses.create(
                    model=self.model,
                    instructions=system,
                    input=user,
                    max_output_tokens=max_tokens,
                )
                self._protocol = "responses"
                return (getattr(resp, "output_text", "") or "").strip()
            except Exception as exc:
                logger.warning("LLM 调用失败：%s", exc)
        return None

    def chat_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 1600,
    ) -> dict | None:
        text = self.chat(system, user, temperature=temperature, max_tokens=max_tokens)
        if not text:
            return None
        data = extract_json(text)
        return data if isinstance(data, dict) else None

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        if not self._client or not self.settings.embedding_model:
            return None
        try:
            resp = self._client.embeddings.create(
                model=self.settings.embedding_model, input=texts
            )
            return [item.embedding for item in resp.data]
        except Exception as exc:
            logger.warning("embedding 调用失败，回退本地向量：%s", exc)
            return None


_shared: LLMClient | None = None


def get_llm() -> LLMClient:
    global _shared
    if _shared is None:
        _shared = LLMClient()
    return _shared

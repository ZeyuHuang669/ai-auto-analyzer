"""文本向量化：优先用 API embedding，没有配置时用本地哈希向量（零依赖、离线可用）。"""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache

import numpy as np

from app.core.config import get_settings
from app.services.llm import get_llm

_WORD_RE = re.compile(r"[a-zA-Z0-9_]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")


def _tokens(text: str) -> list[tuple[str, float]]:
    """词 token + 中日韩字符 bigram，兼顾中英文检索。"""
    text = (text or "").lower()
    out: list[tuple[str, float]] = []
    for word in _WORD_RE.findall(text):
        out.append((f"w:{word}", 1.0))
    for block in _CJK_RE.findall(text):
        for i in range(len(block) - 1):
            out.append((f"b:{block[i:i + 2]}", 0.6))
        if len(block) == 1:
            out.append((f"c:{block}", 0.4))
    return out


def _hash_index(token: str, dim: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % dim


class HashingEmbedder:
    """特征哈希向量：确定性、无需模型文件。"""

    name = "hashing"

    def __init__(self, dim: int = 512):
        self.dim = dim

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = np.zeros(self.dim, dtype=np.float32)
            for token, weight in _tokens(text):
                vec[_hash_index(token, self.dim)] += weight
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec /= norm
            vectors.append(vec.tolist())
        return vectors


class OpenAIEmbedder:
    name = "openai"

    def __init__(self, model: str):
        self.model = model
        self.llm = get_llm()

    def encode(self, texts: list[str]) -> list[list[float]] | None:
        if not self.llm.available or not self.model:
            return None
        out: list[list[float]] = []
        for i in range(0, len(texts), 64):
            batch = self.llm.embed(texts[i : i + 64])
            if batch is None:
                return None
            out.extend(batch)
        return out


class EmbeddingService:
    def __init__(self) -> None:
        settings = get_settings()
        self.dim = settings.embedding_dim
        self._local = HashingEmbedder(self.dim)
        self._remote = (
            OpenAIEmbedder(settings.embedding_model)
            if settings.embedding_model
            else None
        )
        self.active = "hashing"
        self._remote_broken = False

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._remote and not self._remote_broken:
            result = self._remote.encode(texts)
            if result:
                self.active = self._remote.name
                return result
            self._remote_broken = True
        self.active = self._local.name
        return self._local.encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


@lru_cache
def get_embedder() -> EmbeddingService:
    return EmbeddingService()


def lexical_overlap(query: str, text: str) -> float:
    """关键词重叠度（0~1），用于给向量检索做混合重排。"""
    q = {t for t, _ in _tokens(query)}
    if not q:
        return 0.0
    d = {t for t, _ in _tokens(text)}
    if not d:
        return 0.0
    return len(q & d) / len(q)


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0 or math.isnan(denom):
        return 0.0
    return float(np.dot(va, vb) / denom)

"""RAG：把数据集/字段/发现/图表索引成片段，检索后交给模型回答。

PostgreSQL + pgvector 可用时走向量索引；否则用本地 JSON 向量 + numpy 余弦。
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import db as db_module
from app.models import FileAsset, RagChat, RagChunk
from app.services.embeddings import cosine, get_embedder, lexical_overlap
from app.services.llm import get_llm
from app.utils.json import to_python

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 900


def _sample_rows(df: pd.DataFrame, n: int = 5) -> str:
    sample = df.head(n)
    return sample.to_string(index=False, max_cols=12)[:600]


def build_documents(
    file: FileAsset,
    df: pd.DataFrame,
    profile: dict,
    analysis: dict,
    charts: list[dict],
) -> list[dict]:
    """把一次分析拆成可检索的文档片段。"""
    docs: list[dict] = []
    meta_base = {"file_id": file.id, "file_name": file.name}

    overview = [
        f"文件名：{file.name}",
        f"数据规模：{profile['rows']} 行 × {profile['cols']} 列，类型 {profile['kind']}",
        f"质量评分：{profile['quality']['score']}（{profile['quality']['grade']}），"
        f"缺失率 {profile['missing_ratio']:.2%}，重复行 {profile['duplicate_rows']}",
        "字段清单：",
    ]
    for col in profile["columns"]:
        overview.append(f"- {col['name']}（{col['role_label']}），唯一值 {col['unique']}")
    overview.append("数据样例：")
    overview.append(_sample_rows(df))
    docs.append(
        {
            "kind": "dataset",
            "title": f"{file.name} 概览",
            "content": "\n".join(overview)[:MAX_CHUNK_CHARS * 3],
            "meta": meta_base,
        }
    )

    # 单独一份质量/缺失文档，回答"哪些字段缺失/数据质量如何"时命中更准
    missing_cols = sorted(
        [c for c in profile["columns"] if c["missing_ratio"] > 0],
        key=lambda c: c["missing_ratio"],
        reverse=True,
    )
    quality_lines = [
        "数据质量与缺失情况",
        f"质量评分 {profile['quality']['score']}（{profile['quality']['grade']}），"
        f"整体缺失率 {profile['missing_ratio']:.2%}，缺失单元格 {profile['missing_cells']} 个，"
        f"重复行 {profile['duplicate_rows']} 条",
    ]
    if missing_cols:
        quality_lines.append("有缺失的字段（按缺失率排序）：")
        for c in missing_cols[:12]:
            quality_lines.append(
                f"- {c['name']}：缺失 {c['missing']} 行（{c['missing_ratio']:.1%}）"
            )
    else:
        quality_lines.append("所有字段都没有缺失值")
    for issue in profile["quality"].get("issues", []):
        quality_lines.append(f"- {issue['title']}：{issue['detail']}")
    docs.append(
        {
            "kind": "quality",
            "title": "数据质量与缺失情况",
            "content": "\n".join(quality_lines),
            "meta": {**meta_base, "columns": [c["name"] for c in missing_cols[:12]]},
        }
    )

    for col in profile["columns"][:40]:
        col_meta = {**meta_base, "column": col["name"], "columns": [col["name"]]}
        lines = [
            f"字段：{col['name']}",
            f"类型：{col['role_label']}（{col['dtype']}）",
            f"缺失：{col['missing']} 行（{col['missing_ratio']:.1%}），唯一值 {col['unique']} 个",
        ]
        st = col.get("stats")
        if st:
            lines.append(
                f"统计：均值 {st['mean']}，中位数 {st['median']}，最小 {st['min']}，"
                f"最大 {st['max']}，标准差 {st['std']}，偏度 {st['skew']}，"
                f"异常值 {st['outliers']} 个"
            )
        if col.get("top_values"):
            lines.append(
                "高频取值："
                + "、".join(f"{t['value']}({t['count']}次)" for t in col["top_values"][:5])
            )
        if col.get("time"):
            lines.append(
                f"时间范围：{col['time']['min']} ~ {col['time']['max']}"
                f"（跨度 {col['time']['span_days']} 天，粒度 {col['time']['granularity']}）"
            )
        docs.append(
            {
                "kind": "column",
                "title": f"字段 {col['name']}",
                "content": "\n".join(lines),
                "meta": col_meta,
            }
        )

    for f in analysis.get("findings", [])[:10]:
        docs.append(
            {
                "kind": "finding",
                "title": f["title"],
                "content": (
                    f"{f['title']}\n结论：{f['detail']}\n"
                    f"涉及字段：{'、'.join(f['columns']) or '整体'}"
                ),
                "meta": {
                    **meta_base,
                    "finding_kind": f["kind"],
                    "columns": list(f.get("columns") or []),
                },
            }
        )

    for c in charts[:8]:
        docs.append(
            {
                "kind": "chart",
                "title": c["title"],
                "content": f"图表：{c['title']}\n推荐理由：{c['reason']}\n结论：{c['insight']}",
                "meta": {
                    **meta_base,
                    "chart_kind": c["kind"],
                    "columns": list(c.get("columns") or []),
                },
            }
        )

    return docs


def index_dataset(
    db: Session,
    file: FileAsset,
    df: pd.DataFrame,
    profile: dict,
    analysis: dict,
    charts: list[dict],
) -> int:
    """重建某个文件的全部索引片段。"""
    db.query(RagChunk).filter(RagChunk.file_id == file.id).delete()
    db.flush()

    docs = build_documents(file, df, profile, analysis, charts)
    embedder = get_embedder()
    vectors = embedder.embed([d["content"] for d in docs])

    rows: list[RagChunk] = []
    for doc, vec in zip(docs, vectors):
        rows.append(
            RagChunk(
                file_id=file.id,
                kind=doc["kind"],
                title=doc["title"],
                content=doc["content"],
                meta=doc["meta"],
                embedding=json.dumps([round(v, 6) for v in vec]),
                dim=len(vec),
            )
        )
    db.add_all(rows)
    db.commit()

    if db_module.PGVECTOR_READY:
        try:
            for row in rows:
                db.execute(
                    text(
                        "UPDATE rag_chunks SET embedding_vec = CAST(:v AS vector) "
                        "WHERE id = :id"
                    ),
                    {"v": row.embedding, "id": row.id},
                )
            db.commit()
        except Exception as exc:  # pragma: no cover
            db.rollback()
            logger.warning("写入 pgvector 列失败，检索将回退 numpy：%s", exc)
    return len(rows)


def index_chunk_count(db: Session, file_id: str) -> int:
    return db.query(RagChunk).filter(RagChunk.file_id == file_id).count()


def _pg_search(
    db: Session, qvec: list[float], k: int, file_id: str | None
) -> list[dict]:
    vec = json.dumps([round(v, 6) for v in qvec])
    sql = (
        "SELECT id, file_id, kind, title, content, meta, "
        "1 - (embedding_vec <=> CAST(:v AS vector)) AS score "
        "FROM rag_chunks WHERE embedding_vec IS NOT NULL "
    )
    params: dict[str, Any] = {"v": vec, "k": k}
    if file_id:
        sql += "AND file_id = :fid "
        params["fid"] = file_id
    sql += "ORDER BY embedding_vec <=> CAST(:v AS vector) LIMIT :k"
    rows = db.execute(text(sql), params).mappings().all()
    return [
        {
            "id": r["id"],
            "file_id": r["file_id"],
            "kind": r["kind"],
            "title": r["title"],
            "content": r["content"],
            "meta": r["meta"],
            "score": round(float(r["score"]), 4),
        }
        for r in rows
    ]


def _numpy_search(
    db: Session, qvec: list[float], k: int, file_id: str | None
) -> list[dict]:
    query = db.query(RagChunk)
    if file_id:
        query = query.filter(RagChunk.file_id == file_id)
    chunks = query.all()
    scored: list[tuple[float, RagChunk]] = []
    for chunk in chunks:
        try:
            vec = json.loads(chunk.embedding)
        except (json.JSONDecodeError, TypeError):
            continue
        if len(vec) != len(qvec):
            continue
        scored.append((cosine(qvec, vec), chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "id": c.id,
            "file_id": c.file_id,
            "kind": c.kind,
            "title": c.title,
            "content": c.content,
            "meta": c.meta,
            "score": round(score, 4),
        }
        for score, c in scored[:k]
    ]


def search(
    db: Session, question: str, k: int = 6, file_id: str | None = None
) -> list[dict]:
    """向量召回 + 关键词重排，纯离线时也能答得比较准。"""
    embedder = get_embedder()
    qvec = embedder.embed_query(question)
    pool = max(k * 3, 12)

    results: list[dict] = []
    if db_module.PGVECTOR_READY:
        try:
            results = _pg_search(db, qvec, pool, file_id)
        except Exception as exc:  # pragma: no cover
            logger.warning("pgvector 检索失败，回退 numpy：%s", exc)
    if not results:
        results = _numpy_search(db, qvec, pool, file_id)

    # 混合打分：向量 0.6 + 关键词 0.4，再对"问题里点名的字段"加分
    for hit in results:
        meta = hit.get("meta") or {}
        columns = meta.get("columns") or []
        matched = sum(1 for col in columns if col and str(col) in question)
        hit["score"] = round(
            0.6 * float(hit["score"])
            + 0.4 * lexical_overlap(question, hit["content"])
            + 0.06 * matched,
            4,
        )
    results.sort(key=lambda h: h["score"], reverse=True)
    return results[:k]


SYSTEM_PROMPT = """你是上传数据集的问答助手。只能依据下面提供的资料回答问题，并用 [编号] 标注引用来源。
资料不足以回答时，直接说「现有资料中没有这个信息」，不要编造。
回答用中文，先给结论，再给依据；涉及数字时保留原始量级。"""


def _snippet(content: str) -> str:
    """从片段里挑出最像结论的一句。"""
    for line in content.splitlines():
        if line.startswith("结论："):
            return line[len("结论："):].strip()
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    return lines[-1] if lines else content[:160]


def _local_answer(question: str, hits: list[dict]) -> str:
    if not hits:
        return "没有检索到相关内容。可能还没有为这份文件建立索引，或问题与数据无关。"
    lines = ["未配置大模型，先给出检索到的要点（配置 Key 后可获得完整分析）："]
    for i, hit in enumerate(hits[:4], 1):
        lines.append(f"{i}. **{hit['title']}**：{_snippet(hit['content'])[:180]}")
    return "\n\n".join(lines)


def answer(
    db: Session,
    question: str,
    file_id: str | None = None,
    k: int = 6,
) -> dict:
    import time

    t0 = time.perf_counter()
    hits = search(db, question, k=k, file_id=file_id)

    context_parts = []
    for i, hit in enumerate(hits, 1):
        context_parts.append(f"[{i}]（{hit['title']}）\n{hit['content'][:800]}")
    context = "\n\n".join(context_parts)[:8000]

    llm = get_llm()
    engine = "local"
    text_answer = ""
    if llm.available and hits:
        prompt = f"资料：\n{context}\n\n问题：{question}\n\n请依据资料回答。"
        text_answer = llm.chat(SYSTEM_PROMPT, prompt, max_tokens=900) or ""
        if text_answer:
            engine = "llm"
    if not text_answer:
        text_answer = _local_answer(question, hits)
        engine = "local"

    latency = int((time.perf_counter() - t0) * 1000)
    chat = RagChat(
        file_id=file_id,
        question=question,
        answer=text_answer,
        sources=[
            {
                "id": h["id"],
                "title": h["title"],
                "kind": h["kind"],
                "score": h["score"],
                "file_id": h["file_id"],
            }
            for h in hits
        ],
        engine=engine,
        latency_ms=latency,
    )
    db.add(chat)
    db.commit()

    return to_python(
        {
            "question": question,
            "answer": text_answer,
            "sources": chat.sources,
            "hits": hits,
            "engine": engine,
            "latency_ms": latency,
        }
    )

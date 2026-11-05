"""FastAPI 入口。"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import analysis, automation, files, planner, rag, system
from app.core.config import get_settings
from app.core.db import init_db
from app.services.automation import automation_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("app")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(
        automation_loop(settings.automation_interval_seconds)
    )
    app.state.automation_task = task
    logger.info("后端已启动，数据库：%s", settings.database_url.split("@")[-1])
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        logger.info("后端已停止")


app = FastAPI(
    title="AI 自动化文件处理系统",
    description="上传 CSV/Excel → 自动识别 → 自动分析 → 自动推荐图表 → 自动出图 → AI 结论 → 保存历史",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (files, analysis, rag, planner, automation, system):
    app.include_router(module.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("未处理异常：%s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器内部错误：{type(exc).__name__}: {exc}"},
    )


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "version": app.version,
        "docs": "/docs",
        "health": "/api/health",
    }

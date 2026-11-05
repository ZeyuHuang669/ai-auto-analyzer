-- 在 PostgreSQL 上初始化数据库（用 psql 执行）
--   psql -U postgres -f scripts/init_pg.sql
-- 然后把 .env 里的 DATABASE_URL 指向这个库

CREATE DATABASE ai_auto;

\c ai_auto

CREATE EXTENSION IF NOT EXISTS vector;

-- 表结构由后端自动创建（SQLAlchemy create_all），
-- 启动后会自动补 embedding_vec 列与 HNSW 索引。

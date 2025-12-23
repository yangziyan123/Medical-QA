# 入门学习项目（本科生作业）——医疗问答系统（Medical QA）项目设计文档（开发版）

> 目标：面向“医疗咨询/科普”场景，提供**可登录**、**可追溯会话**、**可流式输出**、并支持**知识库检索增强（RAG）**的问答系统。  
> 当前状态：已接入真实 LLM/Embedding（火山引擎 Volcengine Ark，按 OpenAI Compatible API 调用），同时保留 stub 方案便于离线/开发回退。

## 1. 项目完成了什么（当前已实现）

### 1.1 后端（FastAPI）

- **健康检查**
  - `GET /api/health`：返回 `{ ok, env, name }`
- **认证与用户**
  - `POST /api/auth/register`：注册
  - `POST /api/auth/login`：登录并签发 JWT（payload 携带 `username`、`role`）
  - `GET /api/auth/me`：返回当前用户
  - 密码哈希：开发期使用 `pbkdf2_sha256`（降低 Windows bcrypt 兼容风险），兼容校验旧 bcrypt 格式
- **会话与消息（对话历史）**
  - `POST /api/sessions`：创建会话（可选标题）
  - `GET /api/sessions`：列表（cursor 分页，按 `updated_at,id` 倒序）
  - `GET /api/sessions/{id}`：会话详情（含 messages）
  - `PATCH /api/sessions/{id}`：改名（同时更新 `updated_at`）
  - `DELETE /api/sessions/{id}`：按依赖顺序删除（`qa_runs -> messages -> session`）
- **问答（MVP）**
  - `POST /api/chat/ask`：一次性返回回答；会落库：
    - `messages`：写入 user/assistant 两条消息
    - `qa_runs`：记录 prompt（如有检索上下文）、citations、latency、safety_flags
  - LLM：支持 stub + 真实模型（通过 `LLM_PROVIDER/LLM_BASE_URL/LLM_API_KEY/LLM_MODEL` 配置）
    - 已适配火山引擎 Ark（OpenAI Compatible 形式调用 `POST /chat/completions`）
    - `qa_runs.llm_provider / llm_model` 记录本次使用的 provider 与模型（或 endpoint）
- **流式问答（SSE）**
  - `GET|POST /api/chat/stream`：SSE 返回 `meta/token/done/error` 事件
  - 支持认证方式：
    - `Authorization: Bearer <token>`（推荐）
    - 或 query `?token=<token>`（为 EventSource 受限场景预留）
- **知识库导入与检索（管理员）**
  - `POST /api/knowledge/import`（admin）：导入 `raw_text`，切分为 chunks，落库（Postgres），并写入 Qdrant
  - `GET /api/knowledge/search`（admin）：对 query 做向量检索，返回 chunks 文本与文档元信息
  - Embedding：支持 stub + 真实向量化（通过 `EMBEDDING_PROVIDER/EMBEDDING_BASE_URL/EMBEDDING_API_KEY/EMBEDDING_MODEL/EMBEDDING_DIM` 配置）
    - 已适配火山引擎 Ark（OpenAI Compatible 形式调用 `POST /embeddings`）
    - 导入时支持 embedding 批处理：`EMBEDDING_BATCH_SIZE`
- **配置与跨域**
  - `.env` / `.env.example`：集中配置 DB、JWT、Qdrant、CORS 等
  - CORS：默认允许 `http://localhost:5173`（Vite）等
- **数据库迁移**
  - Alembic migrations：已包含 `users/sessions/messages/qa_runs/documents/chunks`

### 1.2 前端（Vue3 + Vite + Pinia）

- **登录/注册页**：注册后自动登录并跳转
- **聊天页**
  - 会话列表：新建、改名、删除、切换
  - SSE 流式问答：边生成边显示（前端用 `fetch + ReadableStream`，以便携带 `Authorization`）
  - 引用展示：当后端返回 `citations` 时显示引用来源卡片
  - 免责声明展示：展示 `safety.disclaimer`
- **知识库管理页（admin）**
  - 导入 `raw_text`
  - 检索调试：展示 top_k 结果、score、来源链接
- **路由权限**
  - `/chat` 需要登录
  - `/admin/knowledge` 需要 `role=admin`

### 1.3 本地依赖服务（docker-compose.dev.yml）

- **PostgreSQL 16**：业务数据（用户、会话、消息、问答运行、知识库文档与切分片段）
- **Qdrant**：向量检索（chunks 向量 + payload）
- **Redis 7**：已在 compose 中提供，但当前代码未接入（预留后续缓存/限流/任务队列等用途）
- **火山引擎 Volcengine Ark（外部服务）**：真实 LLM 与 Embedding API（当前按 OpenAI Compatible 方式调用）

## 2. 项目还未完成什么（缺口/路线图）

### 2.1 大模型与推理能力（核心缺口）

- 真实 LLM 已接入（Volcengine Ark / OpenAI Compatible），待完善项：
  - 记录 tokens（`qa_runs.tokens_in/out`）、更完整的模型/endpoint 元信息与请求 ID
  - 失败重试、熔断、限流、降级（例如自动 fallback 到 stub 或返回更友好错误）
  - Prompt 管理（system prompt 外置配置/版本化；多 prompt 模板与 A/B 测试）
- 输出质量与安全
  - 更严格的医疗安全策略：风险分级（`triage`）、高危症状识别、拒答/引导就医策略
  - 引用与答案对齐（目前 citations 与答案无强绑定，仅“检索到就返回”）

### 2.2 向量化与知识库工程化

- 真实 Embedding 已接入（Volcengine Ark / OpenAI Compatible），待完善项：
  - 统一 embedding 维度与 collection 版本化策略（当前已有维度校验；维度变更需重建/换 collection）
  - 批量导入多个文档的接口与离线导入脚本（当前为“单文档 raw_text + 内部切 chunk”）
- 导入能力增强
  - 支持文件/网页抓取、结构化指南、PDF/Docx 清洗
  - 更丰富的 chunk 元数据：章节、页码、token_count、来源段落等
- 检索策略升级
  - 召回 + rerank、过滤（source_type/时间版本）、多路召回、MMR 等

### 2.3 平台能力与工程化

- Redis 接入：缓存（热知识/会话）、限流、SSE 会话状态、队列/后台任务（Celery/RQ 等）
- 观测与运维：结构化日志、链路追踪、指标（latency、错误率、Qdrant/DB 异常）
- 测试与 CI：当前 `backend/tests` 为空；建议补齐 API / RAG 链路测试
- 权限与后台：角色管理、管理端审计日志、数据删除与合规策略
- 生产化部署：Dockerfile、环境分层（dev/staging/prod）、反向代理（Nginx）与 HTTPS

## 3. 总体架构

```
┌──────────────┐      HTTP/JWT       ┌────────────────────────────┐
│  Vue3 前端   │  ───────────────▶   │  FastAPI 后端（Uvicorn）   │
│  /login/chat │                      │  auth/sessions/chat/RAG    │
└──────────────┘                      └───────────────┬────────────┘
                                                       │
                                           ┌───────────┴───────────┐
                                           │                       │
                                   ┌──────────────┐        ┌──────────────┐
                                   │ PostgreSQL   │        │   Qdrant      │
                                   │ 业务与知识库 │        │ 向量检索召回   │
                                   └──────────────┘        └──────────────┘
                                           │
                                   ┌──────────────┐
                                   │   Redis      │
                                   │（预留未接入）│
                                   └──────────────┘
```

## 4. 后端设计

### 4.1 目录结构（backend/app）

- `main.py`：创建 FastAPI app、挂载路由、CORS、`/api/health`
- `core/`
  - `config.py`：`pydantic-settings` 读取 `.env`
  - `security.py`：密码哈希、JWT 编解码
  - `logging.py`：基础 logging 配置
- `db/`
  - `session.py`：AsyncEngine + AsyncSession 依赖注入
  - `migrations/`：Alembic（async 环境）
- `models/`：SQLAlchemy ORM（users/sessions/messages/qa_runs/documents/chunks）
- `schemas/`：Pydantic 请求/响应模型
- `api/routers/`
  - `auth.py`：注册/登录/me
  - `sessions.py`：会话 CRUD
  - `chat.py`：ask + stream（SSE）
  - `knowledge.py`：导入与检索（admin）
- `rag/`
  - `chunking.py`：raw_text 切分（max_chars + overlap）
  - `embeddings.py`：embedding 客户端（stub + OpenAI Compatible）
  - `qdrant_store.py`：Qdrant client 与 collection 管理
  - `retriever.py`：检索召回 + 拼接上下文
- `services/llm_client.py`：LLM 抽象、Stub、OpenAI Compatible 客户端与 provider 工厂

### 4.2 配置项（backend/.env.example）

- `DATABASE_URL`：`postgresql+asyncpg://...`
- `JWT_SECRET` / `JWT_ALGORITHM` / `JWT_EXPIRES_MIN`
- `QDRANT_URL` / `QDRANT_COLLECTION` / `EMBEDDING_DIM` / `RAG_TOP_K`
- LLM：
  - `LLM_PROVIDER` / `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`
  - `LLM_TIMEOUT_SEC` / `LLM_MAX_TOKENS` / `LLM_TEMPERATURE`
- Embedding：
  - `EMBEDDING_PROVIDER` / `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` / `EMBEDDING_MODEL`
  - `EMBEDDING_TIMEOUT_SEC` / `EMBEDDING_BATCH_SIZE` / `EMBEDDING_NORMALIZE`
- `CORS_ALLOW_ORIGINS`：前端开发地址白名单

### 4.3 关键链路：问答（/api/chat/ask）

1) 解析请求：`question` + 可选 `session_id`
2) 会话处理：
   - 若无 `session_id`：新建会话，标题取 `question` 前 50 字
3) 检索召回（RAG）：
   - 计算 query embedding（按 `EMBEDDING_PROVIDER` 使用真实/占位向量化）
   - Qdrant 搜索 top_k
   - 用 chunk_id 回表 Postgres 取 chunk 文本与 document 元信息
   - 拼接 `context`（形如 `[CIT-1] ...`）
4) 记录消息：
   - 写入 user message
5) 生成回答：
   - 调用 `get_llm_client().generate()`（按 `LLM_PROVIDER` 使用真实/占位 LLM）
6) 落库与回包：
   - 写入 assistant message
   - 写入 `qa_runs`（prompt/citations/latency/safety_flags）
   - 返回 `answer + citations + safety`

### 4.4 关键链路：流式问答（/api/chat/stream）

- 返回类型：`text/event-stream`
- 事件序列（典型）：
  - `event: meta`：`{ stage: "starting" }`
  - `event: meta`：`{ stage: "retrieving" }`
  - `event: meta`：`{ stage: "generating", session_id, qa_run_id }`
  - `event: token`：`{ delta: "..." }`（多次）
  - `event: done`：最终 `ChatAskResponse` JSON
- 断连处理：每次推送 token 前检查 `request.is_disconnected()`

### 4.5 知识库导入与检索

**导入（/api/knowledge/import）**

- 对 `raw_text` 做 sha256，作为文档去重 checksum
- `chunk_text()` 切分：
  - 先按空行分段，尽量合并到 `max_chars`
  - 超长段按滑窗切片（`overlap_chars` 重叠）
- 写入 Postgres：`documents` + `chunks`
- 写入 Qdrant：
  - point id 使用 `chunk.id`
  - payload 写入 `chunk_id/document_id/title/version/source_url/chunk_index`
  - embedding 支持批处理（`EMBEDDING_BATCH_SIZE`），并可选向量归一化（`EMBEDDING_NORMALIZE`）

**检索（/api/knowledge/search）**

- query → embedding → Qdrant top_k
- 回表取 chunk 文本与文档元信息
- 以 score 排序返回

## 5. 数据库设计（PostgreSQL）

### 5.1 表与关系

- `users (1) ── (N) sessions`
- `sessions (1) ── (N) messages`
- `sessions (1) ── (N) qa_runs`
- `documents (1) ── (N) chunks`
- `qa_runs.user_message_id -> messages.id`
- `qa_runs.assistant_message_id -> messages.id (nullable)`

### 5.2 核心字段（摘要）

- `users`
  - `id (uuid pk)`，`username (unique)`，`hashed_password`，`role`
- `sessions`
  - `id`，`user_id (fk)`，`title`，`created_at`，`updated_at`
- `messages`
  - `id`，`session_id (fk)`，`role`，`content`，`created_at`，`client_msg_id`
- `qa_runs`
  - `id`，`session_id`，`user_message_id`，`assistant_message_id`
  - `llm_provider/model`，`prompt_version`，`prompt`
  - `answer`，`citations (jsonb)`，`safety_flags (jsonb)`
  - `tokens_in/out`，`latency_ms`，`created_at`
- `documents`
  - `id`，`title`，`version`，`source_type`，`source_url`，`checksum (unique)`，`created_at`
- `chunks`
  - `id`，`document_id`，`chunk_index`，`text`，`token_count/section/metadata`（预留），“created_at”

## 6. API 设计（概要）

> 详见后端 OpenAPI：`http://localhost:8000/docs`

- `GET /api/health`
- `POST /api/auth/register` / `POST /api/auth/login` / `GET /api/auth/me`
- `POST /api/sessions` / `GET /api/sessions` / `GET|PATCH|DELETE /api/sessions/{id}`
- `POST /api/chat/ask`
- `GET|POST /api/chat/stream`（SSE）
- `POST /api/knowledge/import`（admin）/ `GET /api/knowledge/search`（admin）

## 7. 前端设计（概要）

- 路由：
  - `/login`：登录/注册
  - `/chat`：聊天主界面（requiresAuth）
  - `/admin/knowledge`：知识库管理（requiresAuth + requiresAdmin）
- 状态管理：
  - `auth` store：token（localStorage）、user、自动 `fetchMe`
  - `chat` store：会话列表、当前会话、消息缓存、SSE 流式状态与错误

## 8. 已知限制与注意事项

- **向量维度迁移成本**：`EMBEDDING_DIM` 与 Qdrant collection 向量维度必须一致；维度变更需要重建/切换 collection 并重新写入向量（开发期通常用 `reset-dev.ps1` 直接重置）。
- **Redis 未接入**：compose 中有 redis，但业务暂未使用
- **测试缺失**：当前无自动化测试用例
- **生产化缺失**：未提供生产 Dockerfile/反代/HTTPS/多环境配置规范
- **Prompt 配置仍偏硬编码**：真实 LLM 的 system prompt 当前在代码内置；更建议外置到配置并做版本化管理。
- **合规与安全**：医疗场景需额外的风控与合规流程（当前主要依赖免责声明字段与 prompt 约束）

# Frontend（Vue3 + Vite + Pinia）

本目录为医疗问答系统前端工程（开发版）。已对接后端接口：

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/sessions`
- `GET /api/sessions`
- `GET /api/sessions/{id}`
- `POST /api/chat/ask`
- `POST /api/chat/stream`（SSE 流式）
- `POST /api/knowledge/import`（admin）
- `GET /api/knowledge/search`（admin）

## 本地运行

1) 配置后端地址（可选）

- 复制 `frontend/.env.example` 为 `frontend/.env`
- 修改 `VITE_API_BASE_URL`（默认 `http://localhost:8000`）

2) 安装依赖并启动

PowerShell（在 `frontend/`）：

```powershell
npm.cmd install
npm.cmd run dev
```

3) 验收

- 打开 `http://localhost:5173`
- 登录/注册后进入 `/chat`
- 左侧会话列表可见；右侧可发送问题（Step 6 占位回答）
- 发送问题后应看到“边生成边显示”（Step 8 SSE）
- 若登录账号为 `admin`，右上角会出现“知识库”入口，可导入 raw_text 并调试检索
- 会话列表支持“改名/删除”；长对话时消息区自动保持滚动到底部（你手动上滑查看历史则不会强制回到底部）

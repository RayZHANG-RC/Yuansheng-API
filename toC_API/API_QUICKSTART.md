# 合作方试调 API 快速指南

> **对外交付**：请使用 [`CUSTOMER_API_QUICKSTART.md`](CUSTOMER_API_QUICKSTART.md)（不含运维与内部配置）。  
> 本文档面向 **我方运维 / 开发**，含部署与环境变量说明。

面向外部合作方的最小 HTTP 封装，底层仍走现有 `main.py` 五步管线，不改业务逻辑。

## 1. 环境准备（运维侧，一次性）

```powershell
cd C:\path\to\real_toc
pip install -r requirements-api.txt
```

确认 `config.json` 中已配置有效的 `openai.api_key` 与 `organization_id`（管线 step1 会校验）。

设置合作方 API Key（任选其一）：

```powershell
# 推荐：环境变量，勿提交到 Git
$env:REAL_TOC_PARTNER_API_KEY = "your-secret-key-for-partner"
```

或在 `config.json` 的 `partner_api.api_keys` 中配置（试调可用默认值，上线前务必更换）。支持两种写法：

- 字符串：`"your-secret-key-for-partner"`
- 对象（可单独设配额）：`{ "key": "...", "name": "partner_a", "success_quota": { ... } }`

通过环境变量 `REAL_TOC_PARTNER_API_KEY` 注入的 Key 共用下方默认配额。

## 2. 启动服务

```powershell
python api_server.py
```

默认地址：`http://0.0.0.0:8765`

- 交互文档：http://localhost:8765/docs
- 健康检查：http://localhost:8765/health

可选环境变量：

| 变量 | 说明 |
|------|------|
| `REAL_TOC_PARTNER_API_KEY` | 合作方鉴权 Key（逗号分隔多个） |
| `REAL_TOC_DATA_ROOT` | 会话目录根路径，默认 `data/partner_trials` |
| `REAL_TOC_API_HOST` / `REAL_TOC_API_PORT` | 监听地址与端口 |

## 3. 鉴权

每个请求需携带以下之一：

```http
Authorization: Bearer your-secret-key-for-partner
```

或

```http
X-API-Key: your-secret-key-for-partner
```

## 4. 接口说明

### 4.1 提交分析（异步）

```http
POST /v1/analyze
Content-Type: application/json
Authorization: Bearer your-secret-key-for-partner
```

请求体结构：

```json
{
  "user_id": "partner_demo",
  "session_input": { ... }
}
```

- `user_id`：合作方用户唯一标识（必填，用于目录划分与落盘）
- `session_input`：与 `input.json` 字段一致（见 `examples/partner_request_CAR01_Q001.json`）

**无需提交** `user_settings` 或 `model_set`。服务端按 `config.json` → `partner_api` 自动生成 `setting.json`，并使用固定模型集（默认 `gpt-4.1`）。运维可在本地修改：

- `partner_api.default_user_sensitivity_setting`（语气 / MBTI / 敏感度）
- `partner_api.model_set`（`gpt-4.1` 或 `gpt-5`，不对外暴露）
- `partner_api.default_api_key_success_quota`：按 **API Key** 限制**成功完成**次数（失败不计入；每个 Key 独立计数）

```json
"default_api_key_success_quota": {
  "enabled": true,
  "max_successful_requests": 10,
  "period": "lifetime"
}
```

某个 Key 需要不同于默认的限额时，在 `api_keys` 中使用对象并设置 `success_quota`：

```json
"api_keys": [
  {
    "key": "key-for-partner-a",
    "name": "partner_a",
    "success_quota": {
      "enabled": true,
      "max_successful_requests": 50,
      "period": "daily"
    }
  },
  "another-plain-string-key"
]
```

`period` 可选：`lifetime`（累计）、`daily`（按自然日重置）、`monthly`（按自然月重置）。超额时 `POST /v1/analyze` 返回 **429**（`api_key_success_quota_exceeded`）。

**响应 202：**

```json
{
  "session_id": "20260605_demo_38_CAR01_Q001",
  "status": "queued",
  "poll_url": "/v1/jobs/20260605_demo_38_CAR01_Q001",
  "quota": {
    "enabled": true,
    "max_successful_requests": 10,
    "used": 3,
    "remaining": 7,
    "period": "lifetime",
    "period_key": "lifetime"
  },
  "message": "任务已入队，请轮询 poll_url 获取结果（通常需 1～5 分钟）"
}
```

服务端会在 `data/partner_trials/<user_id>/<question_id>/<session_id>/` 写入 `input.json`、`setting.json`，并后台执行 `main.py`。

### 4.2 查询任务

```http
GET /v1/jobs/{session_id}
Authorization: Bearer your-secret-key-for-partner
```

`status` 取值：

| status | 含义 |
|--------|------|
| `queued` | 已入队 |
| `running` | 管线执行中 |
| `completed` | 成功，`result` 为最终 `output.json` 内容 |
| `failed` | 失败，查看 `error` 及目录下 `api_pipeline.log` |

**完成示例：**

```json
{
  "session_id": "...",
  "status": "completed",
  "result": {
    "session_metadata": { "session_status": "completed", ... },
    "frontend_response": {
      "summary": "...",
      "risk_points": ["...", "..."]
    }
  }
}
```

### 4.3 查询 API Key 配额（可选）

```http
GET /v1/quota
Authorization: Bearer your-secret-key-for-partner
```

按请求头中携带的 API Key 返回该 Key 的配额使用情况（不暴露 Key 本身）。

响应示例：

```json
{
  "enabled": true,
  "max_successful_requests": 10,
  "used": 3,
  "remaining": 7,
  "period": "lifetime",
  "period_key": "lifetime"
}
```

### 4.4 问题列表（可选）

```http
GET /v1/questions
```

返回当前 `question_config/*.jsonc` 支持的 `question_id` 列表。

## 5. 轮询建议

- 间隔：每 **3～5 秒** 请求一次 `GET /v1/jobs/{session_id}`
- 超时：建议客户端 **10 分钟** 后标记超时并联系运维
- 同一 `session_id` 重复提交：若任务仍在 `queued`/`running`，返回 **409**

## 6. 一键试调脚本

PowerShell（项目根目录）：

```powershell
.\scripts\partner_try.ps1 -ApiKey "your-secret-key-for-partner"
```

curl 示例见 `scripts/partner_try.sh`。

## 7. 必填字段速查

顶层：

- `user_id`（字符串，非空）

`session_input`：

- `session_metadata.session_id`（全局唯一，建议含时间戳）
- `question_parameters.question_metadata.question_id`（如 `CAR01_Q001`）
- `question_parameters.user_specification.required_inputs` / `optional_inputs`
- `palette_data`（含 `current_time`；八字/合盘题需 `person_a` 等，见 `_session_input.jsonc`）

## 8. 限制与说明

- 试调版使用进程内线程池，**最多 2 个并发**（可在 `config.json` → `partner_api.max_concurrent_jobs` 调整）
- 成功次数配额按 **API Key** 计数，持久化在 `{data_root}/_quota/success_counts.json` 的 `api_keys` 字段
- 不适合高并发生产；正式上线请改用独立 Worker + 消息队列
- 勿将 OpenAI Key 发给合作方；合作方仅持有 Partner API Key
- 默认试调 Key：`dev-partner-change-me`（`config.json` 中配置，上线前必须更换）

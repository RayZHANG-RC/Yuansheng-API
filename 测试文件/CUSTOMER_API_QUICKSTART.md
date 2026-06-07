# 分析 API 接入指南（合作方版）

本文档面向 **API 调用方（合作方开发）**，说明如何鉴权、提交分析任务、轮询结果及处理配额与错误。  
服务端部署、密钥签发与配额调整由我方运维完成，调用方无需也 **不应** 接触 OpenAI 等底层密钥。

---

## 1. 接入信息

| 项目 | 说明 |
|------|------|
| **Base URL** | 由我方商务/技术支持提供，例如 `http://your-api-host` |
| **API Key** | 由我方单独签发，请妥善保管，勿写入公开仓库或前端代码 |
| **协议** | HTTP（试调）/ HTTPS（正式环境，以实际为准） |
| **数据格式** | 请求与响应均为 JSON，`Content-Type: application/json` |
| **字符编码** | UTF-8 |

---

## 2. 快速开始

整体为 **异步** 流程：

```
1. POST /v1/analyze  提交任务 → 收到 session_id（202）
2. GET  /v1/jobs/{session_id}  轮询状态（queued → running → completed / failed）
3. status = completed 时，从 result.frontend_response 读取面向用户的文案
```

典型耗时：**约 1～5 分钟**（视题目与负载而定）。

---

## 3. 鉴权

每个需鉴权的请求须携带 **API Key**，任选一种方式：

```http
Authorization: Bearer <您的 API Key>
```

或

```http
X-API-Key: <您的 API Key>
```

Key 无效或缺失时返回 **401**。

---

## 4. 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查（无需鉴权） |
| `GET` | `/v1/questions` | 当前支持的 `question_id` 列表 |
| `GET` | `/v1/quota` | 当前 API Key 的成功调用配额 |
| `POST` | `/v1/analyze` | 提交分析任务（异步） |
| `GET` | `/v1/jobs/{session_id}` | 查询任务状态与结果 |

---

## 5. 提交分析

### 5.1 请求

```http
POST /v1/analyze
Content-Type: application/json
Authorization: Bearer <您的 API Key>
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 贵方用户唯一标识，用于会话归档（非配额维度） |
| `session_input` | object | 是 | 题目与排盘输入，结构见下文 |

**说明：**

- 无需提交 `user_settings`、`model_set`，由服务端按合作配置自动生成。
- `session_input.session_metadata.session_id` 须在贵方系统内 **全局唯一**（建议含日期与用户标识，便于排查）。

### 5.2 请求示例（CAR01_Q001）

```json
{
  "user_id": "partner_demo",
  "session_input": {
    "session_metadata": {
      "session_id": "20260605_partner_demo_CAR01_Q001"
    },
    "question_parameters": {
      "question_metadata": {
        "question_id": "CAR01_Q001"
      },
      "user_specification": {
        "required_inputs": [
          {
            "name": "地理位置信息",
            "input": "上海市"
          }
        ],
        "optional_inputs": [
          {
            "name": "当前单位性质",
            "input": "私营企业（含私营独资/私营有限公司/私营股份制）"
          }
        ],
        "other_context": ""
      }
    },
    "palette_data": {
      "current_time": "202606051200",
      "person_a": {
        "birth_time": "199001010800",
        "gender": "male"
      }
    }
  }
}
```

### 5.3 成功响应（202 Accepted）

```json
{
  "session_id": "20260605_partner_demo_CAR01_Q001",
  "status": "queued",
  "question_id": "CAR01_Q001",
  "user_id": "partner_demo",
  "poll_url": "/v1/jobs/20260605_partner_demo_CAR01_Q001",
  "quota": {
    "enabled": true,
    "max_successful_requests": 100,
    "used": 3,
    "remaining": 97,
    "period": "lifetime",
    "period_key": "lifetime"
  },
  "message": "任务已入队，请轮询 poll_url 获取结果（通常需 1～5 分钟）"
}
```

---

## 6. 查询任务

```http
GET /v1/jobs/{session_id}
Authorization: Bearer <您的 API Key>
```

### 6.1 状态说明

| status | 含义 | 调用方动作 |
|--------|------|------------|
| `queued` | 已入队，等待执行 | 继续轮询 |
| `running` | 分析进行中 | 继续轮询 |
| `completed` | 成功完成 | 读取 `result` |
| `failed` | 执行失败 | 查看 `error`，必要时联系技术支持 |

### 6.2 进行中示例

```json
{
  "session_id": "20260605_partner_demo_CAR01_Q001",
  "status": "running",
  "queued_at": "2026-06-07T13:20:01",
  "started_at": "2026-06-07T13:20:02"
}
```

### 6.3 完成示例

业务侧主要使用 `result.frontend_response`：

```json
{
  "session_id": "20260605_partner_demo_CAR01_Q001",
  "status": "completed",
  "finished_at": "2026-06-07T13:22:15",
  "result": {
    "session_metadata": {
      "session_id": "20260605_partner_demo_CAR01_Q001",
      "session_status": "completed",
      "completion_time": "202606071322"
    },
    "frontend_response": {
      "summary": "（面向用户的总结正文，UTF-8 中文）",
      "risk_points": [
        "（风险点 1）",
        "（风险点 2）"
      ]
    }
  }
}
```

### 6.4 失败示例

```json
{
  "session_id": "20260605_partner_demo_CAR01_Q001",
  "status": "failed",
  "error": "管线执行失败，详见 api_pipeline.log",
  "exit_code": 1
}
```

失败任务 **不计入** 成功配额。请保存 `session_id` 并联系技术支持排查。

---

## 7. 配额

配额绑定在 **API Key** 上：仅 **成功完成**（`status = completed`）的任务计入次数，失败、进行中的任务不计入。

### 7.1 查询配额

```http
GET /v1/quota
Authorization: Bearer <您的 API Key>
```

```json
{
  "enabled": true,
  "max_successful_requests": 100,
  "used": 3,
  "remaining": 97,
  "period": "lifetime",
  "period_key": "lifetime"
}
```

`period` 含义：

| 值 | 说明 |
|----|------|
| `lifetime` | 累计总量 |
| `daily` | 按自然日重置 |
| `monthly` | 按自然月重置 |

### 7.2 超额

提交新任务时若配额用尽，返回 **429**，示例：

```json
{
  "detail": {
    "error": "api_key_success_quota_exceeded",
    "message": "当前 API Key 已达到成功调用上限",
    "quota": {
      "enabled": true,
      "max_successful_requests": 100,
      "used": 100,
      "remaining": 0,
      "period": "lifetime"
    }
  }
}
```

如需提升配额，请联系我方商务或技术支持。

---

## 8. 获取题目列表

```http
GET /v1/questions
Authorization: Bearer <您的 API Key>
```

```json
{
  "question_ids": ["CAR01_Q001", "CAR01_Q002", "..."],
  "count": 80
}
```

各题目的必填/选填字段以我方提供的 **题目说明** 或 `question_id` 对应文档为准。不同题目对 `palette_data` 要求不同（如是否需 `person_b`、合盘 `synastry` 等）。

---

## 9. 轮询与重试建议

| 项 | 建议 |
|----|------|
| 轮询间隔 | 每 **3～5 秒** 一次 |
| 客户端超时 | **10 分钟** 仍为 `queued`/`running` 则标记超时并联系支持 |
| 网关 502/503/504 | 多为瞬时网络或网关问题，**指数退避重试** 同一 `GET /v1/jobs/...`，勿因此判定任务失败 |
| 重复提交 | 同一 `session_id` 在 `queued`/`running` 时再次 `POST /v1/analyze` 返回 **409** |

---

## 10. HTTP 状态码

| 状态码 | 含义 |
|--------|------|
| 202 | 任务已接受并入队 |
| 400 | 请求体字段缺失或格式错误 |
| 401 | API Key 无效或缺失 |
| 404 | `session_id` 不存在 |
| 409 | 同一会话正在处理中 |
| 429 | API Key 成功次数配额已用尽 |
| 502/503/504 | 网关或上游瞬时不可用，建议重试 |

---

## 11. 调用示例

### 11.1 curl

```bash
BASE="http://your-api-host"
KEY="your-api-key"

# 提交
curl -s -X POST "$BASE/v1/analyze" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d @request.json

# 轮询
curl -s -H "Authorization: Bearer $KEY" \
  "$BASE/v1/jobs/20260605_partner_demo_CAR01_Q001"

# 配额
curl -s -H "Authorization: Bearer $KEY" "$BASE/v1/quota"
```

### 11.2 Python

```python
import time
import requests

BASE = "http://your-api-host"
HEADERS = {"Authorization": "Bearer your-api-key"}

# 提交
r = requests.post(f"{BASE}/v1/analyze", headers=HEADERS, json=payload, timeout=60)
r.raise_for_status()
session_id = r.json()["session_id"]

# 轮询
deadline = time.time() + 600
while time.time() < deadline:
    job = requests.get(f"{BASE}/v1/jobs/{session_id}", headers=HEADERS, timeout=30)
    if job.status_code in (502, 503, 504):
        time.sleep(5)
        continue
    job.raise_for_status()
    data = job.json()
    if data["status"] in ("completed", "failed"):
        print(data)
        break
    time.sleep(5)
```

### 11.3 PowerShell（Windows）

请使用 **UTF-8** 解析响应，避免中文乱码：

```powershell
$BaseUrl = "http://your-api-host"
$Headers = @{ Authorization = "Bearer your-api-key" }

$resp = Invoke-WebRequest -Uri "$BaseUrl/v1/jobs/$sessionId" -Headers $Headers -UseBasicParsing
$job = $resp.Content | ConvertFrom-Json
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$job.result.frontend_response | ConvertTo-Json -Depth 5
```

建议使用 **PowerShell 7+**（`pwsh`）或上述 `Invoke-WebRequest` 方式；Windows PowerShell 5.x 直接 `Invoke-RestMethod` 可能出现编码问题。

---

## 12. session_input 字段速查

### 12.1 顶层（Analyze 请求）

| 字段 | 必填 |
|------|------|
| `user_id` | 是 |

### 12.2 session_input

| 路径 | 必填 | 说明 |
|------|------|------|
| `session_metadata.session_id` | 是 | 全局唯一会话 ID |
| `question_parameters.question_metadata.question_id` | 是 | 题目 ID，如 `CAR01_Q001` |
| `question_parameters.user_specification.required_inputs` | 视题目 | `{ "name", "input" }` 数组 |
| `question_parameters.user_specification.optional_inputs` | 否 | 空 `input` 的项会被服务端忽略 |
| `palette_data.current_time` | 视题目 | 格式 `yyyyMMddHHmm`，用于起卦 |
| `palette_data.person_a` | 视题目 | `birth_time`（`yyyyMMddHHmm`）、`gender`（`male`/`female`） |
| `palette_data.synastry` / `person_b` | 合盘题 | 合盘题需按题目说明传入 |

`required_inputs` / `optional_inputs` 中 **`name` 须与题目定义一致**，`input` 为用户填写内容。

---

## 13. 安全与合规

- API Key 仅用于服务端调用，不要暴露给浏览器或移动端明文存储。
- 请求体可能含用户出生时间等敏感信息，请贵方按隐私合规要求传输与存储。
- 试调环境并发能力有限；生产级流量、SLA 与 HTTPS 域名请与我方另行约定。

---

## 14. 支持

| 场景 | 联系方式 |
|------|----------|
| 申请 / 轮换 API Key | 商务或技术支持 |
| 配额调整 | 同上 |
| 任务 `failed` 或长时间 `running` | 提供 `session_id` 与请求时间 |
| 题目字段疑问 | 提供 `question_id` |

---

*文档版本：与 API v0.1.0 对齐（异步 analyze + jobs 轮询 + API Key 配额）。*

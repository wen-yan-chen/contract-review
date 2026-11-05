# Nexent 北向 API 实测笔记

> 基于本地部署 Nexent v2.8.0 实测（2026-11-04），非文档推测。
> Base URL：`http://localhost:5013`（`/nb/v1/...` 与 `/api/nb/v1/...` 两种前缀均可用）
> 文档：`/openapi.json`（31 KB，29 个接口）；`/docs` 页面依赖 CDN，离线环境会白屏

---

## 1. 鉴权

- 方式：`Authorization: Bearer <API_KEY>`
- Key 生成位置：控制台 **右上角头像 → 个人设置 → 生成 API Key**（前端键名 `profile.generateAkSk`）
- 作用域：**只能调用同租户（tenant）下的 Agent**；不是租户内全部资源的管理员权限
- 错误响应：`401 {"message": "Invalid or missing bearer token"}`

## 2. 已验证可用的接口

| 接口 | 方法 | 实测结果 |
|---|---|---|
| `/nb/v1/health` | GET | 200 `{"status":"healthy","service":"northbound-api"}`，**无需鉴权** |
| `/nb/v1/agents` | GET | 200，返回当前租户全部 Agent 列表 |
| `/nb/v1/agents/{agent_name}` | GET | 单个 Agent 详情 |
| `/nb/v1/models` | GET | 200，返回模型列表（**含明文 api_key，见第 6 节**） |
| `/nb/v1/chat/run` | POST | 200，`text/event-stream`，见第 3 节 |
| `/nb/v1/conversations/{id}` | GET | 会话历史 |
| `/nb/v1/knowledge/indices` | GET | **403 `restricted to asset administrators`**，见第 5 节 |

### `/nb/v1/agents` 返回字段（节选）

```json
{"message":"success","data":[{
  "name":"tourism_assistant",          // ← chat/run 用的 agent_name
  "display_name":"旅游规划助手",
  "description":"...",
  "model_names":["deepseek-chat"],
  "is_main_agent":true,
  "is_available":true,
  "current_version_no":1
}],"requestId":"..."}
```

## 3. `/nb/v1/chat/run` 请求与响应

**请求**

```json
POST /nb/v1/chat/run
Authorization: Bearer <KEY>
Content-Type: application/json

{
  "agent_name": "tourism_assistant",   // 必填
  "query": "用一句话介绍你自己",        // 必填
  "conversation_id": 4,                // 可选，多轮时传上一轮返回的 id
  "attachments": [],                   // 可选
  "model_id": 1,                       // 可选
  "tool_params": {}                    // 可选
}
```

可选头：`Idempotency-Key`（幂等，防重复提交）

**响应：SSE 流（`text/event-stream`）**，每行 `data: {json}`

| 事件 `type` | 含义 | 关键字段 |
|---|---|---|
| `conversation_created` | 会话创建，**首轮必取** | `content.conversation_id` |
| `other` | 控制类信息（如 token 预算预留） | `content`（JSON 字符串） |
| `agent_new_run` | 本次 run 的起始上下文 | `content` |
| `step_count` | 步骤编号（多智能体编排的痕迹） | `content`、`step_id` |
| `model_attempt_control` | 模型调用尝试（重试/降级） | `phase`、`attempt_id`、`attempt` |
| `final_answer` | **正文增量**，需按序拼接 | `content`（delta 片段）、`answer_phase:"delta"`、`unit_index` |

**拼接规则**：把所有 `type == "final_answer"` 且 `answer_phase == "delta"` 的 `content` 按到达顺序连接，即为完整回答。

## 4. 客户端实现要点

- 用 `urllib` 即可，**不引入 requests 依赖**（有利于"干净环境一次部署"）
- 必须设置 `Accept: text/event-stream`
- 逐行读取，丢弃空行与 `data: [DONE]`
- 401 → 抛 `NexentAuthError`；403 → 抛 `NexentPermissionError`；超时 → 可重试但要带 `Idempotency-Key` 防重复
- **降级路径**：Nexent 不可达时切本地 LLM 直连，保证演示不中断（这是"现场演示"的保险丝）

## 5. 知识库接口的权限坑（重要）

`/nb/v1/knowledge/*` 全部返回：

```
403 {"message":"This endpoint is restricted to asset administrators."}
```

含义：**北向 Key 不是资产管理员，不能通过 API 建索引/传文件**。

应对（按推荐顺序）：

1. **在控制台 UI 里建知识库并挂到 Agent**（评审要看的就是平台侧配置，本就应该在 UI 做）
2. 让管理员把该账号提升为资产管理员后再走 API
3. 本项目的规则检索如果必须在后端做，就用自己的本地索引（Elasticsearch `localhost:9210` 已在跑），不依赖北向知识库接口

## 6. 安全提示

`GET /nb/v1/models` 会**明文返回模型的 `api_key`**（如 DeepSeek 的 `sk-...`）。也就是说任何持有北向 Key 的人都能读到模型密钥。对本机比赛演示无所谓，但如果把这个 Key 或 `/nb/v1/models` 的响应截图发到公开场合（演示视频、PR），**务必先脱敏**，并考虑赛后轮换该 DeepSeek Key。

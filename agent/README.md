# 智能体配置说明

本目录存放 Nexent 智能体的导出配置与可读副本。

| 文件 | 内容 | 说明 |
|---|---|---|
| `agent.json` | Nexent 导出的完整智能体配置 | **含提示词、工具、模型配置**，可直接导入平台 |
| `prompt.md` | 系统提示词的 Markdown 副本 | 与 `agent.json` 的 `prompt` 字段逐字一致，便于阅读与 diff |
| `配置清单.md` | 配置项逐条说明 | 建智能体时对照填写用 |

## agent.json 包含什么

```json
{
  "agent_id": 6,
  "agent_info": {
    "6": {
      "agent_id": 6,
      "name": "contract_review",
      "display_name": "contract_review_agent",
      "description": "面向银行与持牌金融机构的贷款合同智能审查助手…",
      "author": "…",
      "max_steps": 15,
      "prompt": "（2942 字符的完整系统提示词）",
      "tools": [{"class_name": "KnowledgeBaseSearchTool", "name": "knowledge_base_search"}],
      "model_ids": [1],
      "model_names": ["deepseek-chat"],
      "skill_names": ["loan-rule-cards", "missing-clause-audit", "risk-selfcheck", "suggestion-compiler"],
      "managed_agents": [],
      "model_params_override": {"1": {"extra_params": {}}}
    }
  },
  "mcp_info": []
}
```

| 字段 | 含义 |
|---|---|
| `prompt` | 系统提示词全文，与 `prompt.md` 逐字一致（2942 字符） |
| `tools` | 已绑定知识库检索工具 `KnowledgeBaseSearchTool` |
| `skill_names` | 依赖 4 个自定义 Skill，需**先安装**（见 `skills/`） |
| `model_names` | `deepseek-chat` |
| `max_steps` | 15 |
| `mcp_info` | 空（本智能体未使用自定义 MCP） |
| `skill_names` | 空（未使用自定义 Skill） |

> 说明：`tools` 里绑定的是知识库**检索工具**，具体的知识库实例
> （`contract-rules`）在平台侧关联，不写进导出文件。复现时需在控制台
> 「知识库管理」中把该知识库添加给智能体。

## 导入即用

在 Nexent 控制台：智能体开发 → 导入 → 上传 `agent.json`，即可得到一个
与本项目一致（提示词、模型、知识库工具绑定齐全）的智能体。

导入后仍需补一步：把知识库 `contract-rules`（内容来自 `data/kb/rules-full.md`）
添加到该智能体，否则 `legal_basis` 会全部返回「未检索到权威依据」。

## 依赖的知识库

| 项 | 值 |
|---|---|
| 知识库名称 | `contract-rules` |
| 源文件 | `data/kb/rules-full.md`（由 `tools/export_kb.py` 从 `data/rules/rules.yaml` 生成） |
| 内容 | 40 条规则 + 40 条合规范式 + 依据（当前为「待核验」） |
| 向量模型 | `bge-m3`（Ollama，1024 维） |

> 知识库接口 `/nb/v1/knowledge/*` 需要「资产管理员」权限，普通北向 Key 无法调用，
> 因此知识库的创建与上传必须在 Nexent 控制台完成。

## 自定义参数

平台「模型配置 → 自定义参数」中设置了 `temperature = 0`，用于降低输出波动。
该参数不在 `agent.json` 的 `model_params_override.extra_params` 里（导出时为空），
导入后需要手动补一次。

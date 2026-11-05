# 智能体配置说明

本目录存放 Nexent 智能体的配置与存档。

| 文件 | 内容 | 说明 |
|---|---|---|
| `agent.json` | 平台导出的智能体元数据 | Nexent 导出功能的产品，含 name / display_name / description / max_steps |
| `prompt.md` | 系统提示词全文 | **平台导出不含提示词**，因此单独存档；以本文件为准 |
| `配置清单.md` | 配置项逐条说明 | 建智能体时对照填写用 |

## 重要说明：agent.json 不完整是平台限制

Nexent 导出的 `agent.json` 只包含元数据：

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
      "requested_output_tokens": null
    }
  },
  "mcp_info": []
}
```

**不包含**：`system_prompt`、知识库绑定、模型与参数配置。
这些只能在 Nexent 控制台里查看或修改，因此本项目额外提供 `prompt.md` 作为提示词存档。

复现该智能体的完整步骤：

1. Nexent 控制台 → 智能体配置 → 新建
2. 名称 `contract_review`，显示名 `contract_review_agent`
3. 描述见 `配置清单.md` 第 1 节
4. 模型选 `deepseek-chat`，自定义参数 `temperature = 0`
5. 提示词粘贴 `prompt.md` 中的内容
6. 知识库管理 → 添加 `contract-rules`（内容来自 `data/kb/rules-full.md`）
7. 发布

## 依赖的知识库

| 项 | 值 |
|---|---|
| 知识库名称 | `contract-rules` |
| 源文件 | `data/kb/rules-full.md`（由 `tools/export_kb.py` 从 `data/rules/rules.yaml` 生成） |
| 内容 | 40 条规则 + 40 条合规范式 + 依据（当前为「待核验」） |
| 向量模型 | `bge-m3`（Ollama，1024 维） |

> 知识库接口 `/nb/v1/knowledge/*` 需要「资产管理员」权限，普通北向 Key 无法调用，
> 因此知识库的创建与上传必须在 Nexent 控制台完成。

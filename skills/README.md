# 技能包（Nexent Skills）

由 `python tools/build_skills.py` 生成，`dist/` 下是可直接上传的 ZIP。

| 技能 | 类型 | 作用 | 目标指标 |
|---|---|---|---|
| `loan-rule-cards` | 知识类（含 4 份 `<reference>`） | 按 rule_id 精确返回判定条件 / 合规定式 / 缺陷形态 / 已知误报 | 误报率 |
| `missing-clause-audit` | 流程类 | 三态判定：缺失 / 效力不足 / 合规 | 检出率 |
| `risk-selfcheck` | 流程类 | 输出前四问，不通过即删除 | 误报率、一致性 |
| `suggestion-compiler` | 流程类 | 建议必须是可直接替换的完整条款 | 建议可用性 |

## 上传步骤（控制台）

1. 技能仓库 → 我的 Skill → 创建 Skill → 上传技能文件，逐个上传 `dist/*.zip`。
2. 智能体开发 → `contract_review` → 选择工具 → **Skills** 页签 → 勾选四个技能。
3. 保存智能体。

## 注意

- ZIP 根目录必须是 `SKILL.md`（本脚本已按此打包）。若平台提示缺少 SKILL.md，
  改为「技能名/SKILL.md」的目录结构再压一次。
- 技能是**按需加载**：提示词里要写清「判任何规则前先取规则卡」，
  否则模型可能不激活。
- 判定结果仍需服务端 `gate` 兜底：技能负责过程可见，代码负责结果确定。

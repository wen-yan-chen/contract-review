---
name: risk-selfcheck
description: 输出风险清单前的逐条自检。当已形成 risks 列表、准备输出 JSON 时使用：核对判据来源、条款归属、引用逐字性与等级依据，任一不通过即删除该条，不允许修补后保留。
tags:
  - contract-review
  - quality-gate
---

# 输出前自检

## 四问（任一为「否」→ 删除，不要修补）

1. **判据来源**：判定条件是否逐字出现在规则卡里？是「我认为应该」→ 否。
2. **条款归属**：quote 是否在当前 clause_no 的正文里连续出现？
3. **文字支撑**：能否指出条款里直接体现该判据的文字？指不出 → 否。
4. **等级依据**：`risk_level` 是否等于规则默认等级，或有卡里写明的升级条件？

## 已知必须删除的形态（来自本项目 28 条误报复核）

| 形态 | 例子 |
|---|---|
| 自造判据 | R16：「最高债权额等于本金，未覆盖利息」——规则不判金额是否高于本金 |
| 套错规则 | 把「意向书失效」挂到 R40「解除后清算顺序」 |
| 把「没约定」当「违反」 | R33 只约定了诉讼管辖、全文没有仲裁——不满足「诉讼与仲裁并存」 |
| 用无关条款论证 | 条款讲生效时间，却用来证明 R40 清算顺序缺失 |
| 把合规写法当风险 | 罚息上浮 50% 且设合计上限——属合规定式 |
| 跨条款推理 | 「与其他条款叠加」「累计计算」「与附件冲突」作为报告理由 |

## 输出

```json
{"keep": [0, 2], "drop": [{"index": 1, "reason": "criterion_not_in_card"},
                          {"index": 3, "reason": "quote_not_in_clause"}]}
```

reason 取值固定：`criterion_not_in_card` / `quote_not_in_clause` / `no_text_support` /
`level_mismatch` / `cross_clause_reasoning` / `compliant_pattern`。

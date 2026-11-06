---
name: loan-rule-cards
description: 贷款合同审查的规则卡库。当需要判定某条款是否违反 R01–R40 中的某条规则、或需要确认该规则的判定条件、合规定式与缺陷形态时使用：按条款类别加载对应规则卡，只依据卡面判据下结论。
tags:
  - contract-review
  - rules
  - compliance
---

# 贷款合同规则卡

## 这个技能解决什么

知识库是语义检索，top-3 里经常混进「措辞相近、判定条件不同」的规则，
结果是把 A 规则的问题挂到 B 规则上——这是本项目历史上最主要的误报来源（28 条误报中 25 条属此类）。
规则卡按 rule_id 精确返回，不经过相似度排序。

## 取卡方式

1. 先判断条款属于哪一类：利率 / 担保 / 违约 / 合规。
2. **只加载该类**规则卡，不要一次加载四类。
3. 类内按风险类型或关键词定位候选规则，最多 3 条，不要全量比对。

## 使用纪律（必须遵守）

1. 判定只能依据卡里的【判定条件】原文，不得扩展、类推、引入行业惯例。
2. 卡里没有的判据 = 不能用。典型反例：R16 只判「是否写明具体最高债权额及其构成」，
   不得因为「金额等于本金」「未区分本金限额」「担保范围未含违约金」而报违反。
3. 命中【合规定式】→ 直接不报，不再讨论。
4. 命中【缺陷特征】→ 必须报，quote 取缺陷对应的原文片段。
5. `risk_level` 取该规则的默认等级；只有卡里写明升级条件且条款满足时才升级。
6. 条款的问题不属于任何规则 → 不报。**不要用最接近的规则代替**。

## 规则族索引

<reference path="cards/interest.md" />
<reference path="cards/guarantee.md" />
<reference path="cards/breach.md" />
<reference path="cards/compliance.md" />

## 判定输出

每条判定返回一行：

```json
{"clause_no": "第四十六条", "rule_id": "R16", "verdict": "violate|compliant|unmatched",
 "criterion": "卡面判定条件原文", "matched_form": "命中缺陷特征的原文片段", "default_level": "高"}
```

`verdict=violate` 的条目才进入风险清单；`compliant` 与 `unmatched` 直接丢弃。

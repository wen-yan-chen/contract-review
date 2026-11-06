"""从 rules.yaml / compliant.yaml 生成 4 个 Nexent 技能包。

产物：
    skills/loan-rule-cards/SKILL.md + cards/{interest,guarantee,breach,compliance}.md
    skills/missing-clause-audit/SKILL.md
    skills/risk-selfcheck/SKILL.md
    skills/suggestion-compiler/SKILL.md
    skills/dist/<name>.zip          ← 直接上传到 Nexent 技能仓库

用法：
    python tools/build_skills.py            # 生成并打包
    python tools/build_skills.py --no-zip   # 只生成目录

规则卡内容全部来自 data/rules/rules.yaml 与 data/rules/compliant.yaml；
"已知误报形态"来自 data/review/fp_list.md 的 28 条人工复核结论，
在这里以常量维护（改规则时记得同步）。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
DIST = SKILLS / "dist"

# 历史误报复核结论（data/review/fp_list.md），按 rule_id 归并。
# 这些是"看似风险、实则不成立"的具体形态，直接写进规则卡，
# 比在系统提示词里写一百条闸门都管用。
KNOWN_FP: dict[str, list[str]] = {
    "R02": ["罚息按合同利率上浮 50% 且设合计上限 → 合规定式，不报（C10-024、C14-012）"],
    "R06": ["全合同只出现一种计息口径（360 或 365），未并存 → 不成立（C12-029）"],
    "R11": ["条款只写「保证」但内容与保证方式无关 → 不成立（C15-043）"],
    "R16": [
        "已写明「本最高额担保所担保的最高债权额为人民币 X 万元」→ 不成立（C02-046、C09-037、C12-036、C21-043）",
        "不得以「金额等于本金」「未区分本金限额」「担保范围未含违约金」为由报告——规则不判这些",
    ],
    "R20": ["未见「排除司法程序自行处置担保物」的表述 → 不成立（C12-043）"],
    "R23": [
        "只写「应支付违约金／赔偿实际损失」、未约定具体计收标准 → 不成立（C01-055、C11-060、C12-053）",
        "给出具体计收标准（如每日万分之五）且与损失赔偿并行 → 成立（C10-052）",
    ],
    "R24": ["未见违约金与罚息并行计收的约定 → 不成立（C11-068、C12-064）"],
    "R26": ["交叉违约已有金额等限定条件 → 不成立（C11-061、C11-064）"],
    "R33": ["仅约定诉讼管辖、全文未出现仲裁 → 不成立（C02-070、C12-071）"],
    "R34": ["管辖地与合同存在法定连接点 → 不成立（C02-068、C12-070）"],
    "R40": [
        "已约定解除后的处理 → 不成立（C11-089、C12-094）",
        "条款内容与「解除后清算顺序」无关 → 不成立（C02-093、C02-097），这是本项目最常被套错的规则",
    ],
}

CATEGORY_SLUG = {"利率": "interest", "担保": "guarantee", "违约": "breach", "合规": "compliance"}
CATEGORY_TITLE = {
    "利率": "利率类规则卡",
    "担保": "担保类规则卡",
    "违约": "违约类规则卡",
    "合规": "合规类规则卡",
}

# 缺失型规则的同义词检索表（missing-clause-audit 使用）
SYNONYMS = {
    "电子签名": "电子签名 / 电子签章 / 数字证书 / CA 证书 / 可靠电子签名 / 签署时间戳 / 电子合同",
    "最高额": "最高额 / 最高债权额 / 最高额度 / 授信余额",
    "抵押": "抵押登记 / 抵押 / 他项权证 / 不动产登记 / 办理登记",
    "提前到期": "提前到期 / 加速到期 / 宣布到期 / 提前收回",
    "交叉违约": "交叉违约 / 其他债务 / 其他合同项下违约",
    "保证": "保证 / 担保 / 连带责任保证 / 一般保证",
}


def load_rules() -> tuple[list[dict], dict[str, dict]]:
    rules = yaml.safe_load((ROOT / "data/rules/rules.yaml").read_text(encoding="utf-8"))
    compliant = yaml.safe_load((ROOT / "data/rules/compliant.yaml").read_text(encoding="utf-8"))
    return rules, {c["rule_id"]: c for c in compliant["rules"]}


def render_card(rule: dict, comp: dict) -> str:
    rid = rule["rule_id"]
    judge = rule.get("judge", "")
    tag = "计入指标" if judge == "deterministic" else "不计分，仅提示"
    lines = [
        f"### {rid} {rule['title']}　`{rule.get('risk_level', '')}`　`{tag}`",
        "",
        f"- **risk_type（必须逐字使用）**：{rule['risk_type']}",
        f"- **判定条件**：{rule['detect'].get('llm_hint', '').strip()}",
        f"- **证据要素**：{' · '.join(rule.get('evidence_spec') or [])}",
        f"- **合规定式**：{comp.get('compliant_text', '').strip()}",
    ]
    regex = (rule.get("detect") or {}).get("regex")
    if regex:
        lines.append(f"- **缺陷特征（正则线索）**：`{regex}`")
    lines.append(f"- **建议模板**：{rule.get('suggestion_template', '').strip()}")
    if "【" in rule.get("suggestion_template", ""):
        lines.append("  - 模板中的 `【】` 必须替换为合同对应要素（金额取本金上浮 20% 的整数），禁止原样输出占位符。")
    kws = rule.get("suggestion_keywords") or []
    if kws:
        lines.append(f"- **建议关键词**：{'、'.join(str(k) for k in kws)}")
    if rid in KNOWN_FP:
        lines.append("- **已知误报形态（务必不要报）**：")
        lines.extend(f"  - {x}" for x in KNOWN_FP[rid])
    lines.append("")
    return "\n".join(lines)


def render_cards(rules: list[dict], comps: dict[str, dict]) -> dict[str, str]:
    by_cat: dict[str, list[dict]] = {}
    for r in rules:
        by_cat.setdefault(r["category"], []).append(r)

    out = {}
    for cat, items in by_cat.items():
        slug = CATEGORY_SLUG[cat]
        ids = f"{items[0]['rule_id']}–{items[-1]['rule_id']}"
        body = [
            f"# {CATEGORY_TITLE[cat]}（{ids}）",
            "",
            "> 由 `tools/build_skills.py` 从 `data/rules/rules.yaml`、`data/rules/compliant.yaml` 生成，请勿手改。",
            "> `计入指标` = judge: deterministic；`不计分，仅提示` = discretionary。",
            "",
        ]
        body.extend(render_card(r, comps.get(r["rule_id"], {})) for r in items)
        out[slug] = "\n".join(body).rstrip() + "\n"
    return out


LOAN_RULE_CARDS_SKILL = """---
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
"""


def missing_rules(rules: list[dict]) -> list[dict]:
    keys = ("未约定", "缺失", "不明", "不足", "未明确")
    # R33 是「诉讼与仲裁并存」的冲突型，不是缺失型，判定口径不同，不放进本技能
    exclude = {"R33"}
    return [r for r in rules if r["rule_id"] not in exclude and any(k in r["title"] for k in keys)]


def build_missing_skill(rules: list[dict]) -> str:
    rows = []
    for r in missing_rules(rules):
        ev = "、".join(r.get("evidence_spec") or []) or "—"
        rows.append(f"| {r['rule_id']} | {r['title']} | {r['risk_type']} | {ev} |")
    table = "\n".join(rows)

    syn_rows = []
    for topic, words in SYNONYMS.items():
        matched = [r for r in missing_rules(rules) if topic in r["risk_type"] or topic in r["title"]]
        if matched:
            syn_rows.append(f"| {topic} | {words} |")
    syn_table = "\n".join(syn_rows) if syn_rows else "| 电子签名 | 电子签名 / 电子签章 / 数字证书 / 可靠电子签名 / 签署时间戳 |"

    return f"""---
name: missing-clause-audit
description: 缺失型与效力型风险审计。当某条规则的表述含「未约定/缺失/不明/不足」，或按关键词在全文检索不到对应约定时使用：区分真缺失、写了但效力不足、以及合规三种形态，避免把「有条款」直接当成「没问题」。
tags:
  - contract-review
  - missing-clause
  - audit
---

# 缺失 / 效力审计

## 为什么要单独做

规则标题写「缺失」时，模型容易只做「有没有」的二值判断：
条款里出现了「电子签名」三个字就认为不缺失，
于是「写了但效力不利」的情形被整批漏掉——本项目 3 条漏检全部属于这一类
（条款写「电子签名的效力以出借人系统记录为准」，被当成「已约定电子签名」放行）。

## 三态判定（必须三选一，不许二值）

| 形态 | 判据 | 动作 |
|---|---|---|
| **missing 缺失** | 本条与全文（含表格、附件）按同义词检索仍无对应约定 | 报，锚定最相关条款作 clause_no |
| **insufficient 效力不足** | 有约定，但把效力交给一方单方记录、排除法定要件、未约定交付/存证/登记 | **报**（重点，最易漏） |
| **compliant 合规** | 有约定且满足要件（见各规则卡的合规定式） | 不报 |

## 检索纪律

1. 先在本条内检索，再在全文（含表格、附件）检索，最后才判 missing。
2. 用同义词表检索，不要只用规则标题里的词。
3. 一旦检索到 → 进入 insufficient / compliant 分支，**不要再判 missing**。

## 同义词表

| 主题 | 检索词 |
|---|---|
{syn_table}

## 需要按本技能审计的规则（自动生成）

| 规则 | 标题 | 风险类型 | 证据要素 |
|---|---|---|---|
{table}

## 边界（与系统提示词的「不可判定事项」区分）

- **不可判定**：是否真的签署、谁签的、有没有录音录像、是否加粗提示、当事人真实意思。
- **可判定**：条款有没有约定效力标准、有没有约定合同文本交付与存证、有没有约定登记义务。
- 条款存在 ≠ 合规。「有约定」只完成了三态里的第一步排除。
- 特别提醒 R38：条款写「电子签名的效力以出借人系统记录为准」是**缺陷形态**
  （把合同效力交给一方单方记录，且未约定可靠电子签名与文本交付），必须报。

## 输出

```json
{{"rule_id": "R38", "clause_no": "第八十三条", "verdict": "missing|insufficient|compliant",
 "anchor_clause": "第八十三条", "evidence": "条款原文片段",
 "missing_element": "可靠电子签名标准 / 合同文本交付与存证"}}
```
"""


RISK_SELFCHECK_SKILL = """---
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
"""


SUGGESTION_SKILL = """---
name: suggestion-compiler
description: 把风险项编译成可直接替换的条款表述。当需要生成或改写 suggestion 字段时使用：输入规则号、原条款与合同要素，输出完整、可粘贴、无占位符的条款文本。
tags:
  - contract-review
  - drafting
---

# 修改建议编译

## 目标

审查岗拿到建议后，能直接替换原文，不需要再改一个字。

## 结构（缺一不可）

**主体 + 触发条件 + 数值/口径 + 违约后果 + 救济或例外**

## 硬约束

1. 不许出现 `【】`、`____`、`××`、「建议补充」「进一步完善」等占位或空话。
2. 合同已有的金额、利率、期限必须继承；需要新数值时给出确定数值，不要留空。
3. 与原条款长度可比（±50%）。
4. 只改法律表述，不改商业条件（利率水平、担保方式、期限）。
5. 必须包含该规则卡列出的建议关键词。

## 示例

- 差：`建议完善罚息条款。`（无结构、不可替换）
- 好：`逾期罚息按合同执行利率上浮 50% 计收，罚息、复利与利息合计不超过法律及司法解释规定的上限；出借人计收前应书面通知借款人。`

## 自检

把建议单独拿给一个没看过上下文的人，他能否直接替换原文？不能 → 重写。
"""


SKILLS_README = """# 技能包（Nexent Skills）

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
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"  {path.relative_to(ROOT)}  ({len(text.splitlines())} 行)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-zip", action="store_true")
    args = ap.parse_args()

    rules, comps = load_rules()
    print(f"规则 {len(rules)} 条，合规定式 {len(comps)} 条")

    if SKILLS.exists():
        for child in SKILLS.iterdir():
            if child.name != "README.md":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
    SKILLS.mkdir(exist_ok=True)

    cards = render_cards(rules, comps)
    write(SKILLS / "loan-rule-cards/SKILL.md", LOAN_RULE_CARDS_SKILL)
    for slug, text in cards.items():
        write(SKILLS / f"loan-rule-cards/cards/{slug}.md", text)

    write(SKILLS / "missing-clause-audit/SKILL.md", build_missing_skill(rules))
    write(SKILLS / "risk-selfcheck/SKILL.md", RISK_SELFCHECK_SKILL)
    write(SKILLS / "suggestion-compiler/SKILL.md", SUGGESTION_SKILL)
    write(SKILLS / "README.md", SKILLS_README)

    if args.no_zip:
        return 0

    DIST.mkdir(exist_ok=True)
    for z in DIST.glob("*.zip"):
        z.unlink()
    for name in ("loan-rule-cards", "missing-clause-audit", "risk-selfcheck", "suggestion-compiler"):
        target = DIST / f"{name}.zip"
        base = SKILLS / name
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(base.rglob("*")):
                if f.is_file():
                    zf.write(f, f.relative_to(base).as_posix())
        print(f"  dist/{target.name}  {target.stat().st_size / 1024:.1f} KB")

    print("\n完成。下一步：上传 dist/*.zip → 智能体 Skills 页签勾选 → 重跑 batch。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

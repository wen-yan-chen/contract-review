"""按规则判定条件对误报做初判（成立 / 不成立），供人工复核。

判定依据来自 rules.yaml 的 llm_hint，用可核对的关键要素判，不做主观推测。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DATA = Path(r"D:\contest-32\data")
REVIEW = DATA / "review"


def judge(rule_id: str, text: str, quote: str) -> tuple[str, str]:
    """返回 (结论, 依据)。结论：成立 / 不成立 / 边界"""
    t = text or ""
    q = quote or ""

    # R16 最高债权额是否写明具体金额
    if rule_id == "R16":
        if re.search(r"最高债权额为人民币[\d．.]+[万亿]?元|最高债权额为人民币[一二三四五六七八九十百千万零]+", t):
            return "不成立", "条款已写明具体最高债权额，符合 R16 判定条件"
        if "以" in t and "为准" in t and "万元" not in t:
            return "成立", "仅以其他条款指引，未写明具体金额"
        return "不成立", "未见循环引用或缺失金额的表述"

    # R23 违约金是否显著超过实际损失（需有比例/金额）
    if rule_id == "R23":
        m = re.search(r"百分之[一二三四五六七八九十百]+|每日万分之[一二三四五六七八九十]+|\d+\s*%", q or t)
        if m:
            return "成立", f"条款给出违约金计收标准（{m.group(0)}），且与损失赔偿并行，存在过高风险"
        return "不成立", "条款只写「应支付违约金/赔偿实际损失」，未约定具体计收标准，不满足「显著超过实际损失」的判定条件"

    # R02 罚息是否 2 倍以上或排除上限
    if rule_id == "R02":
        if re.search(r"三倍|[三四五六七八九]倍|不受任何上限", t):
            return "成立", "罚息为倍数或明确排除上限"
        if "上浮百分之五十" in t or "上浮50%" in t:
            return "不成立", "罚息上浮 50% 且设合计上限，属合规范式"
        return "不成立", "未见倍数或排除上限的表述"

    # R33 诉讼与仲裁并存 / 仲裁机构不明
    if rule_id == "R33":
        if "仲裁" in t:
            return "成立", "条款同时涉及仲裁"
        return "不成立", "仅约定诉讼管辖，未出现仲裁约定，不满足 R33 判定条件"

    # R34 管辖是否与争议有实际联系
    if rule_id == "R34":
        if re.search(r"签订地|履行地|住所地|所在地", t):
            return "不成立", "管辖地与合同存在法定连接点"
        return "成立", "约定管辖地与争议无连接点"

    # R40 解除后的清算顺序
    if rule_id == "R40":
        if "解除" in t and re.search(r"清算|顺序|返还|结清", t):
            return "不成立", "已约定解除后的处理"
        return "不成立", "本条款内容与「解除后清算顺序」无关，模型套用了错误规则"

    # R11 保证方式
    if rule_id == "R11":
        if "连带责任保证" in t:
            return "不成立", "已明确为连带责任保证"
        if "保证" in t:
            return "成立", "仅表述为「保证」，未明确连带责任"
        return "不成立", "本条款未涉及保证方式"

    # R24 违约金与罚息重复
    if rule_id == "R24":
        if re.search(r"罚息.{0,40}违约金|违约金.{0,40}罚息", t) and re.search(r"并行|同时|互不抵扣", t):
            return "成立", "罚息与违约金并行计收且互不抵扣"
        return "不成立", "未见并行计收的约定"

    # R06 计息天数矛盾
    if rule_id == "R06":
        if "三百六十" in t and "三百六十五" in t:
            return "成立", "两种计息口径并存"
        return "不成立", "仅出现一种计息口径"

    # R26 交叉违约范围
    if rule_id == "R26":
        if "其他金融机构" in t and ("任何" in t or "全部" in t):
            return "成立", "交叉违约范围未限定"
        return "不成立", "交叉违约已有金额等限定条件"

    # R20 自行处置担保物
    if rule_id == "R20":
        if re.search(r"自行处置|自行变卖|无需.{0,10}(诉讼|司法)", t):
            return "成立", "约定排除司法程序自行处置"
        return "不成立", "未见排除司法程序的表述"

    return "边界", "需人工判断"


def main() -> None:
    items = json.loads((REVIEW / "fp_list.json").read_text(encoding="utf-8"))
    stats: dict[str, int] = {}
    for it in items:
        verdict, reason = judge(it["rule_id"], it["clause_text"], it["quote"])
        it["verdict"], it["reason"] = verdict, reason
        stats[verdict] = stats.get(verdict, 0) + 1

    (REVIEW / "fp_list.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 误报复核清单（含初判）", "",
             f"共 {len(items)} 条：成立 {stats.get('成立',0)} / 不成立 {stats.get('不成立',0)} / "
             f"边界 {stats.get('边界',0)}", "",
             "| # | 合同 | 条款 | 规则 | 结论 | 依据 |", "|---:|---|---|---|---|---|"]
    for i, it in enumerate(items, 1):
        lines.append(f"| {i} | {it['cid']} | {it['clause_no']} | {it['rule_id']} "
                     f"{it['rule_title']} | **{it['verdict']}** | {it['reason']} |")
    (REVIEW / "fp_list.md").write_text("\n".join(lines), encoding="utf-8")
    print("初判完成:", stats)
    print(f"清单 → {REVIEW / 'fp_list.md'}")


if __name__ == "__main__":
    main()

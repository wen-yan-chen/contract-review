r"""给 rules.yaml 的 40 条规则加 judge 标记，用于缩小计分范围。

  deterministic  可客观判定（有数值/存在性判据，评审抽检也能得到同一结论）
  discretionary  需主观权衡（"是否完善""是否过宽"），只作提示性建议，不计入指标

用法：
  python classify_rules.py              # 预览
  python classify_rules.py --apply      # 写入 rules.yaml（幂等，已有 judge 会跳过）
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RULES = r"D:\contest-32\data\rules\rules.yaml"

# 客观判据：数值阈值、要素缺失、文本矛盾、明确事实
DETERMINISTIC = {
    "R02": "罚息倍数/是否设上限，有数值判据",
    "R03": "放款时预扣利息，事实可查",
    "R06": "360 与 365 并存，文本矛盾可查",
    "R11": "是否写明「连带责任保证」，要素可查",
    "R12": "担保范围是否含利息/违约金/实现债权费用，要素可查",
    "R13": "保证期间是否短于法定下限，可计算",
    "R14": "是否约定办理抵押登记，要素可查",
    "R16": "最高额担保是否写明最高债权额，要素可查",
    "R19": "保证人是否属法律禁止主体，事实可查",
    "R20": "是否排除司法程序，表述可查",
    "R23": "违约金比例是否超限，有数值判据",
    "R24": "违约金与罚息是否重复计算，可核对",
    "R26": "交叉违约是否限定范围，要素可查",
    "R30": "是否赋予单方变更权，表述可查",
    "R33": "诉讼与仲裁是否并存，文本矛盾可查",
    "R34": "管辖地是否与法定连接点相关，可核对",
    "R35": "是否约定送达地址与视为送达，要素可查",
    "R38": "是否约定电子签名效力，要素可查",
    "R39": "是否按年化披露综合成本，要素可查",
    "R40": "是否约定解除后清算顺序，要素可查",
}

DISCRETIONARY = {
    "R01": "「基准是否足够明确」需主观权衡",
    "R04": "「复利约定是否清楚」主观",
    "R05": "「单方调息是否合理」主观",
    "R07": "「重定价安排是否完备」主观",
    "R08": "「费用是否应折算年化」主观",
    "R09": "「提前还款违约金是否过高」需比较基准",
    "R10": "「起息日不一致是否有影响」轻微主观",
    "R15": "「抵押率是否合理」需外部数据",
    "R17": "「质物保管责任是否清楚」主观",
    "R18": "「配偶同意是否必需」视情形",
    "R21": "「违约情形是否过宽」主观",
    "R22": "「加速到期是否随意」主观",
    "R25": "「宽限期是否必需」视交易习惯",
    "R27": "「费用承担是否应更细」主观",
    "R28": "「陈述保证是否过重」主观",
    "R29": "「是否需约定不可抗力」视情形",
    "R31": "格式条款的加粗提示无法在纯文本合同验证",
    "R32": "「是否属无效格式条款」需实质判断",
    "R36": "「个人信息处理是否合规」需结合告知文件",
    "R37": "「数据出境限制是否必要」视业务",
}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--path", default=RULES)
    args = ap.parse_args()

    assert set(DETERMINISTIC) | set(DISCRETIONARY) == {f"R{i:02d}" for i in range(1, 41)}, "覆盖不全"
    assert not (set(DETERMINISTIC) & set(DISCRETIONARY)), "分类冲突"

    path = Path(args.path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    out: list[str] = []
    current: str | None = None
    has_judge = False
    added = 0
    for line in lines:
        m = re.match(r"^-\s*rule_id:\s*(R\d{2})", line)
        if m:
            current = m.group(1)
            has_judge = False
            out.append(line)
            continue
        if current and re.match(r"^\s+judge:", line):
            has_judge = True
        if current and not has_judge and re.match(r"^\s{2}[a-z_]+:", line) and added >= 0:
            # 在规则块第一个二级键之前插入 judge
            judge = "deterministic" if current in DETERMINISTIC else "discretionary"
            reason = (DETERMINISTIC.get(current) or DISCRETIONARY.get(current) or "").replace('"', "'")
            out.append(f'  judge: {judge}   # {reason}\n')
            has_judge = True
            added += 1
        out.append(line)

    print(f"规则总数 40；deterministic {len(DETERMINISTIC)} 条，discretionary {len(DISCRETIONARY)} 条")
    print(f"本次写入 judge 字段 {added} 处")

    if args.apply:
        path.write_text("".join(out), encoding="utf-8")
        print(f"已写入 {path}")
    else:
        print("预览模式，未写入（加 --apply 生效）")

    # 预览前 6 行变化
    print("\n--- 前 12 行 ---")
    print("".join(out[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

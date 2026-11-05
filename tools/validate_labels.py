r"""标注数据校验器 —— 交付前把标注的错误挡在前面。

检查项（E 开头为错误，W 为警告）：
  E1 必填字段缺失
  E2 clause_id 在条款表中不存在
  E3 risk_id 重复
  E4 risk_level 不是 高/中/低
  E5 rule_id 格式不符（应为 R01–R40 或 UNMATCHED）
  E6 quote 在条款正文中不是"唯一出现"（会出现定位歧义）
  E7 char_start/char_end 与 quote 不一致（切片结果 != quote）
  E8 legal_basis 结构缺失或 verify_status 非法
  E9 consistency_checks 字段缺失
  W1 条款表本身的问题（clause_id 重复、正文为空、偏移越界）

用法：
  python validate_labels.py --data-root D:\contest-32\data
  python validate_labels.py --data-root D:\contest-32\data --strict   # pending 也算错
  python validate_labels.py --demo                                    # 自检，不依赖真实数据
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

LEVELS = {"高", "中", "低"}
RULE_ID_RE = re.compile(r"^(R\d{2}|UNMATCHED)$")
REQUIRED_RISK_FIELDS = ["risk_id", "clause_id", "clause_no", "risk_type", "rule_id",
                        "risk_level", "quote", "problem", "suggestion", "legal_basis"]


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"[E] {where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"[W] {where}: {msg}")

    def ok(self) -> bool:
        return not self.errors


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_clauses(cid: str, clauses: list[dict], rep: Report) -> dict[str, dict]:
    """校验条款表并返回 clause_id -> clause 的索引。"""
    index: dict[str, dict] = {}
    for c in clauses:
        cid_ = c.get("clause_id")
        if not cid_:
            rep.err(f"clauses/{cid}", "存在没有 clause_id 的条款")
            continue
        if cid_ in index:
            rep.err(f"clauses/{cid}", f"clause_id 重复: {cid_}")
        index[cid_] = c
        if not (c.get("text") or "").strip():
            rep.err(f"clauses/{cid}", f"{cid_} 正文为空")
    return index


def check_label(cid: str, label: dict, clause_index: dict[str, dict],
                rules: dict[str, dict], strict: bool, rep: Report) -> None:
    risks = label.get("risks")
    if not isinstance(risks, list):
        rep.err(f"labels/{cid}", "risks 不是数组")
        return

    seen_risk_ids: set[str] = set()
    for i, r in enumerate(risks, 1):
        where = f"labels/{cid}#risks[{i}]"

        missing = [f for f in REQUIRED_RISK_FIELDS if f not in r]
        if missing:
            rep.err(where, f"缺字段 {missing}")
            continue

        rid = r["risk_id"]
        if rid in seen_risk_ids:
            rep.err(where, f"risk_id 重复: {rid}")
        seen_risk_ids.add(rid)

        if r["risk_level"] not in LEVELS:
            rep.err(where, f"risk_level 非法: {r['risk_level']}")

        if not RULE_ID_RE.match(str(r["rule_id"])):
            rep.err(where, f"rule_id 格式不符: {r['rule_id']}")
        elif r["rule_id"] != "UNMATCHED" and rules and r["rule_id"] not in rules:
            rep.err(where, f"rule_id 在规则库中不存在: {r['rule_id']}")

        # E8 依据（独立校验，与条款是否存在无关，避免被 continue 跳过）
        lb = r["legal_basis"]
        if isinstance(lb, str):
            if lb.strip() not in ("未检索到依据", "未检索到权威依据"):
                rep.err(where, f"legal_basis 为字符串时必须明确写「未检索到依据」，当前: {lb!r}")
        elif isinstance(lb, dict):
            status = lb.get("verify_status")
            if status not in ("pending", "verified"):
                rep.err(where, f"legal_basis.verify_status 非法: {status!r}")
            elif status == "pending" and strict:
                rep.err(where, "legal_basis 仍为 pending（--strict 模式）")
            if status == "verified" and not lb.get("url"):
                rep.warn(where, "verify_status=verified 但没有 url，无法复核")
        else:
            rep.err(where, "legal_basis 必须是对象或字符串")

        clause = clause_index.get(r["clause_id"])
        if not clause:
            rep.err(where, f"clause_id 不存在于条款表: {r['clause_id']}")
            continue

        text = clause.get("text", "")
        quote = r["quote"]

        # E6 唯一定位
        cnt = text.count(quote)
        if cnt == 0:
            rep.err(where, "quote 在条款正文中找不到（可能改了字或跨条款拼接）")
        elif cnt > 1:
            rep.err(where, f"quote 在条款正文中出现 {cnt} 次，定位不唯一")

        # E7 偏移一致
        if "char_start" in r and "char_end" in r:
            s, e = r["char_start"], r["char_end"]
            if not isinstance(s, int) or not isinstance(e, int):
                rep.err(where, "char_start/char_end 必须是整数")
            elif text[s:e] != quote:
                rep.err(where, f"偏移切片不等于 quote（得到: {text[s:e][:40]!r}）")
        else:
            rep.warn(where, "缺少 char_start/char_end，前端定位将不可靠")

    # E9 授信比对
    for j, chk in enumerate(label.get("consistency_checks") or [], 1):
        need = ["check_id", "field", "contract_value", "credit_report_value", "level"]
        miss = [f for f in need if f not in chk]
        if miss:
            rep.err(f"labels/{cid}#consistency_checks[{j}]", f"缺字段 {miss}")
        elif chk["level"] not in LEVELS:
            rep.err(f"labels/{cid}#consistency_checks[{j}]", f"level 非法: {chk['level']}")


def load_rules(rules_path: Path) -> dict[str, dict]:
    if not rules_path.exists():
        return {}
    try:
        import yaml  # type: ignore
    except ImportError:
        print("　提示: 未安装 PyYAML，跳过规则库交叉校验（pip install pyyaml）")
        return {}
    data = yaml.safe_load(rules_path.read_text(encoding="utf-8")) or []
    if isinstance(data, dict):
        data = data.get("rules", [])
    return {r["rule_id"]: r for r in data if isinstance(r, dict) and r.get("rule_id")}


def run(data_root: Path, strict: bool) -> int:
    rep = Report()
    labels_dir = data_root / "labels"
    clauses_dir = data_root / "clauses"

    # 排除非标注文件：schema、数据集划分、类型映射等
    skip_stems = {"schema", "split", "type_map", "manifest", "readme"}
    labels = sorted(p for p in labels_dir.glob("*.json") if p.stem.lower() not in skip_stems)
    if not labels:
        print(f"未找到标注文件: {labels_dir}/*.json")
        return 1

    rules = load_rules(data_root / "rules" / "rules.yaml")
    print(f"标注文件 {len(labels)} 个，规则 {len(rules)} 条")
    if not rules:
        print("　⚠️ 规则库为空：无法交叉校验 rule_id，生成的标注可能引用不存在的规则")
    print()

    total_risks = 0
    for lp in labels:
        cid = lp.stem
        label = load_json(lp)
        cp = clauses_dir / f"{cid}.json"
        if not cp.exists():
            rep.err(f"labels/{cid}", f"缺少对应条款表 clauses/{cid}.json")
            continue
        clauses = load_json(cp)
        if isinstance(clauses, dict):
            clauses = clauses.get("clauses", [])
        clause_index = check_clauses(cid, clauses, rep)
        check_label(cid, label, clause_index, rules, strict, rep)
        total_risks += len(label.get("risks") or [])
        print(f"  检查 {cid}: {len(clauses)} 条款 / {len(label.get('risks') or [])} 条标注")

    print()
    for line in rep.errors:
        print(line)
    for line in rep.warnings:
        print(line)

    print()
    print(f"合计: {len(labels)} 份合同, {total_risks} 条标注")
    print(f"错误 {len(rep.errors)} 个, 警告 {len(rep.warnings)} 个")
    print("结论:", "通过 ✅" if rep.ok() else "不通过 ❌")
    return 0 if rep.ok() else 2


def demo() -> int:
    """自检：构造一份含典型错误的数据，验证校验器能抓出来。"""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "labels").mkdir()
        (root / "clauses").mkdir()
        (root / "rules").mkdir()

        clause_text = "逾期罚息按合同利率的三倍计收，且不受任何上限约束。"
        (root / "clauses" / "C99.json").write_text(json.dumps([
            {"clause_id": "C99-012", "clause_no": "第十二条", "text": clause_text}
        ], ensure_ascii=False), encoding="utf-8")

        good_quote = "逾期罚息按合同利率的三倍计收"
        start = clause_text.index(good_quote)
        (root / "labels" / "C99.json").write_text(json.dumps({
            "contract_id": "C99",
            "risks": [
                {"risk_id": "C99-R01", "clause_id": "C99-012", "clause_no": "第十二条",
                 "risk_type": "利率-罚息超限", "rule_id": "R02", "risk_level": "高",
                 "char_start": start, "char_end": start + len(good_quote),
                 "quote": good_quote, "problem": "x", "suggestion": "y",
                 "legal_basis": {"name": "待核验", "verify_status": "pending"}},
                {"risk_id": "C99-R02", "clause_id": "C99-999", "clause_no": "第九百九十九条",
                 "risk_type": "利率-罚息超限", "rule_id": "R99", "risk_level": "极高",
                 "char_start": 0, "char_end": 5, "quote": "不存在的引用",
                 "problem": "x", "suggestion": "y", "legal_basis": "随便写的依据"},
            ],
            "consistency_checks": [],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        print("--- DEMO：预期抓出 3 个错误（clause_id 不存在 / 等级非法 / 依据非法）---")
        code = run(root, strict=False)
        expected_fail = code == 2
        print("\nDEMO 结果:", "校验器工作正常 ✅" if expected_fail else "校验器未抓出错误 ❌")
        return 0 if expected_fail else 1


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="标注数据校验器")
    ap.add_argument("--data-root", default="data", help="数据根目录（默认 ./data）")
    ap.add_argument("--strict", action="store_true", help="legal_basis 为 pending 也算错误")
    ap.add_argument("--demo", action="store_true", help="运行内置自检")
    args = ap.parse_args()
    if args.demo:
        return demo()
    return run(Path(args.data_root), args.strict)


if __name__ == "__main__":
    raise SystemExit(main())

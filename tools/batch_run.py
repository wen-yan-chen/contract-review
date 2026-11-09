"""批量跑分：对全部合同调用智能体，落盘 predictions/{cid}.json。

用法：
  python batch_run.py                # 全部 20 份
  python batch_run.py --only dev     # 只跑 dev
  python batch_run.py --resume       # 跳过已有结果
  python batch_run.py --ids C13,C17
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, r"D:\contest-32\api")
from nexent_client import NexentClient, NexentError  # noqa: E402

DATA = Path(r"D:\contest-32\data")
AGENT = "contract_review"


def load_clauses(cid: str) -> list[dict]:
    data = json.loads((DATA / "clauses" / f"{cid}.json").read_text(encoding="utf-8"))
    return data["clauses"] if isinstance(data, dict) else data


def extract_json(ans: str) -> dict | None:
    """从模型输出中提取最后一个完整的 JSON 对象。

    模型可能输出多段（多步骤、工具调用中间结果），因此从后往前找
    第一个能解析的平衡括号片段。
    """
    s = re.sub(r"^\s*```(?:json)?\s*", "", ans.strip())
    s = re.sub(r"\s*```\s*$", "", s)

    starts = [i for i, ch in enumerate(s) if ch == "{"]
    for start in reversed(starts[-40:]):
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(s)):
            ch = s[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    cand = s[start:i + 1]
                    for attempt in (cand, re.sub(r",\s*([}\]])", r"\1", cand)):
                        try:
                            obj = json.loads(attempt)
                            if isinstance(obj, dict) and "risks" in obj:
                                return obj
                        except json.JSONDecodeError:
                            continue
                    break
    return None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default=None)
    ap.add_argument("--only", choices=["dev", "holdout", "clean", "all"], default="all")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    split = json.loads((DATA / "labels" / "split.json").read_text(encoding="utf-8"))
    if args.ids:
        ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    elif args.only == "all":
        ids = split["dev"] + split["holdout"]
    elif args.only == "clean":
        ids = split["clean"]
    else:
        ids = split[args.only]
    ids = sorted(dict.fromkeys(ids))

    out_dir = DATA / "predictions"
    out_dir.mkdir(parents=True, exist_ok=True)
    client = NexentClient()

    total = len(ids)
    print(f"待跑 {total} 份: {ids}", flush=True)

    ok, failed = 0, []
    t_all = time.time()

    for i, cid in enumerate(ids, 1):
        dst = out_dir / f"{cid}.json"
        if args.resume and dst.exists():
            print(f"[{i}/{total}] {cid} 已存在，跳过", flush=True)
            ok += 1
            continue

        clauses = load_clauses(cid)

        def render(c: dict) -> str:
            t = c["text"].strip()
            no = c["clause_no"]
            # 条款正文往往已包含编号，避免出现「第十二条　第十二条　…」
            if t.startswith(no):
                t = t[len(no):].lstrip("　 \t")
            return f"{no}　{t}"

        body = "\n".join(render(c) for c in clauses)
        query = ("请对照知识库中的 40 条规则，逐条审查下面的贷款合同，"
                 "按约定的 JSON 格式输出全部风险。\n\n" + body)

        t0 = time.time()
        parsed = None
        last_err = ""
        for attempt in range(1, 4):
            try:
                out = client.chat_sync(AGENT, query)
            except NexentError as e:
                last_err = f"{type(e).__name__}: {e}"
                time.sleep(3 * attempt)
                continue
            if not (out.get("answer") or "").strip():
                last_err = "空回答"
                time.sleep(3 * attempt)
                continue
            parsed = extract_json(out["answer"])
            if parsed is not None:
                break
            last_err = "JSON 解析失败"
            (out_dir / f"{cid}.raw.txt").write_text(out["answer"], encoding="utf-8")
            time.sleep(3 * attempt)

        dt = time.time() - t0
        if parsed is None:
            print(f"[{i}/{total}] {cid} 重试 3 次仍失败（{last_err}），耗时 {dt:.0f}s", flush=True)
            failed.append(cid)
            continue

        parsed.setdefault("risks", [])
        dst.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        n = len(parsed.get("risks") or [])
        print(f"[{i}/{total}] {cid} OK  风险 {n} 条  耗时 {dt:.0f}s", flush=True)
        ok += 1
        time.sleep(1.5)

    dur = time.time() - t_all
    print()
    print(f"完成: 成功 {ok}/{total}，失败 {failed or '无'}")
    print(f"总耗时 {dur/60:.1f} 分钟，平均 {dur/max(ok,1):.0f}s/份")
    return 0 if not failed else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)

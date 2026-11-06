"""合同审查后端：上传解析 + 调用智能体 + 结果落盘。

启动：
  python api\\server.py            # http://127.0.0.1:8000/web/
  uvicorn api.server:app --port 8000

接口：
  GET  /api/contracts            列出全部合同（样例 + 已上传）
  GET  /api/contracts/{cid}      取条款与审查结果
  POST /api/upload               上传 docx/pdf/txt → 解析切分 → 返回合同 id
  POST /api/review/{cid}         调用 Nexent 智能体审查 → 落盘 → 返回结果
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CLAUSES = DATA / "clauses"
PREDICTIONS = DATA / "predictions"
META = DATA / "meta"

sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT))
from nexent_client import NexentClient, NexentError  # noqa: E402
from tools.gate import apply_gates  # noqa: E402

AGENT = "contract_review"
MAX_BYTES = 20 * 1024 * 1024

app = FastAPI(title="贷款合同审查", version="1.0.0")

# ---------------------------------------------------------------- 解析

CLAUSE_RE = re.compile(r"第[一二三四五六七八九十百零〇两]+条")
PAGE_NOISE = re.compile(r"^\s*(?:第\s*\d+\s*页(?:\s*共\s*\d+\s*页)?|-?\s*\d+\s*-?)\s*$")


def extract_text(filename: str, blob: bytes) -> str:
    """按扩展名抽取纯文本。"""
    suffix = Path(filename).suffix.lower()

    if suffix in (".txt", ".md"):
        for enc in ("utf-8", "gb18030", "utf-16"):
            try:
                return blob.decode(enc)
            except UnicodeDecodeError:
                continue
        raise HTTPException(400, "文本编码无法识别，请另存为 UTF-8")

    if suffix == ".docx":
        from docx import Document

        doc = Document(io.BytesIO(blob))
        parts = [p.text for p in doc.paragraphs]
        # 表格内容也纳入（担保清单、还款计划常以表格出现）
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append("　".join(cells))
        return "\n".join(parts)

    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(blob))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")
        text = "\n".join(pages)
        if len(text.strip()) < 50:
            raise HTTPException(
                400,
                "该 PDF 未提取到文字层（可能是扫描件）。请上传 docx，或先做 OCR。",
            )
        return text

    raise HTTPException(400, f"不支持的文件类型：{suffix}（仅支持 docx / pdf / txt / md）")


def split_clauses(text: str) -> list[dict]:
    """按「第X条」切分条款；编号前的段落归入前言。"""
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    lines = [ln for ln in lines if ln and not PAGE_NOISE.match(ln)]
    joined = "\n".join(lines)

    matches = list(CLAUSE_RE.finditer(joined))
    if not matches:
        # 无条款编号：退化为按空行分段
        paras = [p.strip() for p in re.split(r"\n{2,}", joined) if p.strip()]
        return [
            {"clause_id": f"X-{i:03d}", "clause_no": f"第{i}段", "text": p}
            for i, p in enumerate(paras, 1)
        ]

    clauses: list[dict] = []
    preamble = joined[: matches[0].start()].strip()
    if preamble:
        clauses.append({"clause_id": "X-000", "clause_no": "前言", "text": preamble})

    for idx, m in enumerate(matches, 1):
        end = matches[idx].start() if idx < len(matches) else len(joined)
        body = joined[m.start(): end].strip()
        clauses.append({
            "clause_id": f"X-{idx:03d}",
            "clause_no": m.group(0),
            "text": body,
        })
    return clauses


# ---------------------------------------------------------------- 智能体

def contract_text(clauses: list[dict]) -> str:
    out = []
    for c in clauses:
        body = c["text"].strip()
        no = c["clause_no"]
        if body.startswith(no):
            body = body[len(no):].lstrip("　 \t")
        out.append(f"{no}　{body}")
    return "\n".join(out)


def extract_json(ans: str) -> dict | None:
    s = re.sub(r"^\s*```(?:json)?\s*", "", (ans or "").strip())
    s = re.sub(r"\s*```\s*$", "", s)
    starts = [i for i, ch in enumerate(s) if ch == "{"]
    for start in reversed(starts[-40:]):
        depth, in_str, esc = 0, False, False
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
                    cand = s[start: i + 1]
                    for attempt in (cand, re.sub(r",\s*([}\]])", r"\1", cand)):
                        try:
                            obj = json.loads(attempt)
                            if isinstance(obj, dict) and "risks" in obj:
                                return obj
                        except json.JSONDecodeError:
                            pass
                    break
    return None


# ---------------------------------------------------------------- 接口

def _meta_path(cid: str) -> Path:
    return META / f"{cid}.json"


def load_meta(cid: str) -> dict:
    p = _meta_path(cid)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def save_meta(cid: str, meta: dict) -> None:
    META.mkdir(parents=True, exist_ok=True)
    _meta_path(cid).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def display_name(cid: str) -> str:
    meta = load_meta(cid)
    if meta.get("name"):
        return meta["name"]
    # 样例合同：从 samples 里的文件名推断
    for f in (DATA / "samples").glob(f"{cid}*.docx"):
        return f.stem
    return cid


def _count(cid: str) -> tuple[int, int]:
    clauses = pred = 0
    cp = CLAUSES / f"{cid}.json"
    if cp.exists():
        data = json.loads(cp.read_text(encoding="utf-8"))
        clauses = len(data if isinstance(data, list) else data.get("clauses", []))
    pp = PREDICTIONS / f"{cid}.json"
    if pp.exists():
        data = json.loads(pp.read_text(encoding="utf-8"))
        pred = len(data.get("risks") or [])
    return clauses, pred


@app.get("/api/contracts")
def list_contracts():
    items = []
    for cp in sorted(CLAUSES.glob("*.json")):
        cid = cp.stem
        clauses, risks = _count(cid)
        items.append({
            "cid": cid,
            "name": display_name(cid),
            "clauses": clauses,
            "risks": risks,
            "updated": int(cp.stat().st_mtime),
            "uploaded": cid.startswith("U-"),
        })
    items.sort(key=lambda x: x["updated"], reverse=True)
    return {"contracts": items}


@app.patch("/api/contracts/{cid}")
def rename_contract(cid: str, payload: dict):
    if not (CLAUSES / f"{cid}.json").exists():
        raise HTTPException(404, f"合同不存在：{cid}")
    name = (payload or {}).get("name", "").strip()
    if not name:
        raise HTTPException(400, "名称不能为空")
    if len(name) > 80:
        raise HTTPException(400, "名称过长（最多 80 字）")
    meta = load_meta(cid)
    meta["name"] = name
    save_meta(cid, meta)
    return {"cid": cid, "name": name}


@app.delete("/api/contracts/{cid}")
def delete_contract(cid: str):
    cp = CLAUSES / f"{cid}.json"
    if not cp.exists():
        raise HTTPException(404, f"合同不存在：{cid}")
    cp.unlink(missing_ok=True)
    (PREDICTIONS / f"{cid}.json").unlink(missing_ok=True)
    _meta_path(cid).unlink(missing_ok=True)
    updir = DATA / "uploads" / cid
    if updir.exists():
        for f in updir.glob("*"):
            f.unlink(missing_ok=True)
        updir.rmdir()
    return {"deleted": cid}


@app.get("/api/contracts/{cid}/export")
def export_contract(cid: str, format: str = "docx"):
    cp = CLAUSES / f"{cid}.json"
    if not cp.exists():
        raise HTTPException(404, f"合同不存在：{cid}")

    clauses = json.loads(cp.read_text(encoding="utf-8"))
    if isinstance(clauses, dict):
        clauses = clauses.get("clauses", [])
    pp = PREDICTIONS / f"{cid}.json"
    pred = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else {}

    from urllib.parse import quote

    name = display_name(cid)
    from report import build_docx, build_markdown  # noqa: E402

    if format == "md":
        text = build_markdown(cid, name, clauses, pred)
        from fastapi.responses import Response
        fname = quote(f"{name}_审查报告.md")
        return Response(
            content=text.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fname}"},
        )

    blob = build_docx(cid, name, clauses, pred)
    from fastapi.responses import Response
    fname = quote(f"{name}_审查报告.docx")
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fname}"},
    )


@app.get("/api/contracts/{cid}")
def get_contract(cid: str):
    cp = CLAUSES / f"{cid}.json"
    if not cp.exists():
        raise HTTPException(404, f"合同不存在：{cid}")
    clauses = json.loads(cp.read_text(encoding="utf-8"))
    if isinstance(clauses, dict):
        clauses = clauses.get("clauses", [])
    pp = PREDICTIONS / f"{cid}.json"
    pred = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else None
    return {"cid": cid, "clauses": clauses, "prediction": pred}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    blob = await file.read()
    if not blob:
        raise HTTPException(400, "文件为空")
    if len(blob) > MAX_BYTES:
        raise HTTPException(400, "文件超过 20MB 限制")

    text = extract_text(file.filename or "upload.docx", blob)
    clauses = split_clauses(text)
    if len(clauses) < 3:
        raise HTTPException(400, "未能识别出条款结构，请确认文件内容")

    digest = hashlib.sha1(blob).hexdigest()[:8]
    cid = f"U-{digest}"
    (CLAUSES / f"{cid}.json").write_text(
        json.dumps(clauses, ensure_ascii=False, indent=2), encoding="utf-8")

    # 保留原始文件，便于复现
    up = DATA / "uploads" / cid
    up.mkdir(parents=True, exist_ok=True)
    (up / (file.filename or "source")).write_bytes(blob)

    return {"cid": cid, "filename": file.filename, "clauses": len(clauses),
            "chars": len(text)}


@app.post("/api/review/{cid}")
def review(cid: str):
    cp = CLAUSES / f"{cid}.json"
    if not cp.exists():
        raise HTTPException(404, f"合同不存在：{cid}")

    clauses = json.loads(cp.read_text(encoding="utf-8"))
    if isinstance(clauses, dict):
        clauses = clauses.get("clauses", [])

    query = ("请对照知识库中的 40 条规则，逐条审查下面的贷款合同，"
             "按约定的 JSON 格式输出全部风险。\n\n" + contract_text(clauses) +
             "\n\n【合同要素】\n" + json.dumps({"clauses": len(clauses)}, ensure_ascii=False))

    t0 = time.time()
    try:
        client = NexentClient()
        out = client.chat_sync(AGENT, query)
    except NexentError as e:
        raise HTTPException(502, f"智能体调用失败：{type(e).__name__} {e}")

    obj = extract_json(out["answer"])
    if obj is None:
        snippet = (out["answer"] or "")[:300]
        raise HTTPException(502, f"智能体未返回有效 JSON。片段：{snippet}")

    obj.setdefault("risks", [])
    obj.setdefault("consistency_checks", [])

    # 落盘前过一次确定性闸门：技能负责"过程可见"，这一步负责"结果确定"
    obj, gate_log = apply_gates(obj, clauses)

    obj["_meta"] = {
        "elapsed_seconds": round(time.time() - t0, 1),
        "steps": out.get("steps", 0),
        "events": out.get("events", 0),
        "clauses": len(clauses),
    }
    if gate_log:
        obj["_meta"]["gate"] = gate_log
    (PREDICTIONS / f"{cid}.json").write_text(
        json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return obj


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.mount("/web", StaticFiles(directory=str(ROOT / "web"), html=True), name="web")
app.mount("/data", StaticFiles(directory=str(DATA)), name="data")


@app.get("/")
def index():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/web/")


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(f"服务启动: http://{host}:{port}/web/")
    uvicorn.run(app, host=host, port=port, log_level="warning")

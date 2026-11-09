"""字体收口：中文用黑体，西文与数字用 Arial。

黑体的数字与标点自带较宽字距（如 2.6% 会排成 2. 6%），
中英混排时把拉丁字形换成 Arial 更整齐；中文仍为黑体。
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.oxml.ns import qn

SRC = Path(r"D:\contest-32\docs\deck.pptx")
LATIN, EA = "Arial", "黑体"


def walk(shapes):
    for sh in shapes:
        if sh.shape_type == 6 and hasattr(sh, "shapes"):
            yield from walk(sh.shapes)
            continue
        yield sh


def iter_runs(slide):
    for sh in walk(slide.shapes):
        if sh.has_text_frame:
            for p in sh.text_frame.paragraphs:
                for r in p.runs:
                    yield r
        if getattr(sh, "has_table", False) and sh.has_table:
            for row in sh.table.rows:
                for cell in row.cells:
                    for p in cell.text_frame.paragraphs:
                        for r in p.runs:
                            yield r


def apply(run) -> None:
    rPr = run._r.get_or_add_rPr()
    rPr.get_or_add_latin().set("typeface", LATIN)

    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = etree.SubElement(rPr, qn("a:ea"))
    ea.set("typeface", EA)

    cs = rPr.find(qn("a:cs"))
    if cs is None:
        etree.SubElement(rPr, qn("a:cs")).set("typeface", LATIN)


def main() -> None:
    prs = Presentation(str(SRC))
    n = 0
    for s in prs.slides:
        for r in iter_runs(s):
            apply(r)
            n += 1
    prs.save(str(SRC))
    print(f"已设置 {n} 个 run：西文 {LATIN} / 中文 {EA}")


if __name__ == "__main__":
    main()

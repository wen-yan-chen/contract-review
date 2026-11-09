"""统一放大字号：正文 +2pt 左右，标题按比例提升。

不改版面坐标，只改字号；放大后逐页渲染检查溢出。
"""

from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation
from pptx.util import Pt

SRC = Path(r"D:\contest-32\docs\deck.pptx")


def scale_size(pt: float) -> float:
    """按原字号分档放大：小字多放，大字少放，避免溢出。"""
    if pt <= 9:
        return pt + 2.0
    if pt <= 11:
        return pt + 1.8
    if pt <= 14:
        return pt + 1.5
    if pt <= 20:
        return pt + 2.0
    if pt <= 30:
        return round(pt * 1.12)
    if pt <= 46:
        return round(pt * 1.08)
    return pt


def walk(shapes):
    for sh in shapes:
        if sh.shape_type == 6 and hasattr(sh, "shapes"):
            yield from walk(sh.shapes)
            continue
        yield sh


def bump(slide) -> int:
    n = 0
    for sh in walk(slide.shapes):
        if sh.has_text_frame:
            for p in sh.text_frame.paragraphs:
                for r in p.runs:
                    if r.font.size:
                        old = r.font.size.pt
                        new = scale_size(old)
                        if new != old:
                            r.font.size = Pt(new)
                            n += 1
        if getattr(sh, "has_table", False) and sh.has_table:
            for row in sh.table.rows:
                for cell in row.cells:
                    for p in cell.text_frame.paragraphs:
                        for r in p.runs:
                            if r.font.size:
                                old = r.font.size.pt
                                new = scale_size(old)
                                if new != old:
                                    r.font.size = Pt(new)
                                    n += 1
    return n


def main() -> None:
    prs = Presentation(str(SRC))
    total = 0
    for i, s in enumerate(prs.slides, 1):
        k = bump(s)
        total += k
        if k:
            print(f"  第{i:02d}页 调整 {k} 处")
    prs.save(str(SRC))
    print(f"共调整 {total} 处字号 → {SRC}")


if __name__ == "__main__":
    main()

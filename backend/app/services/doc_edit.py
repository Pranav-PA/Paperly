"""
In-place editing of uploaded Word and PDF files: like editing the real document, not re-creating it.

The AI sees the document as numbered blocks (paragraphs for Word, text lines for PDF) and returns small
operations (replace / insert / delete / formatting). Everything it doesn't touch stays byte-for-byte the same.
"""
import copy
import html
import io
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.text.paragraph import Paragraph

from app.services.fonts import _font_files

try:  # PyMuPDF: `pkg install python-pymupdf` on Termux, `pip install pymupdf` elsewhere.
    import pymupdf
except ImportError:  # pragma: no cover - depends on the device
    pymupdf = None


class DocEditError(Exception):
    """A requested operation couldn't be applied; the message is safe to show."""


@dataclass
class Block:
    id: str
    text: str
    bold: bool = False
    align: str = "left"
    size: Optional[float] = None
    in_table: bool = False
    page: Optional[int] = None


@dataclass
class Change:
    target: str
    before: str
    after: str


@dataclass
class EditOutcome:
    data: bytes
    changes: List[Change] = field(default_factory=list)


def pdf_supported() -> bool:
    return pymupdf is not None


def _label_split(text: str) -> Tuple[str, str]:
    """'Q10. What is…' -> ('Q10.', ' What is…'); returns ('', text) when there's no question label."""
    m = re.match(r"^\s*((?:Q\.?\s*)?\(?\d+[a-z]?[.)]?)(\s.*)?$", text, re.S | re.I)
    if m and m.group(2) is not None:
        return m.group(1), m.group(2)
    return "", text


# =====================================================================
# Word (.docx)
# =====================================================================
def _docx_paragraphs(doc) -> List[Tuple[str, Paragraph, bool]]:
    """All paragraphs in reading order with stable ids: H* header, B* body (incl. tables), F* footer."""
    out: List[Tuple[str, Paragraph, bool]] = []
    section = doc.sections[0]
    for i, p in enumerate(section.header.paragraphs, 1):
        out.append((f"H{i}", p, False))

    n = 0
    seen_cells = set()
    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            n += 1
            out.append((f"B{n}", Paragraph(child, doc._body), False))
        elif child.tag == qn("w:tbl"):
            for tc in child.iter(qn("w:tc")):
                if id(tc) in seen_cells:
                    continue
                seen_cells.add(id(tc))
                for p_el in tc.iterchildren(qn("w:p")):
                    n += 1
                    out.append((f"B{n}", Paragraph(p_el, doc._body), True))

    for i, p in enumerate(section.footer.paragraphs, 1):
        out.append((f"F{i}", p, False))
    return out


def _runs_text(p: Paragraph) -> str:
    return "".join(r.text for r in p.runs)


def docx_blocks(data: bytes) -> List[Block]:
    doc = Document(io.BytesIO(data))
    blocks = []
    for bid, p, in_table in _docx_paragraphs(doc):
        text = _runs_text(p)
        runs = [r for r in p.runs if r.text.strip()]
        sizes = [r.font.size.pt for r in runs if r.font.size]
        align = {1: "center", 2: "right", 3: "justify"}.get(int(p.alignment) if p.alignment is not None else 0, "left")
        blocks.append(Block(
            id=bid, text=text, in_table=in_table, align=align,
            bold=bool(runs) and all(r.bold for r in runs),
            size=max(sizes) if sizes else None,
        ))
    return blocks


def _replace_runs_text(p: Paragraph, new_text: str) -> None:
    """Change the paragraph text while keeping each run's formatting: only the differing middle is rewritten."""
    runs = list(p.runs)
    if not runs:
        p.add_run(new_text)
        return
    old = "".join(r.text for r in runs)
    if old == new_text:
        return
    pre = 0
    while pre < min(len(old), len(new_text)) and old[pre] == new_text[pre]:
        pre += 1
    suf = 0
    while suf < min(len(old), len(new_text)) - pre and old[-1 - suf] == new_text[-1 - suf]:
        suf += 1
    start, end = pre, len(old) - suf
    middle = new_text[pre:len(new_text) - suf]

    pos, target = 0, len(runs) - 1
    spans = []
    for i, r in enumerate(runs):
        spans.append((pos, pos + len(r.text)))
        if pos <= start < pos + len(r.text) and target == len(runs) - 1:
            target = i
        pos += len(r.text)
    for i, r in enumerate(runs):
        rs, _ = spans[i]
        t = r.text
        left = t[:max(0, min(len(t), start - rs))]
        right = t[max(0, min(len(t), end - rs)):]
        r.text = left + (middle if i == target else "") + right


def _set_text_like(p: Paragraph, text: str) -> None:
    """Fill a copied paragraph with new text, reusing its label run (e.g. bold 'Q10.') and main text run."""
    runs = [r for r in p.runs]
    if not runs:
        p.add_run(text)
        return
    label, rest = _label_split(text)
    label_run = runs[0] if len(runs) >= 2 and re.fullmatch(r"\s*(?:Q\.?\s*)?\(?\d+[a-z]?[.)]?\s*", runs[0].text, re.I) else None
    # A trailing marks run like "[2 Marks]" / "(3)" keeps its own formatting too.
    marks_pattern = r"\s*[\[(]\s*\d+(?:\.\d+)?\s*(?:marks?|m)?\s*[\])]\s*$"
    marks_run = runs[-1] if len(runs) >= 2 and runs[-1] is not label_run and re.fullmatch(marks_pattern, runs[-1].text, re.I) else None
    new_marks = re.search(marks_pattern, text, re.I) if marks_run is not None else None
    body_run = max((r for r in runs if r is not label_run and r is not marks_run), key=lambda r: len(r.text), default=runs[0])
    for r in runs:
        if r not in (label_run, body_run, marks_run):
            r._r.getparent().remove(r._r)
    body = rest if (label_run is not None and label) else text
    if new_marks:
        marks_run.text = new_marks.group(0)
        body = body[:len(body) - len(new_marks.group(0))] if body.endswith(new_marks.group(0)) else body
    elif marks_run is not None:
        marks_run._r.getparent().remove(marks_run._r)
    if label_run is not None and label:
        label_run.text = label
    elif label_run is not None:
        label_run._r.getparent().remove(label_run._r)
    body_run.text = body


def apply_docx_ops(data: bytes, ops: list) -> EditOutcome:
    doc = Document(io.BytesIO(data))
    index = {bid: (p, in_table) for bid, p, in_table in _docx_paragraphs(doc)}
    order = [bid for bid, _, _ in _docx_paragraphs(doc)]
    changes: List[Change] = []

    def get(bid: Optional[str]) -> Paragraph:
        if not bid or bid not in index:
            raise DocEditError(f"Couldn't find block {bid} in the document.")
        return index[bid][0]

    def span(start: str, end: Optional[str]) -> List[str]:
        if not end or end == start:
            return [start]
        i, j = order.index(start), order.index(end) if end in order else order.index(start)
        return order[min(i, j):max(i, j) + 1]

    for op in ops:
        kind = op.op
        if kind == "replace":
            ids = span(op.target, op.end_target)
            first = get(ids[0])
            before = "\n".join(_runs_text(get(b)) for b in ids)
            parts = (op.text or "").split("\n\n")
            _replace_runs_text(first, parts[0])
            for extra in ids[1:]:
                el = get(extra)._p
                el.getparent().remove(el)
            anchor = first
            for part in parts[1:]:
                new_p = copy.deepcopy(first._p)
                anchor._p.addnext(new_p)
                anchor = Paragraph(new_p, first._parent)
                _set_text_like(anchor, part)
            changes.append(Change(ids[0], before, op.text or ""))
        elif kind == "insert_after":
            anchor = get(op.target)
            template = anchor
            # When inserting after a blank line, copy the nearest paragraph with text as the style template.
            if not _runs_text(anchor).strip():
                pos = order.index(op.target)
                for bid in reversed(order[:pos]):
                    if _runs_text(get(bid)).strip():
                        template = get(bid)
                        break
            for part in (op.text or "").split("\n\n"):
                new_p = copy.deepcopy(template._p)
                anchor._p.addnext(new_p)
                anchor = Paragraph(new_p, template._parent)
                _set_text_like(anchor, part)
            changes.append(Change(op.target, "", op.text or ""))
        elif kind == "delete":
            ids = span(op.target, op.end_target)
            before = "\n".join(_runs_text(get(b)) for b in ids)
            for b in ids:
                el = get(b)._p
                if el.getparent() is not None:
                    el.getparent().remove(el)
            changes.append(Change(ids[0], before, ""))
        elif kind == "set_columns":
            n = max(1, min(3, int(op.value or 1)))
            for section in doc.sections:
                sect = section._sectPr
                cols = sect.find(qn("w:cols"))
                if cols is None:
                    cols = OxmlElement("w:cols")
                    sect.append(cols)
                cols.set(qn("w:num"), str(n))
                cols.set(qn("w:space"), "425")
            changes.append(Change("layout", "", f"{n} column(s)"))
        elif kind == "set_font":
            family, size = _parse_font(op.value)
            normal = doc.styles["Normal"]
            base = normal.font.size.pt if normal.font.size else 11.0
            factor = (size / base) if size else None
            if family:
                normal.font.name = family
            if size:
                normal.font.size = Pt(size)
            for _, p, _ in _docx_paragraphs(doc):
                for r in p.runs:
                    if family:
                        r.font.name = family
                        rpr = r._r.get_or_add_rPr()
                        rpr.get_or_add_rFonts().set(qn("w:eastAsia"), family)
                    if factor and r.font.size:
                        r.font.size = Pt(round(r.font.size.pt * factor * 2) / 2)
            changes.append(Change("layout", "", f"font {family or ''} {f'{size:g} pt' if size else ''}".strip()))
        else:
            raise DocEditError(f"Unsupported change '{kind}' for Word documents.")

    buffer = io.BytesIO()
    doc.save(buffer)
    return EditOutcome(buffer.getvalue(), changes)


def _parse_font(value: Optional[str]) -> Tuple[Optional[str], Optional[float]]:
    """'Times New Roman, 12' / 'serif' / '12' -> (family, size)."""
    if not value:
        return None, None
    family, size = None, None
    for part in [v.strip() for v in value.split(",")]:
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(pt)?", part, re.I)
        if m:
            size = max(6.0, min(28.0, float(m.group(1))))
        elif part:
            family = {"serif": "Times New Roman", "sans": "Arial", "sans-serif": "Arial"}.get(part.lower(), part)
    return family, size


# =====================================================================
# PDF
# =====================================================================
@dataclass
class _PdfLine:
    id: str
    page: int
    rect: tuple
    text: str
    size: float
    bold: bool
    serif: bool
    color: int
    spans: list


def _pdf_lines(doc) -> List[_PdfLine]:
    """Editable units of a PDF: one per paragraph (PyMuPDF text block), so a multi-line question is a single unit.
    Very long blocks (badly structured PDFs) are split into lines so one edit can't wipe half a page."""
    units: List[_PdfLine] = []
    for pno, page in enumerate(doc):
        n = 0
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            lines = [l for l in block["lines"] if any(s["text"].strip() for s in l["spans"])]
            if not lines:
                continue
            groups = [lines] if len(lines) <= 6 else [[l] for l in lines]
            for group in groups:
                n += 1
                spans = [s for l in group for s in l["spans"] if s["text"].strip()]
                main = max(spans, key=lambda s: len(s["text"]))
                parts = []
                for l in group:
                    text, prev_x1 = "", None
                    for sp in l["spans"]:
                        if prev_x1 is not None and sp["bbox"][0] - prev_x1 > sp["size"] * 2 and not text.endswith(" "):
                            text += "    "  # visible gap, e.g. before right-aligned marks
                        text += sp["text"]
                        prev_x1 = sp["bbox"][2]
                    parts.append(text.strip())
                x0 = min(l["bbox"][0] for l in group)
                y0 = min(l["bbox"][1] for l in group)
                x1 = max(l["bbox"][2] for l in group)
                y1 = max(l["bbox"][3] for l in group)
                units.append(_PdfLine(
                    id=f"p{pno + 1}.{n}", page=pno, rect=(x0, y0, x1, y1), text=" ".join(parts),
                    size=main["size"], bold=bool(main["flags"] & 16) or "bold" in main["font"].lower(),
                    serif=bool(main["flags"] & 4) or any(k in main["font"].lower() for k in ("times", "serif", "roman")),
                    color=main["color"], spans=[l["bbox"] for l in group],
                ))
    return units


def pdf_blocks(data: bytes) -> List[Block]:
    if pymupdf is None:
        raise DocEditError("PDF editing isn't installed on the server (Termux: pkg install python-pymupdf).")
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [Block(id=l.id, text=l.text, bold=l.bold, size=round(l.size, 1), page=l.page + 1) for l in _pdf_lines(doc)]


def pdf_page_count(data: bytes) -> int:
    if pymupdf is None:
        return 0
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return doc.page_count


def render_pdf_page(data: bytes, page_number: int, dpi: int = 110) -> bytes:
    if pymupdf is None:
        raise DocEditError("PDF preview isn't installed on the server.")
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if not 1 <= page_number <= doc.page_count:
            raise DocEditError("No such page.")
        return doc[page_number - 1].get_pixmap(dpi=dpi).tobytes("png")


def _css_font(serif: bool) -> str:
    files = _font_files()
    if serif and "DejaVuSerif.ttf" in files:
        return "DejaVu Serif, serif"
    if not serif and "DejaVuSans.ttf" in files:
        return "DejaVu Sans, sans-serif"
    return "serif" if serif else "sans-serif"


def _write_html(page, rect, text: str, line: _PdfLine) -> None:
    label, rest = _label_split(text)
    body = html.escape(rest if label else text).replace("\n", "<br>")
    content = (f"<b>{html.escape(label)}</b>{body}" if label else body)
    if line.bold and not label:
        content = f"<b>{content}</b>"
    r, g, b = (line.color >> 16) & 255, (line.color >> 8) & 255, line.color & 255
    css = (f"* {{font-family: {_css_font(line.serif)}; font-size: {line.size:.1f}px; "
           f"color: rgb({r},{g},{b}); line-height: 1.15; margin: 0; padding: 0;}}")
    page.insert_htmlbox(pymupdf.Rect(rect), content, css=css, scale_low=0.6)


def apply_pdf_ops(data: bytes, ops: list) -> EditOutcome:
    if pymupdf is None:
        raise DocEditError("PDF editing isn't installed on the server (Termux: pkg install python-pymupdf).")
    doc = pymupdf.open(stream=data, filetype="pdf")
    try:
        lines = _pdf_lines(doc)
        by_id = {l.id: l for l in lines}
        order = [l.id for l in lines]
        changes: List[Change] = []

        def span(start: str, end: Optional[str]) -> List[_PdfLine]:
            if start not in by_id:
                raise DocEditError(f"Couldn't find line {start} in the PDF.")
            if not end or end == start or end not in by_id:
                return [by_id[start]]
            i, j = sorted((order.index(start), order.index(end)))
            chosen = [by_id[x] for x in order[i:j + 1]]
            if len({l.page for l in chosen}) > 1:
                raise DocEditError("A single change can't span two PDF pages; change each page separately.")
            return chosen

        # Collect edits per page so redactions happen once per page.
        pending = []
        for op in ops:
            if op.op not in ("replace", "delete"):
                raise DocEditError(
                    "PDFs can only have text replaced or removed in place. For layout changes "
                    "(columns, fonts, adding questions) ask me to convert it into an editable Paperly paper."
                )
            chosen = span(op.target, op.end_target)
            page = doc[chosen[0].page]
            x0 = min(l.rect[0] for l in chosen)
            y0 = min(l.rect[1] for l in chosen)
            x1 = max(l.rect[2] for l in chosen)
            y1 = max(l.rect[3] for l in chosen)
            # Use the width up to the right margin, but stop before text beside it (e.g. right-aligned marks).
            chosen_ids = {c.id for c in chosen}
            beside = [l.rect[0] for l in lines if l.page == chosen[0].page and l.id not in chosen_ids
                      and l.rect[0] >= x1 - 1 and l.rect[1] < y1 and l.rect[3] > y0]
            right_edge = min(beside) - 4 if beside else max(
                (l.rect[2] for l in lines if l.page == chosen[0].page), default=x1)
            # Grow downward into empty space before the next text on the page, so longer text keeps its size.
            below = [l.rect[1] for l in lines if l.page == chosen[0].page and l.rect[1] >= y1 - 0.5
                     and l.id not in {c.id for c in chosen} and l.rect[0] < max(x1, right_edge) and l.rect[2] > x0]
            page_bottom = page.rect.height - 20
            bottom = min(below + [page_bottom]) - 1
            box = (x0, y0 - 0.5, max(x1, right_edge), max(y1 + 1, bottom))
            before = "\n".join(l.text for l in chosen)
            for l in chosen:
                for r in l.spans:  # each text line of the unit
                    page.add_redact_annot(pymupdf.Rect(r[0], r[1] - 0.5, r[2], r[3] + 0.5), fill=(1, 1, 1))
            pending.append((page, box, op, chosen[0], before))

        for page in {p for p, *_ in pending}:
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)

        for page, box, op, first, before in pending:
            if op.op == "replace" and (op.text or "").strip():
                _write_html(page, box, op.text, first)
            changes.append(Change(first.id, before, op.text if op.op == "replace" else ""))

        out = doc.tobytes(garbage=3, deflate=True)
        return EditOutcome(out, changes)
    finally:
        doc.close()

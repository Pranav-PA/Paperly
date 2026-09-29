import html
import io
import re
from typing import List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, LEGAL, LETTER, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    FrameBreak,
    HRFlowable,
    KeepTogether,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.paper_schema import PaperLayout, PaperSchema, Question
from app.services.fonts import font_set

_PAGE_SIZES = {"A4": A4, "Letter": LETTER, "Legal": LEGAL}
_MARGINS = {"narrow": 0.5 * inch, "normal": 0.75 * inch, "wide": 1.0 * inch}
_COLUMN_GAP = 18


def _esc(text: str) -> str:
    """Escape for ReportLab's mini-markup while keeping line breaks."""
    return html.escape(text or "").replace("\n", "<br/>")


def question_label(layout: PaperLayout, n: int) -> str:
    return {"Q1.": f"Q{n}.", "1.": f"{n}.", "1)": f"{n})", "(1)": f"({n})"}.get(layout.numbering_style, f"Q{n}.")


def marks_label(marks: float) -> str:
    return f"[{marks:g} Mark{'' if marks == 1 else 's'}]"


def accent(layout: PaperLayout):
    if layout.accent_color and re.fullmatch(r"#?[0-9a-fA-F]{6}", layout.accent_color.strip()):
        return colors.HexColor("#" + layout.accent_color.strip().lstrip("#"))
    return colors.black


class _Styles:
    def __init__(self, layout: PaperLayout):
        regular, bold, italic, _ = font_set(layout.font_family)
        fs = layout.font_size
        lead = fs * layout.line_spacing
        color = accent(layout)
        head_align = TA_CENTER if layout.header_alignment == "center" else TA_LEFT
        self.bold_font = bold
        self.body = ParagraphStyle("Body", fontName=regular, fontSize=fs, leading=lead)
        self.small = ParagraphStyle("Small", parent=self.body, fontSize=fs - 1, leading=(fs - 1) * layout.line_spacing)
        self.institution = ParagraphStyle("Inst", parent=self.body, fontName=bold, fontSize=fs + 4, leading=(fs + 4) * 1.25,
                                          alignment=head_align, textColor=color, spaceAfter=2)
        self.title = ParagraphStyle("Title", parent=self.body, fontName=bold, fontSize=fs + 3, leading=(fs + 3) * 1.25,
                                    alignment=head_align, textColor=color, spaceAfter=2)
        self.subtitle = ParagraphStyle("Sub", parent=self.body, fontName=italic, alignment=head_align, spaceAfter=6)
        self.right = ParagraphStyle("Right", parent=self.body, alignment=TA_RIGHT)
        self.section = ParagraphStyle("Section", parent=self.body, fontName=bold, fontSize=fs + 1, leading=(fs + 1) * 1.3,
                                      alignment=TA_CENTER, textColor=color, spaceBefore=10, spaceAfter=3)
        self.section_note = ParagraphStyle("SecNote", parent=self.small, fontName=italic, alignment=TA_CENTER, spaceAfter=5)
        self.question = ParagraphStyle("Q", parent=self.body, spaceBefore=5, spaceAfter=2)
        self.option = ParagraphStyle("Opt", parent=self.body, leftIndent=14, spaceAfter=1)
        self.solution = ParagraphStyle("Sol", parent=self.small, fontName=italic, textColor=colors.HexColor("#003366"),
                                       leftIndent=14, spaceBefore=2, spaceAfter=3)
        self.instructions_head = ParagraphStyle("GIH", parent=self.body, fontName=bold, spaceBefore=4, spaceAfter=2)
        self.instruction = ParagraphStyle("GI", parent=self.small, leftIndent=8, spaceAfter=1)
        self.footer_font = regular
        self.footer_size = max(fs - 2, 7)


class PdfGenerationService:
    @classmethod
    def generate_pdf_bytes(cls, schema: PaperSchema, include_solutions: bool = False, solutions_only: bool = False) -> bytes:
        """Render the paper (optionally with answers, or just the answer key) following schema.layout."""
        layout = schema.layout
        st = _Styles(layout)

        page = _PAGE_SIZES.get(layout.page_size, A4)
        if layout.orientation == "landscape":
            page = landscape(page)
        margin = _MARGINS.get(layout.margins, _MARGINS["normal"])
        width = page[0] - 2 * margin
        columns = 1 if solutions_only else layout.columns
        col_width = (width - _COLUMN_GAP * (columns - 1)) / columns

        header = cls._header(schema, st, width, solutions_only)
        body = cls._body(schema, st, col_width, include_solutions or solutions_only, solutions_only)

        buffer = io.BytesIO()
        doc = BaseDocTemplate(buffer, pagesize=page, leftMargin=margin, rightMargin=margin,
                              topMargin=margin, bottomMargin=margin, title=schema.metadata.title)
        top, bottom = page[1] - margin, margin + 14  # leave room for the footer line

        def column_frames(y_top: float, prefix: str) -> List[Frame]:
            return [
                Frame(margin + i * (col_width + _COLUMN_GAP), bottom, col_width, y_top - bottom,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id=f"{prefix}{i}")
                for i in range(columns)
            ]

        def decorate(y_top: float):
            def on_page(canvas, _doc):
                canvas.saveState()
                canvas.setFont(st.footer_font, st.footer_size)
                canvas.setFillColor(colors.HexColor("#555555"))
                if layout.footer_text:
                    canvas.drawString(margin, margin - 2, layout.footer_text[:150])
                if layout.show_page_numbers:
                    canvas.drawRightString(page[0] - margin, margin - 2, f"Page {canvas.getPageNumber()}")
                if columns > 1:
                    canvas.setStrokeColor(colors.HexColor("#BBBBBB"))
                    canvas.setLineWidth(0.5)
                    for i in range(1, columns):
                        x = margin + i * (col_width + _COLUMN_GAP) - _COLUMN_GAP / 2
                        canvas.line(x, bottom, x, y_top)
                canvas.restoreState()
            return on_page

        if columns == 1:
            doc.addPageTemplates([PageTemplate(id="single", frames=column_frames(top, "c"), onPage=decorate(top))])
            story = header + body
        else:
            # Header spans the full width on page 1; questions flow through the columns below it.
            header_height = sum(
                f.wrap(width, page[1])[1] + f.getSpaceBefore() + f.getSpaceAfter() for f in header
            ) + 8
            header_height = min(header_height, (top - bottom) * 0.7)
            first_top = top - header_height
            header_frame = Frame(margin, first_top, width, header_height,
                                 leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="header")
            doc.addPageTemplates([
                PageTemplate(id="first", frames=[header_frame] + column_frames(first_top - 4, "f"), onPage=decorate(first_top - 4)),
                PageTemplate(id="later", frames=column_frames(top, "l"), onPage=decorate(top)),
            ])
            story = [NextPageTemplate("later")] + header + [FrameBreak()] + body

        doc.build(story)
        return buffer.getvalue()

    @staticmethod
    def _header(schema: PaperSchema, st: _Styles, width: float, solutions_only: bool) -> list:
        meta, layout = schema.metadata, schema.layout
        out = []
        if meta.institution_name:
            out.append(Paragraph(_esc(meta.institution_name.upper()), st.institution))
        title = f"Answer Key & Solutions: {meta.title}" if solutions_only else meta.title
        out.append(Paragraph(_esc(title), st.title))
        if meta.subtitle:
            out.append(Paragraph(_esc(meta.subtitle), st.subtitle))
        if solutions_only:
            out.append(HRFlowable(width="100%", thickness=1, color=accent(layout), spaceBefore=4, spaceAfter=6))
            return out

        subject = meta.subject + (f" ({meta.class_grade})" if meta.class_grade else "")
        rows = [
            [Paragraph(f"<b>Subject:</b> {_esc(subject)}", st.body),
             Paragraph(f"<b>Max Marks:</b> {meta.total_marks:g}", st.right)],
            [Paragraph(f"<b>Date:</b> {_esc(meta.date or '____________')}", st.body),
             Paragraph(f"<b>Time Allowed:</b> {meta.duration_minutes} Mins", st.right)],
        ]
        table = Table(rows, colWidths=[width / 2, width / 2])
        style = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 6 if layout.boxed_header else 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6 if layout.boxed_header else 0),
        ]
        if layout.boxed_header:
            style.append(("BOX", (0, 0), (-1, -1), 1, accent(layout)))
        table.setStyle(TableStyle(style))
        out.append(table)

        if layout.student_fields:
            cells = [Paragraph(f"<b>{_esc(f)}:</b> ________________", st.body) for f in layout.student_fields[:6]]
            per_row = 3 if len(cells) > 2 else len(cells)
            grid = [cells[i:i + per_row] for i in range(0, len(cells), per_row)]
            grid[-1] += [""] * (per_row - len(grid[-1]))
            fields = Table(grid, colWidths=[width / per_row] * per_row)
            fields.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 6)]))
            out.append(Spacer(1, 4))
            out.append(fields)

        if meta.general_instructions:
            out.append(Paragraph("General Instructions:", st.instructions_head))
            for inst in meta.general_instructions:
                out.append(Paragraph(f"• {_esc(inst)}", st.instruction))
        out.append(HRFlowable(width="100%", thickness=1, color=accent(schema.layout), spaceBefore=6, spaceAfter=4))
        return out

    @classmethod
    def _body(cls, schema: PaperSchema, st: _Styles, col_width: float, with_answers: bool, solutions_only: bool) -> list:
        layout = schema.layout
        out = []
        for sec in schema.sections:
            out.append(Paragraph(_esc(sec.title.upper()), st.section))
            if sec.instructions and not solutions_only:
                out.append(Paragraph(f"({_esc(sec.instructions)})", st.section_note))
            for q in sec.questions:
                block = cls._answer_only(q, layout, st) if solutions_only else cls._question(q, layout, st, col_width, with_answers)
                out.append(KeepTogether(block))
        return out

    @staticmethod
    def _question(q: Question, layout: PaperLayout, st: _Styles, col_width: float, with_answers: bool) -> list:
        label = question_label(layout, q.question_number)
        text = Paragraph(f"<b>{label}</b> {_esc(q.text)}", st.question)
        if layout.show_marks and q.marks:
            marks_w = min(58, col_width * 0.25)
            row = Table([[text, Paragraph(f"<b>{marks_label(q.marks)}</b>", st.right)]],
                        colWidths=[col_width - marks_w, marks_w])
            row.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            block = [row]
        else:
            block = [text]

        if q.options:
            opts = [f"<b>({_esc(o.label)})</b> {_esc(o.text)}" for o in q.options]
            if layout.option_layout == "inline":
                block.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;".join(opts), st.option))
            elif layout.option_layout == "grid":
                cells = [Paragraph(o, st.option) for o in opts]
                if len(cells) % 2:
                    cells.append("")
                grid = Table([cells[i:i + 2] for i in range(0, len(cells), 2)], colWidths=[col_width / 2] * 2)
                grid.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                                          ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                                          ("VALIGN", (0, 0), (-1, -1), "TOP")]))
                block.append(grid)
            else:
                block.extend(Paragraph(o, st.option) for o in opts)
        elif layout.answer_lines and not with_answers:
            gap = layout.font_size * 1.9
            for _ in range(layout.answer_lines):
                block.append(Spacer(1, gap))
                block.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#999999"), spaceBefore=0, spaceAfter=0))

        if with_answers:
            if q.answer_key:
                block.append(Paragraph(f"<b>Answer:</b> {_esc(q.answer_key)}", st.solution))
            if q.detailed_solution:
                block.append(Paragraph(f"<b>Solution:</b> {_esc(q.detailed_solution)}", st.solution))
        block.append(Spacer(1, 3))
        return block

    @staticmethod
    def _answer_only(q: Question, layout: PaperLayout, st: _Styles) -> list:
        label = question_label(layout, q.question_number)
        answer = _esc(q.answer_key) if q.answer_key else "<i>(no answer provided)</i>"
        block = [Paragraph(f"<b>{label}</b> <b>Answer:</b> {answer}", st.question)]
        if q.detailed_solution:
            block.append(Paragraph(_esc(q.detailed_solution), st.solution))
        return block

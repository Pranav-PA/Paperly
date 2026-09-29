import io
import html
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from app.schemas.paper_schema import PaperSchema, QuestionType


class PdfGenerationService:
    @classmethod
    def generate_pdf_bytes(cls, schema: PaperSchema, include_solutions: bool = False) -> bytes:
        """
        Generates a publication-grade vector PDF using pure-Python ReportLab.
        Works reliably on Termux and low-resource Linux systems without headless browsers.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        styles = getSampleStyleSheet()

        # Custom Typography Styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=14,
            leading=18,
            alignment=1,  # Center
            fontName="Helvetica-Bold",
            spaceAfter=2,
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=13,
            alignment=1,
            fontName="Helvetica-Oblique",
            spaceAfter=6,
        )
        section_style = ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading2"],
            fontSize=11,
            leading=15,
            alignment=1,
            fontName="Helvetica-Bold",
            spaceBefore=10,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "DocBody",
            parent=styles["Normal"],
            fontSize=10,
            leading=13,
            fontName="Helvetica",
        )
        question_style = ParagraphStyle(
            "QuestionText",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            fontName="Helvetica",
            spaceBefore=4,
            spaceAfter=2,
        )
        option_style = ParagraphStyle(
            "OptionText",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=13,
            fontName="Helvetica",
            leftIndent=15,
            spaceAfter=1,
        )
        solution_style = ParagraphStyle(
            "SolutionText",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            fontName="Helvetica-Oblique",
            textColor=colors.HexColor("#003366"),
            leftIndent=15,
            spaceBefore=2,
            spaceAfter=3,
        )

        elements = []
        meta = schema.metadata

        # 1. Header (Institution & Exam Title)
        if meta.institution_name:
            elements.append(Paragraph(html.escape(meta.institution_name.upper()), title_style))
        elements.append(Paragraph(html.escape(meta.title), title_style))
        if meta.subtitle:
            elements.append(Paragraph(html.escape(meta.subtitle), subtitle_style))

        # 2. Metadata Bar Table
        c_subject = meta.subject + (f" ({meta.class_grade})" if meta.class_grade else "")
        meta_data = [
            [
                Paragraph(f"<b>Subject:</b> {html.escape(c_subject)}", body_style),
                Paragraph(f"<b>Max Marks:</b> {meta.total_marks:g}", ParagraphStyle("Right", parent=body_style, alignment=2)),
            ],
            [
                Paragraph(f"<b>Date:</b> {html.escape(meta.date or 'Academic Session')}", body_style),
                Paragraph(f"<b>Time Allowed:</b> {meta.duration_minutes} Mins", ParagraphStyle("Right2", parent=body_style, alignment=2)),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[3.25 * inch, 3.25 * inch])
        meta_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 4))

        # 3. General Instructions
        if meta.general_instructions:
            elements.append(Paragraph("<b>General Instructions:</b>", ParagraphStyle("GIHeading", parent=body_style, fontName="Helvetica-Bold", spaceBefore=4, spaceAfter=2)))
            for inst in meta.general_instructions:
                elements.append(Paragraph(f"• {html.escape(inst)}", ParagraphStyle("GIItem", parent=body_style, fontSize=9, leading=12, leftIndent=8, spaceAfter=1)))
            elements.append(Spacer(1, 4))

        # Divider rule
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=4, spaceAfter=6))

        # 4. Sections & Questions
        for sec in schema.sections:
            elements.append(Paragraph(html.escape(sec.title.upper()), section_style))
            if sec.instructions:
                elements.append(Paragraph(f"<i>({html.escape(sec.instructions)})</i>", ParagraphStyle("SecInst", parent=body_style, fontSize=9, alignment=1, spaceAfter=4)))

            for q in sec.questions:
                q_elements = []
                q_text = f"<b>Q{q.question_number}.</b> {html.escape(q.text)}  <b>[{q.marks:g} Marks]</b>"
                q_elements.append(Paragraph(q_text, question_style))

                if q.options and q.type in [QuestionType.MCQ, QuestionType.MULTI_SELECT]:
                    for opt in q.options:
                        opt_str = f"<b>({opt.label})</b> {html.escape(opt.text)}"
                        q_elements.append(Paragraph(opt_str, option_style))

                if include_solutions and (q.answer_key or q.detailed_solution):
                    if q.answer_key:
                        q_elements.append(Paragraph(f"<b>Answer:</b> {html.escape(q.answer_key)}", solution_style))
                    if q.detailed_solution:
                        q_elements.append(Paragraph(f"<b>Solution:</b> {html.escape(q.detailed_solution)}", solution_style))

                elements.append(KeepTogether(q_elements))
                elements.append(Spacer(1, 3))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

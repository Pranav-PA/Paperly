import io
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

from app.schemas.paper_schema import PaperSchema


class DocxGenerationService:
    @classmethod
    def generate_question_paper_docx(cls, schema: PaperSchema, include_solutions: bool = False) -> bytes:
        """Renders PaperSchema into a publication-grade DOCX examination paper."""
        doc = Document()

        # Set 0.75-inch standard margins
        for section in doc.sections:
            section.top_margin = Inches(0.75)
            section.bottom_margin = Inches(0.75)
            section.left_margin = Inches(0.75)
            section.right_margin = Inches(0.75)

        # 1. Header (Institution & Exam Title)
        meta = schema.metadata
        if meta.institution_name:
            p_inst = doc.add_paragraph()
            p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r_inst = p_inst.add_run(meta.institution_name.upper())
            r_inst.bold = True
            r_inst.font.size = Pt(14)
            p_inst.paragraph_format.space_after = Pt(2)

        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_title = p_title.add_run(meta.title)
        r_title.bold = True
        r_title.font.size = Pt(12)
        p_title.paragraph_format.space_after = Pt(4)

        if meta.subtitle:
            p_sub = doc.add_paragraph()
            p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r_sub = p_sub.add_run(meta.subtitle)
            r_sub.italic = True
            r_sub.font.size = Pt(10)
            p_sub.paragraph_format.space_after = Pt(6)

        # 2. Metadata Bar Table (Class, Subject, Time, Max Marks)
        table = doc.add_table(rows=2, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False

        # Left: Class & Subject; Right: Time & Marks
        c_subject = meta.subject + (f" ({meta.class_grade})" if meta.class_grade else "")
        table.cell(0, 0).paragraphs[0].text = f"Subject: {c_subject}"
        table.cell(0, 1).paragraphs[0].text = f"Maximum Marks: {meta.total_marks:g}"
        table.cell(0, 1).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

        duration_str = f"{meta.duration_minutes} Minutes"
        table.cell(1, 0).paragraphs[0].text = f"Date: {meta.date or '____________'}"
        table.cell(1, 1).paragraphs[0].text = f"Time Allowed: {duration_str}"
        table.cell(1, 1).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

        doc.add_paragraph().paragraph_format.space_after = Pt(4)

        # 3. General Instructions
        if meta.general_instructions:
            p_inst_heading = doc.add_paragraph()
            r_ih = p_inst_heading.add_run("General Instructions:")
            r_ih.bold = True
            r_ih.font.size = Pt(10)
            p_inst_heading.paragraph_format.space_after = Pt(2)

            for inst in meta.general_instructions:
                p_i = doc.add_paragraph(style="List Bullet")
                r_i = p_i.add_run(inst)
                r_i.font.size = Pt(9.5)
                p_i.paragraph_format.space_after = Pt(2)

            doc.add_paragraph().paragraph_format.space_after = Pt(6)

        # Horizontal Divider line
        p_div = doc.add_paragraph()
        p_div.paragraph_format.space_after = Pt(10)
        p_div_border = parse_xml(r'<w:pBdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                                 r'<w:bottom w:val="single" w:sz="6" w:space="1" w:color="000000"/>'
                                 r'</w:pBdr>')
        p_div._p.get_or_add_pPr().append(p_div_border)

        # 4. Sections & Questions
        for section in schema.sections:
            p_sec = doc.add_paragraph()
            p_sec.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r_sec = p_sec.add_run(section.title.upper())
            r_sec.bold = True
            r_sec.font.size = Pt(11)
            p_sec.paragraph_format.space_before = Pt(8)
            p_sec.paragraph_format.space_after = Pt(4)

            if section.instructions:
                p_si = doc.add_paragraph()
                p_si.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r_si = p_si.add_run(f"({section.instructions})")
                r_si.italic = True
                r_si.font.size = Pt(9.5)
                p_si.paragraph_format.space_after = Pt(6)

            for q in section.questions:
                cls._render_question_docx(doc, q)
                if include_solutions:
                    cls._render_solution_docx(doc, q)

        # Save to buffer
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

    @classmethod
    def _render_question_docx(cls, doc: Document, q) -> None:
        p_q = doc.add_paragraph()
        p_q.paragraph_format.space_before = Pt(4)
        p_q.paragraph_format.space_after = Pt(2)

        # Question prompt and mark indicator
        r_num = p_q.add_run(f"Q{q.question_number}. ")
        r_num.bold = True
        r_num.font.size = Pt(10.5)

        r_text = p_q.add_run(q.text)
        r_text.font.size = Pt(10.5)

        # Right-aligned marks indicator
        r_marks = p_q.add_run(f"  [{q.marks:g} Mark{'' if q.marks == 1 else 's'}]")
        r_marks.bold = True
        r_marks.font.size = Pt(9.5)

        # Render options for MCQ
        if q.options:
            for opt in q.options:
                p_opt = doc.add_paragraph()
                p_opt.paragraph_format.left_indent = Inches(0.3)
                p_opt.paragraph_format.space_after = Pt(1)
                r_opt_label = p_opt.add_run(f"({opt.label}) ")
                r_opt_label.bold = True
                r_opt_label.font.size = Pt(10)
                r_opt_text = p_opt.add_run(opt.text)
                r_opt_text.font.size = Pt(10)

    @staticmethod
    def _render_solution_docx(doc: Document, q) -> None:
        if not (q.answer_key or q.detailed_solution):
            return
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.space_after = Pt(4)
        if q.answer_key:
            r = p.add_run(f"Answer: {q.answer_key}")
            r.bold = True
            r.font.size = Pt(9.5)
            r.font.color.rgb = RGBColor(0x00, 0x33, 0x66)
        if q.detailed_solution:
            r = p.add_run(f"\nSolution: {q.detailed_solution}")
            r.italic = True
            r.font.size = Pt(9.5)
            r.font.color.rgb = RGBColor(0x00, 0x33, 0x66)

    @classmethod
    def generate_solutions_docx(cls, schema: PaperSchema) -> bytes:
        """Renders comprehensive Answer Key and Step-by-Step Solutions DOCX."""
        doc = Document()
        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_title = p_title.add_run(f"ANSWER KEY & SOLUTIONS: {schema.metadata.title.upper()}")
        r_title.bold = True
        r_title.font.size = Pt(13)

        for section in schema.sections:
            p_sec = doc.add_paragraph()
            r_sec = p_sec.add_run(f"\n{section.title}")
            r_sec.bold = True
            r_sec.font.size = Pt(11)

            for q in section.questions:
                p_sol = doc.add_paragraph()
                p_sol.paragraph_format.space_before = Pt(4)
                r_q = p_sol.add_run(f"Q{q.question_number}: ")
                r_q.bold = True

                if q.answer_key:
                    r_ans = p_sol.add_run(f"Answer: {q.answer_key}\n")
                    r_ans.bold = True

                if q.detailed_solution:
                    r_exp = p_sol.add_run(f"Explanation: {q.detailed_solution}")
                    r_exp.font.size = Pt(10)

        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

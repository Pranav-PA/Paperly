from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    MCQ = "mcq"
    MULTI_SELECT = "multi_select"
    NUMERICAL = "numerical"
    ASSERTION_REASON = "assertion_reason"
    SHORT_ANSWER = "short_answer"
    LONG_ANSWER = "long_answer"
    MATCH_THE_FOLLOWING = "match_the_following"
    CASE_STUDY = "case_study"


class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionOption(BaseModel):
    label: str = Field(description="e.g. A, B, C, D")
    text: str = Field(description="The option content/choice")


class Question(BaseModel):
    id: str = Field(description="Unique question identifier, e.g. q_secA_1")
    question_number: int = Field(description="Displayed sequential question number, e.g. 1")
    type: QuestionType = Field(default=QuestionType.MCQ)
    text: str = Field(description="Question stem / prompt text (supports equations/LaTeX)")
    options: Optional[List[QuestionOption]] = Field(default=None, description="Choices for MCQs")
    marks: float = Field(default=1.0, ge=0, description="Marks allocated for this question (0 if the document shows none)")
    negative_marks: float = Field(default=0.0, description="Negative deduction if incorrect")
    difficulty: DifficultyLevel = Field(default=DifficultyLevel.MEDIUM)
    topic: Optional[str] = Field(default=None, description="Topic or subtopic covered")
    answer_key: Optional[str] = Field(default=None, description="Concise answer (e.g. 'B' or '24.5 m/s')")
    detailed_solution: Optional[str] = Field(
        default=None,
        description="Complete step-by-step solution, equations, substitutions, and pedagogical explanation"
    )
    verification_scratchpad: Optional[str] = Field(
        default=None,
        description="Internal mathematical reasoning and calculation proof performed by AI validator"
    )


class Section(BaseModel):
    id: str = Field(description="e.g. sec_A")
    title: str = Field(description="e.g. Section A: Multiple Choice Questions")
    instructions: Optional[str] = Field(default=None, description="Section-specific guidance")
    section_total_marks: Optional[float] = Field(default=None, description="Calculated total marks for section")
    questions: List[Question] = Field(default_factory=list)


class PaperMetadata(BaseModel):
    institution_name: Optional[str] = Field(default=None, description="School, College, or Institute Name")
    title: str = Field(default="Question Paper", description="e.g. Periodic Assessment 2 / NEET Physics Mock")
    subtitle: Optional[str] = Field(default=None, description="e.g. Academic Session 2026-2027")
    class_grade: Optional[str] = Field(default=None, description="e.g. Class 12 / Grade X")
    subject: str = Field(default="", description="e.g. Physics")
    academic_year: Optional[str] = Field(default=None, description="e.g. 2026")
    date: Optional[str] = Field(default=None, description="e.g. 29 Sep 2026")
    duration_minutes: int = Field(default=60, ge=1, description="Examination duration in minutes")
    total_marks: float = Field(default=0, ge=0, description="Total maximum marks for the paper")
    general_instructions: List[str] = Field(default_factory=list, description="List of exam guidelines")


class PaperLayout(BaseModel):
    """How the paper looks when exported to PDF/DOCX. Every field has a sensible default."""
    columns: int = Field(default=1, ge=1, le=3, description="Question columns per page (header always spans full width)")
    font_family: Literal["serif", "sans"] = Field(default="sans", description="serif = Times style, sans = Helvetica/Arial style")
    font_size: float = Field(default=10.5, ge=7, le=16, description="Body font size in points")
    line_spacing: float = Field(default=1.3, ge=1.0, le=2.5, description="Line height multiplier")
    page_size: Literal["A4", "Letter", "Legal"] = "A4"
    orientation: Literal["portrait", "landscape"] = "portrait"
    margins: Literal["narrow", "normal", "wide"] = "normal"
    option_layout: Literal["vertical", "grid", "inline"] = Field(
        default="vertical", description="MCQ options: one per line, 2x2 grid, or all on one line"
    )
    numbering_style: Literal["Q1.", "1.", "1)", "(1)"] = "Q1."
    show_marks: bool = Field(default=True, description="Show [n Marks] after each question")
    header_alignment: Literal["center", "left"] = "center"
    accent_color: Optional[str] = Field(default=None, description="Hex colour for headings, e.g. #1E3A8A; null = black")
    boxed_header: bool = Field(default=False, description="Draw a border around the exam details block")
    student_fields: List[str] = Field(default_factory=list, description='Blanks under the header, e.g. ["Name", "Roll No."]')
    answer_lines: int = Field(default=0, ge=0, le=20, description="Ruled writing lines after each non-MCQ question")
    footer_text: Optional[str] = None
    show_page_numbers: bool = True


class PaperSchema(BaseModel):
    metadata: PaperMetadata
    sections: List[Section] = Field(default_factory=list)
    layout: PaperLayout = Field(default_factory=PaperLayout)

    def calculate_total_marks(self) -> float:
        """Sum marks across all questions in all sections."""
        total = 0.0
        for section in self.sections:
            sec_total = sum(q.marks for q in section.questions)
            section.section_total_marks = sec_total
            total += sec_total
        return total

    def total_question_count(self) -> int:
        """Count total questions across all sections."""
        return sum(len(s.questions) for s in self.sections)


class PaperEditRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=4000, description="Natural language edit command (e.g. 'Replace Q5 with a numerical')")


class PaperEditResponse(BaseModel):
    paper_id: str
    version_number: int
    change_summary: str
    paper_schema: PaperSchema

from enum import Enum
from typing import List, Optional
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
    marks: float = Field(ge=0.5, description="Marks allocated for this question")
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
    title: str = Field(description="e.g. Periodic Assessment 2 / NEET Physics Mock")
    subtitle: Optional[str] = Field(default=None, description="e.g. Academic Session 2026-2027")
    class_grade: Optional[str] = Field(default=None, description="e.g. Class 12 / Grade X")
    subject: str = Field(description="e.g. Physics")
    academic_year: Optional[str] = Field(default=None, description="e.g. 2026")
    date: Optional[str] = Field(default=None, description="e.g. 29 Sep 2026")
    duration_minutes: int = Field(default=60, ge=1, description="Examination duration in minutes")
    total_marks: float = Field(ge=1.0, description="Total maximum marks for the paper")
    general_instructions: List[str] = Field(default_factory=list, description="List of exam guidelines")


class PaperSchema(BaseModel):
    metadata: PaperMetadata
    sections: List[Section] = Field(default_factory=list)

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

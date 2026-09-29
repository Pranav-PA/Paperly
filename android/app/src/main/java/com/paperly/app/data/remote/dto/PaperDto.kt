package com.paperly.app.data.remote.dto

import com.google.gson.annotations.SerializedName

data class QuestionOptionDto(
    @SerializedName("label") val label: String,
    @SerializedName("text") val text: String
)

data class QuestionDto(
    @SerializedName("id") val id: String,
    @SerializedName("question_number") val questionNumber: Int,
    @SerializedName("type") val type: String,
    @SerializedName("text") val text: String,
    @SerializedName("options") val options: List<QuestionOptionDto>?,
    @SerializedName("marks") val marks: Double,
    @SerializedName("negative_marks") val negativeMarks: Double = 0.0,
    @SerializedName("difficulty") val difficulty: String,
    @SerializedName("topic") val topic: String?,
    @SerializedName("answer_key") val answerKey: String?,
    @SerializedName("detailed_solution") val detailedSolution: String?
)

data class SectionDto(
    @SerializedName("id") val id: String,
    @SerializedName("title") val title: String,
    @SerializedName("instructions") val instructions: String?,
    @SerializedName("section_total_marks") val sectionTotalMarks: Double?,
    @SerializedName("questions") val questions: List<QuestionDto>
)

data class PaperMetadataDto(
    @SerializedName("institution_name") val institutionName: String?,
    @SerializedName("title") val title: String,
    @SerializedName("subtitle") val subtitle: String?,
    @SerializedName("class_grade") val classGrade: String?,
    @SerializedName("subject") val subject: String,
    @SerializedName("academic_year") val academicYear: String?,
    @SerializedName("date") val date: String?,
    @SerializedName("duration_minutes") val durationMinutes: Int,
    @SerializedName("total_marks") val totalMarks: Double,
    @SerializedName("general_instructions") val generalInstructions: List<String>
)

data class PaperSchemaDto(
    @SerializedName("metadata") val metadata: PaperMetadataDto,
    @SerializedName("sections") val sections: List<SectionDto>
)

data class EditPaperRequestDto(
    @SerializedName("instruction") val instruction: String
)

data class EditPaperResponseDto(
    @SerializedName("paper_id") val paperId: String,
    @SerializedName("version_number") val versionNumber: Int,
    @SerializedName("change_summary") val changeSummary: String,
    @SerializedName("paper_schema") val paperSchema: PaperSchemaDto
)

data class PaperVersionDto(
    @SerializedName("id") val id: String,
    @SerializedName("version_number") val versionNumber: Int,
    @SerializedName("change_summary") val changeSummary: String?,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("is_active") val isActive: Boolean
)

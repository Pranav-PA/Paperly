package com.paperly.app.data.model

import com.google.gson.JsonObject
import com.google.gson.annotations.SerializedName

// ---------- Auth ----------
data class LoginRequest(val username: String, val password: String)

data class TokenResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("expires_in") val expiresIn: Long
)

data class UserProfile(
    val id: String,
    val username: String,
    @SerializedName("full_name") val fullName: String?,
    val role: String
)

data class ChangePasswordRequest(
    @SerializedName("current_password") val currentPassword: String,
    @SerializedName("new_password") val newPassword: String
)

data class HealthResponse(
    val status: String,
    val version: String?,
    @SerializedName("ai_mode") val aiMode: String?,
    val model: String?
)

// ---------- Conversations ----------
data class CreateConversationRequest(val title: String)

data class ConversationSummary(
    val id: String,
    val title: String,
    @SerializedName("updated_at") val updatedAt: String,
    @SerializedName("latest_paper_id") val latestPaperId: String?
)

data class Message(
    val id: String,
    val role: String,
    val content: String,
    @SerializedName("metadata_json") val metadataJson: String?,
    @SerializedName("created_at") val createdAt: String
)

data class ConversationDetail(
    val id: String,
    val title: String,
    val messages: List<Message>,
    @SerializedName("latest_paper_id") val latestPaperId: String?,
    @SerializedName("active_job_id") val activeJobId: String?
)

data class SendMessageRequest(val content: String)

data class MessageMeta(
    val action: String?,
    @SerializedName("paper_id") val paperId: String?,
    @SerializedName("job_id") val jobId: String?
)

data class UploadResponse(
    val filename: String,
    @SerializedName("extracted_characters") val extractedCharacters: Int
)

// ---------- Jobs ----------
data class JobStarted(@SerializedName("job_id") val jobId: String)

data class JobStatus(
    val id: String,
    val status: String, // running | done | error
    val result: JsonObject?,
    val error: String?
)

// ---------- Papers ----------
data class PaperSummary(
    val id: String,
    @SerializedName("conversation_id") val conversationId: String,
    val title: String,
    val subject: String?,
    @SerializedName("class_grade") val classGrade: String?,
    @SerializedName("total_marks") val totalMarks: Double,
    @SerializedName("question_count") val questionCount: Int,
    @SerializedName("version_number") val versionNumber: Int,
    @SerializedName("updated_at") val updatedAt: String
)

data class QuestionOption(val label: String, val text: String)

data class Question(
    val id: String,
    @SerializedName("question_number") val number: Int,
    val type: String,
    val text: String,
    val options: List<QuestionOption>?,
    val marks: Double,
    val difficulty: String?,
    val topic: String?,
    @SerializedName("answer_key") val answerKey: String?,
    @SerializedName("detailed_solution") val detailedSolution: String?
)

data class Section(
    val id: String,
    val title: String,
    val instructions: String?,
    @SerializedName("section_total_marks") val totalMarks: Double?,
    val questions: List<Question>
)

data class PaperMetadata(
    @SerializedName("institution_name") val institutionName: String?,
    val title: String,
    val subtitle: String?,
    @SerializedName("class_grade") val classGrade: String?,
    val subject: String,
    @SerializedName("duration_minutes") val durationMinutes: Int,
    @SerializedName("total_marks") val totalMarks: Double,
    @SerializedName("general_instructions") val generalInstructions: List<String>?
)

data class Paper(
    val metadata: PaperMetadata,
    val sections: List<Section>
) {
    val questionCount: Int get() = sections.sumOf { it.questions.size }
}

data class EditRequest(val instruction: String)

data class EditResult(
    @SerializedName("version_number") val versionNumber: Int,
    @SerializedName("change_summary") val changeSummary: String,
    @SerializedName("paper_schema") val paper: Paper
)

data class PaperVersion(
    @SerializedName("version_number") val versionNumber: Int,
    @SerializedName("change_summary") val changeSummary: String?,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("is_active") val isActive: Boolean
)

data class ErrorBody(val detail: Any?)

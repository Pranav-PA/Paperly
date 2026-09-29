package com.paperly.app.data.remote.dto

import com.google.gson.annotations.SerializedName

data class CreateConversationDto(
    @SerializedName("title") val title: String? = "New Assessment"
)

data class ConversationSummaryDto(
    @SerializedName("id") val id: String,
    @SerializedName("title") val title: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String
)

data class MessageDto(
    @SerializedName("id") val id: String,
    @SerializedName("conversation_id") val conversationId: String,
    @SerializedName("role") val role: String,
    @SerializedName("content") val content: String,
    @SerializedName("metadata_json") val metadataJson: String?,
    @SerializedName("created_at") val createdAt: String
)

data class SendMessageDto(
    @SerializedName("content") val content: String
)

data class ConversationDetailDto(
    @SerializedName("id") val id: String,
    @SerializedName("title") val title: String,
    @SerializedName("messages") val messages: List<MessageDto>,
    @SerializedName("latest_paper_id") val latestPaperId: String?
)

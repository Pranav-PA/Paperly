package com.paperly.app.data.remote

import com.paperly.app.data.remote.dto.*
import okhttp3.MultipartBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.*

interface PaperlyApiService {

    // Auth
    @POST("api/v1/auth/login/json")
    suspend fun login(@Body body: LoginRequestDto): Response<TokenDto>

    @GET("api/v1/auth/me")
    suspend fun getMe(): Response<UserDto>

    // Conversations
    @GET("api/v1/conversations")
    suspend fun listConversations(): Response<List<ConversationSummaryDto>>

    @POST("api/v1/conversations")
    suspend fun createConversation(@Body body: CreateConversationDto): Response<ConversationSummaryDto>

    @GET("api/v1/conversations/{id}")
    suspend fun getConversation(@Path("id") id: String): Response<ConversationDetailDto>

    @POST("api/v1/conversations/{id}/messages")
    suspend fun postMessage(
        @Path("id") id: String,
        @Body body: SendMessageDto
    ): Response<MessageDto>

    @Multipart
    @POST("api/v1/conversations/{id}/upload")
    suspend fun uploadFile(
        @Path("id") id: String,
        @Part file: MultipartBody.Part
    ): Response<ResponseBody>

    // Papers & Revision
    @GET("api/v1/papers/{id}")
    suspend fun getPaper(@Path("id") id: String): Response<PaperSchemaDto>

    @POST("api/v1/papers/{id}/edit")
    suspend fun editPaper(
        @Path("id") id: String,
        @Body body: EditPaperRequestDto
    ): Response<EditPaperResponseDto>

    @Streaming
    @GET("api/v1/papers/{id}/export/{format}")
    suspend fun exportPaper(
        @Path("id") id: String,
        @Path("format") format: String,
        @Query("include_answers") includeAnswers: Boolean = false
    ): Response<ResponseBody>

    @Streaming
    @GET("api/v1/papers/{id}/solutions/{format}")
    suspend fun exportSolutions(
        @Path("id") id: String,
        @Path("format") format: String
    ): Response<ResponseBody>

    @GET("api/v1/papers/{id}/versions")
    suspend fun getVersions(@Path("id") id: String): Response<List<PaperVersionDto>>

    @POST("api/v1/papers/{id}/revert/{version_number}")
    suspend fun revertVersion(
        @Path("id") id: String,
        @Path("version_number") versionNumber: Int
    ): Response<ResponseBody>
}

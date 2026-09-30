package com.paperly.app.data.remote

import com.paperly.app.data.model.*
import okhttp3.MultipartBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.*

interface PaperlyApi {
    @GET("health")
    suspend fun health(): HealthResponse

    // Auth
    @POST("api/v1/auth/login/json")
    suspend fun login(@Body body: LoginRequest): TokenResponse

    @GET("api/v1/auth/me")
    suspend fun me(): UserProfile

    @GET("api/v1/auth/discovery")
    suspend fun discovery(): DiscoveryInfo

    @POST("api/v1/auth/change-password")
    suspend fun changePassword(@Body body: ChangePasswordRequest): Response<Unit>

    // Conversations
    @GET("api/v1/conversations")
    suspend fun conversations(): List<ConversationSummary>

    @POST("api/v1/conversations")
    suspend fun createConversation(@Body body: CreateConversationRequest): ConversationSummary

    @GET("api/v1/conversations/{id}")
    suspend fun conversation(@Path("id") id: String): ConversationDetail

    @DELETE("api/v1/conversations/{id}")
    suspend fun deleteConversation(@Path("id") id: String): Response<Unit>

    @POST("api/v1/conversations/{id}/messages")
    suspend fun sendMessage(@Path("id") id: String, @Body body: SendMessageRequest): Message

    @Multipart
    @POST("api/v1/conversations/{id}/upload")
    suspend fun upload(@Path("id") id: String, @Part file: MultipartBody.Part): UploadResponse

    // Jobs
    @GET("api/v1/jobs/{id}")
    suspend fun job(@Path("id") id: String): JobStatus

    // Papers
    @GET("api/v1/papers")
    suspend fun papers(): List<PaperSummary>

    @GET("api/v1/papers/{id}")
    suspend fun paper(@Path("id") id: String): Paper

    @POST("api/v1/papers/{id}/edit")
    suspend fun editPaper(@Path("id") id: String, @Body body: EditRequest): JobStarted

    @GET("api/v1/papers/{id}/pages/{page}")
    suspend fun page(@Path("id") id: String, @Path("page") page: Int, @Query("v") version: Int): Response<ResponseBody>

    @GET("api/v1/papers/{id}/versions")
    suspend fun versions(@Path("id") id: String): List<PaperVersion>

    @POST("api/v1/papers/{id}/revert/{version}")
    suspend fun revert(@Path("id") id: String, @Path("version") version: Int): Response<ResponseBody>

    @Streaming
    @GET("api/v1/papers/{id}/export/{format}")
    suspend fun exportPaper(
        @Path("id") id: String,
        @Path("format") format: String,
        @Query("include_answers") includeAnswers: Boolean
    ): Response<ResponseBody>

    @Streaming
    @GET("api/v1/papers/{id}/solutions/{format}")
    suspend fun exportSolutions(@Path("id") id: String, @Path("format") format: String): Response<ResponseBody>
}

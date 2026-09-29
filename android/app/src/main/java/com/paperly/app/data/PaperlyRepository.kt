package com.paperly.app.data

import android.content.ContentResolver
import android.net.Uri
import android.provider.OpenableColumns
import com.google.gson.Gson
import com.google.gson.JsonParser
import com.paperly.app.data.model.*
import com.paperly.app.data.remote.PaperlyApi
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.io.File
import java.io.IOException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.util.concurrent.TimeUnit

/** Thrown with a message that is safe to show to the teacher as-is. */
class PaperlyException(message: String, val isAuthError: Boolean = false) : Exception(message)

class PaperlyRepository(
    private val sessionStore: SessionStore,
    private val cacheDir: File,
    private val contentResolver: ContentResolver
) {
    private val gson = Gson()

    private val http: OkHttpClient = OkHttpClient.Builder()
        .addInterceptor(Interceptor { chain ->
            val token = sessionStore.current.token
            val request = chain.request().newBuilder().apply {
                if (!token.isNullOrBlank()) header("Authorization", "Bearer $token")
            }.build()
            chain.proceed(request)
        })
        .connectTimeout(20, TimeUnit.SECONDS)
        // Cloudflare closes requests after ~100 s; long AI work runs as polled background jobs instead.
        .readTimeout(95, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    private var cachedUrl: String? = null
    private var cachedApi: PaperlyApi? = null

    private fun api(baseUrl: String = sessionStore.current.serverUrl): PaperlyApi {
        if (baseUrl.isBlank()) throw PaperlyException("Set the server URL first (Server settings on the login screen).")
        if (baseUrl != cachedUrl || cachedApi == null) {
            cachedApi = Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(http)
                .addConverterFactory(GsonConverterFactory.create(gson))
                .build()
                .create(PaperlyApi::class.java)
            cachedUrl = baseUrl
        }
        return cachedApi!!
    }

    /** Run a call and convert every failure into a readable PaperlyException. */
    private suspend fun <T> call(block: suspend PaperlyApi.() -> T): T = withContext(Dispatchers.IO) {
        try {
            api().block()
        } catch (e: CancellationException) {
            throw e
        } catch (e: PaperlyException) {
            throw e
        } catch (e: HttpException) {
            val detail = parseDetail(e.response()?.errorBody()?.string())
            if (e.code() == 401 && sessionStore.current.isLoggedIn) {
                sessionStore.signOut()
                throw PaperlyException("Your session expired. Please sign in again.", isAuthError = true)
            }
            throw PaperlyException(detail ?: httpMessage(e.code()), isAuthError = e.code() == 401)
        } catch (e: SocketTimeoutException) {
            throw PaperlyException("The server took too long to answer. Please try again.")
        } catch (e: UnknownHostException) {
            throw PaperlyException("Can't find the server. Check the Server URL (it changes each time the tunnel restarts).")
        } catch (e: IOException) {
            throw PaperlyException("Can't reach the server. Check your internet and that Paperly is running in Termux.")
        } catch (e: IllegalArgumentException) {
            throw PaperlyException("The Server URL looks invalid. Example: https://your-name.trycloudflare.com")
        } catch (e: Exception) {
            // e.g. the URL points at a web page instead of Paperly, so the reply isn't the JSON we expect.
            throw PaperlyException("Unexpected reply from the server. Check the Server URL points to Paperly.")
        }
    }

    private fun parseDetail(body: String?): String? = try {
        val detail = JsonParser.parseString(body ?: "").asJsonObject.get("detail")
        when {
            detail == null -> null
            detail.isJsonPrimitive -> detail.asString
            detail.isJsonArray -> detail.asJsonArray.firstOrNull()?.asJsonObject?.get("msg")?.asString
            else -> null
        }
    } catch (e: Exception) {
        null
    }

    private fun httpMessage(code: Int) = when (code) {
        401 -> "Incorrect username or password."
        403 -> "This account is disabled."
        404 -> "Not found. It may have been deleted."
        429 -> "Too many attempts. Please wait a few minutes."
        502, 503, 504 -> "The server can't be reached right now. Is Paperly running in Termux?"
        530 -> "The tunnel URL is no longer active. Get the new URL from Termux."
        else -> "Server error ($code). Please try again."
    }

    // ---------- Server & auth ----------
    suspend fun checkServer(url: String): HealthResponse = withContext(Dispatchers.IO) {
        val normalized = SessionStore.normalizeUrl(url)
        try {
            api(normalized).health()
        } catch (e: Exception) {
            if (e is CancellationException) throw e
            throw PaperlyException("No Paperly server found at $normalized")
        }
    }

    suspend fun login(username: String, password: String) {
        val token = call { login(LoginRequest(username.trim(), password)) }.accessToken
        sessionStore.signIn(token, username.trim(), null)
        runCatching { call { me() } }.getOrNull()?.let {
            sessionStore.signIn(token, it.username, it.fullName)
        }
    }

    fun logout() = sessionStore.signOut()

    suspend fun changePassword(current: String, new: String) {
        call { changePassword(ChangePasswordRequest(current, new)) }.let {
            if (!it.isSuccessful) throw PaperlyException(parseDetail(it.errorBody()?.string()) ?: httpMessage(it.code()))
        }
    }

    // ---------- Conversations ----------
    suspend fun conversations() = call { conversations() }

    suspend fun conversation(id: String) = call { conversation(id) }

    suspend fun createConversation(firstPrompt: String): ConversationSummary {
        val title = firstPrompt.trim().let { if (it.length > 60) it.take(57).trimEnd() + "…" else it }
        return call { createConversation(CreateConversationRequest(title)) }
    }

    suspend fun deleteConversation(id: String) {
        call { deleteConversation(id) }
    }

    suspend fun sendMessage(conversationId: String, text: String) =
        call { sendMessage(conversationId, SendMessageRequest(text)) }

    fun metaOf(message: Message): MessageMeta? =
        message.metadataJson?.let { runCatching { gson.fromJson(it, MessageMeta::class.java) }.getOrNull() }

    suspend fun upload(conversationId: String, uri: Uri): UploadResponse {
        val (name, bytes, mime) = withContext(Dispatchers.IO) {
            try {
                var name = "document"
                contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
                    if (c.moveToFirst()) name = c.getString(0) ?: name
                }
                val bytes = contentResolver.openInputStream(uri)?.use { it.readBytes() }
                    ?: throw PaperlyException("Couldn't read that file.")
                Triple(name, bytes, contentResolver.getType(uri) ?: "application/octet-stream")
            } catch (e: PaperlyException) {
                throw e
            } catch (e: Exception) {
                throw PaperlyException("Couldn't read that file. Try saving it to your phone first.")
            } catch (e: OutOfMemoryError) {
                throw PaperlyException("That file is too large to upload.")
            }
        }
        if (bytes.size > 15 * 1024 * 1024) throw PaperlyException("That file is larger than 15 MB.")
        val part = MultipartBody.Part.createFormData("file", name, bytes.toRequestBody(mime.toMediaTypeOrNull()))
        return call { upload(conversationId, part) }
    }

    // ---------- Jobs ----------
    /** Poll a background job until it finishes. Returns the finished job (status done or error). */
    suspend fun awaitJob(jobId: String): JobStatus {
        var networkFailures = 0
        while (true) {
            val job = try {
                call { job(jobId) }.also { networkFailures = 0 }
            } catch (e: PaperlyException) {
                if (e.message?.startsWith("Not found") == true || e.message?.startsWith("Job not found") == true) {
                    throw PaperlyException("The server restarted while working. Please try again.")
                }
                // Brief network blips shouldn't abort a long generation.
                if (e.isAuthError || ++networkFailures >= 5) throw e
                null
            }
            if (job != null && job.status != "running") return job
            delay(2500)
        }
    }

    // ---------- Papers ----------
    suspend fun papers() = call { papers() }

    suspend fun paper(id: String) = call { paper(id) }

    suspend fun editPaper(id: String, instruction: String): EditResult {
        val jobId = call { editPaper(id, EditRequest(instruction)) }.jobId
        val job = awaitJob(jobId)
        if (job.status == "error" || job.result == null) {
            throw PaperlyException(job.error ?: "The change couldn't be applied.")
        }
        return try {
            gson.fromJson(job.result, EditResult::class.java)
        } catch (e: Exception) {
            throw PaperlyException("The change was saved but couldn't be shown. Reopen the paper.")
        }
    }

    suspend fun versions(id: String) = call { versions(id) }

    suspend fun revert(id: String, version: Int) {
        call { revert(id, version) }.let {
            if (!it.isSuccessful) throw PaperlyException(httpMessage(it.code()))
        }
    }

    enum class ExportKind { PAPER, PAPER_WITH_ANSWERS, SOLUTIONS }

    /** Download an export into the app cache and return the file (ready to open/share/save). */
    suspend fun export(paperId: String, title: String, kind: ExportKind, format: String): File {
        val response = call {
            when (kind) {
                ExportKind.SOLUTIONS -> exportSolutions(paperId, format)
                else -> exportPaper(paperId, format, kind == ExportKind.PAPER_WITH_ANSWERS)
            }
        }
        if (!response.isSuccessful) throw PaperlyException(httpMessage(response.code()))
        val body = response.body() ?: throw PaperlyException("The server sent an empty file.")
        return withContext(Dispatchers.IO) {
            val suffix = when (kind) {
                ExportKind.PAPER -> ""
                ExportKind.PAPER_WITH_ANSWERS -> "_with_answers"
                ExportKind.SOLUTIONS -> "_solutions"
            }
            val safeTitle = title.replace(Regex("[^A-Za-z0-9 _-]"), "").trim().replace(' ', '_').ifEmpty { "Paper" }
            val dir = File(cacheDir, "exports").apply { mkdirs() }
            val file = File(dir, "$safeTitle$suffix.$format")
            try {
                body.byteStream().use { input -> file.outputStream().use { input.copyTo(it) } }
            } catch (e: Exception) {
                throw PaperlyException("The download was interrupted. Please try again.")
            }
            file
        }
    }
}

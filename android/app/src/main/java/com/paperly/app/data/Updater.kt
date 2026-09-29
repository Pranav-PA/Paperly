package com.paperly.app.data

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.core.content.FileProvider
import com.google.gson.Gson
import com.google.gson.annotations.SerializedName
import com.paperly.app.BuildConfig
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.util.concurrent.TimeUnit

data class UpdateInfo(val version: String, val notes: String, val apkUrl: String, val sizeBytes: Long)

/**
 * Checks GitHub Releases for a newer Paperly APK, downloads it and hands it to Android's installer.
 * Sideloaded apps can't update silently: Android always shows its own install confirmation.
 */
class Updater(private val context: Context) {
    // Separate client: never send the Paperly login token to GitHub.
    private val http = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()
    private val gson = Gson()

    private data class Asset(
        val name: String,
        @SerializedName("browser_download_url") val url: String,
        val size: Long
    )

    private data class Release(
        @SerializedName("tag_name") val tag: String,
        val body: String?,
        val draft: Boolean,
        val prerelease: Boolean,
        val assets: List<Asset>
    )

    /** Returns the newer release, or null when up to date (or GitHub can't be reached). */
    suspend fun check(): UpdateInfo? = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("https://api.github.com/repos/$REPO/releases/latest")
                .header("Accept", "application/vnd.github+json")
                .build()
            http.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return@withContext null
                val release = gson.fromJson(response.body?.string(), Release::class.java)
                val apk = release.assets.firstOrNull { it.name.endsWith(".apk") } ?: return@withContext null
                val latest = release.tag.removePrefix("v")
                if (release.draft || release.prerelease || !isNewer(latest, BuildConfig.VERSION_NAME)) return@withContext null
                UpdateInfo(latest, cleanNotes(release.body.orEmpty()), apk.url, apk.size)
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            null
        }
    }

    /** Downloads the APK, reporting progress 0..1. */
    suspend fun download(info: UpdateInfo, onProgress: (Float) -> Unit): File = withContext(Dispatchers.IO) {
        val dir = File(context.cacheDir, "updates").apply { mkdirs() }
        dir.listFiles()?.forEach { it.delete() }
        val file = File(dir, "Paperly-${info.version}.apk")
        try {
            http.newCall(Request.Builder().url(info.apkUrl).build()).execute().use { response ->
                if (!response.isSuccessful) throw PaperlyException("Download failed (${response.code}).")
                val body = response.body ?: throw PaperlyException("Download failed.")
                val total = body.contentLength().takeIf { it > 0 } ?: info.sizeBytes
                body.byteStream().use { input ->
                    file.outputStream().use { output ->
                        val buffer = ByteArray(32 * 1024)
                        var done = 0L
                        while (true) {
                            val read = input.read(buffer)
                            if (read < 0) break
                            output.write(buffer, 0, read)
                            done += read
                            if (total > 0) onProgress((done.toFloat() / total).coerceIn(0f, 1f))
                        }
                    }
                }
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: PaperlyException) {
            throw e
        } catch (e: Exception) {
            throw PaperlyException("Download failed. Check the internet connection and try again.")
        }
        file
    }

    /** True once the user has allowed Paperly to install apps (required once on Android 8+). */
    fun canInstall(): Boolean = context.packageManager.canRequestPackageInstalls()

    fun openInstallPermissionSettings() {
        val intent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        runCatching { context.startActivity(intent) }
    }

    fun install(apk: File) {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", apk)
        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
    }

    companion object {
        const val REPO = "Pranav-PA/Paperly"

        /** Compares dotted versions numerically: 1.10.0 > 1.9.3. */
        fun isNewer(candidate: String, current: String): Boolean {
            val a = candidate.split('.', '-').map { it.toIntOrNull() ?: 0 }
            val b = current.split('.', '-').map { it.toIntOrNull() ?: 0 }
            for (i in 0 until maxOf(a.size, b.size)) {
                val x = a.getOrElse(i) { 0 }
                val y = b.getOrElse(i) { 0 }
                if (x != y) return x > y
            }
            return false
        }

        /** Release notes are Markdown; keep them readable as plain text in a dialog. */
        private fun cleanNotes(markdown: String): String = markdown.lines()
            .filterNot { it.contains("Generated with") }
            .joinToString("\n") { line ->
                line.replace(Regex("^#+\\s*"), "")
                    .replace(Regex("^\\s*[-*]\\s+"), "• ")
                    .replace("**", "")
                    .replace("`", "")
                    .replace(Regex("\\[([^]]+)]\\([^)]+\\)"), "$1")
            }
            .trim()
            .take(1200)
    }
}

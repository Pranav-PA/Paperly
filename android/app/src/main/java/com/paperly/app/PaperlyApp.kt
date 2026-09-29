package com.paperly.app

import android.app.Application
import android.os.Build
import com.paperly.app.data.PaperlyRepository
import com.paperly.app.data.SessionStore
import com.paperly.app.data.Updater
import java.io.File

class PaperlyApp : Application() {
    lateinit var sessionStore: SessionStore
        private set
    lateinit var repository: PaperlyRepository
        private set
    lateinit var updater: Updater
        private set

    private val crashFile get() = File(filesDir, "last_crash.txt")

    override fun onCreate() {
        super.onCreate()
        installCrashRecorder()
        sessionStore = SessionStore(this)
        repository = PaperlyRepository(sessionStore, cacheDir, contentResolver)
        updater = Updater(this)
    }

    /** Save any crash so the next launch can show it and let the user share it. */
    private fun installCrashRecorder() {
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            runCatching {
                crashFile.writeText(
                    "Paperly ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})\n" +
                        "Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT}), ${Build.MANUFACTURER} ${Build.MODEL}\n\n" +
                        error.stackTraceToString().take(12_000)
                )
            }
            previous?.uncaughtException(thread, error)
        }
    }

    /** Returns and clears the report from the previous crash, if any. */
    fun takeCrashReport(): String? =
        crashFile.takeIf { it.exists() }?.let { f -> runCatching { f.readText() }.getOrNull().also { f.delete() } }
}

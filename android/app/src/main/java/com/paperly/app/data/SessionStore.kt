package com.paperly.app.data

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class Session(
    val serverUrl: String,
    val token: String?,
    val username: String?,
    val fullName: String?
) {
    val isLoggedIn: Boolean get() = !token.isNullOrBlank()
    val displayName: String get() = fullName?.takeIf { it.isNotBlank() } ?: username.orEmpty()
}

/** Persists the server URL and login so the app stays signed in across restarts. */
class SessionStore(context: Context) {
    private val prefs = context.getSharedPreferences("paperly_session", Context.MODE_PRIVATE)

    private val _session = MutableStateFlow(read())
    val session: StateFlow<Session> = _session.asStateFlow()

    val current: Session get() = _session.value

    private fun read() = Session(
        serverUrl = prefs.getString(KEY_URL, null) ?: "",
        token = prefs.getString(KEY_TOKEN, null),
        username = prefs.getString(KEY_USER, null),
        fullName = prefs.getString(KEY_NAME, null)
    )

    fun setServerUrl(url: String) {
        prefs.edit().putString(KEY_URL, normalizeUrl(url)).apply()
        _session.value = read()
    }

    fun signIn(token: String, username: String, fullName: String?) {
        prefs.edit()
            .putString(KEY_TOKEN, token)
            .putString(KEY_USER, username)
            .putString(KEY_NAME, fullName)
            .apply()
        _session.value = read()
    }

    fun signOut() {
        prefs.edit().remove(KEY_TOKEN).remove(KEY_NAME).apply()
        _session.value = read()
    }

    companion object {
        private const val KEY_URL = "server_url"
        private const val KEY_TOKEN = "token"
        private const val KEY_USER = "username"
        private const val KEY_NAME = "full_name"

        /** Accepts "abc.trycloudflare.com", "192.168.1.5:8000", full URLs; returns "scheme://host[:port]/". */
        fun normalizeUrl(input: String): String {
            var url = input.trim().trimEnd('/')
            if (url.isEmpty()) return ""
            if (!url.startsWith("http://") && !url.startsWith("https://")) {
                val looksLocal = url.first().isDigit() || url.startsWith("localhost")
                url = (if (looksLocal) "http://" else "https://") + url
            }
            return "$url/"
        }
    }
}

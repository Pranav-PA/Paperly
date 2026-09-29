package com.paperly.app

import android.app.Application
import com.paperly.app.data.PaperlyRepository
import com.paperly.app.data.SessionStore

class PaperlyApp : Application() {
    lateinit var sessionStore: SessionStore
        private set
    lateinit var repository: PaperlyRepository
        private set

    override fun onCreate() {
        super.onCreate()
        sessionStore = SessionStore(this)
        repository = PaperlyRepository(sessionStore, cacheDir, contentResolver)
    }
}

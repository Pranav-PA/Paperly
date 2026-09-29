package com.paperly.app

import android.app.Application
import com.paperly.app.data.local.PaperlyDatabase
import com.paperly.app.data.repository.AuthRepository
import com.paperly.app.data.repository.ConversationRepository
import com.paperly.app.data.repository.PaperRepository

class PaperlyApp : Application() {

    lateinit var database: PaperlyDatabase
        private set

    lateinit var authRepository: AuthRepository
        private set

    lateinit var conversationRepository: ConversationRepository
        private set

    lateinit var paperRepository: PaperRepository
        private set

    override fun onCreate() {
        super.onCreate()
        database = PaperlyDatabase.getInstance(this)
        authRepository = AuthRepository(database.userDao())
        conversationRepository = ConversationRepository(database.conversationDao(), database.messageDao())
        paperRepository = PaperRepository(database.paperDao())
    }
}

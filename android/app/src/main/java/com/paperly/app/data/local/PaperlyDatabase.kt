package com.paperly.app.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import com.paperly.app.data.local.dao.ConversationDao
import com.paperly.app.data.local.dao.MessageDao
import com.paperly.app.data.local.dao.PaperDao
import com.paperly.app.data.local.dao.UserDao
import com.paperly.app.data.local.entity.ConversationEntity
import com.paperly.app.data.local.entity.MessageEntity
import com.paperly.app.data.local.entity.PaperEntity
import com.paperly.app.data.local.entity.UserEntity

@Database(
    entities = [
        UserEntity::class,
        ConversationEntity::class,
        MessageEntity::class,
        PaperEntity::class
    ],
    version = 1,
    exportSchema = false
)
abstract class PaperlyDatabase : RoomDatabase() {

    abstract fun userDao(): UserDao
    abstract fun conversationDao(): ConversationDao
    abstract fun messageDao(): MessageDao
    abstract fun paperDao(): PaperDao

    companion object {
        @Volatile
        private var INSTANCE: PaperlyDatabase? = null

        fun getInstance(context: Context): PaperlyDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    PaperlyDatabase::class.java,
                    "paperly_local.db"
                ).fallbackToDestructiveMigration().build()
                INSTANCE = instance
                instance
            }
        }
    }
}

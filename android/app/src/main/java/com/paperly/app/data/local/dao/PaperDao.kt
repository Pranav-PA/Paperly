package com.paperly.app.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.paperly.app.data.local.entity.PaperEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface PaperDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertPaper(paper: PaperEntity)

    @Query("SELECT * FROM papers WHERE id = :id LIMIT 1")
    fun getPaperById(id: String): Flow<PaperEntity?>

    @Query("SELECT * FROM papers WHERE conversationId = :conversationId ORDER BY updatedAt DESC LIMIT 1")
    suspend fun getPaperByConversation(conversationId: String): PaperEntity?

    @Query("SELECT * FROM papers ORDER BY updatedAt DESC")
    fun getAllPapers(): Flow<List<PaperEntity>>
}

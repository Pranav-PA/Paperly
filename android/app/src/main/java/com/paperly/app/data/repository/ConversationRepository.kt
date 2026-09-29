package com.paperly.app.data.repository

import com.paperly.app.data.local.dao.ConversationDao
import com.paperly.app.data.local.dao.MessageDao
import com.paperly.app.data.local.entity.ConversationEntity
import com.paperly.app.data.local.entity.MessageEntity
import com.paperly.app.data.remote.NetworkClient
import com.paperly.app.data.remote.PaperlyApiService
import com.paperly.app.data.remote.dto.CreateConversationDto
import com.paperly.app.data.remote.dto.SendMessageDto
import kotlinx.coroutines.flow.Flow
import java.util.UUID

class ConversationRepository(
    private val conversationDao: ConversationDao,
    private val messageDao: MessageDao,
    private val apiService: PaperlyApiService = NetworkClient.getApiService()
) {

    fun getLocalConversations(): Flow<List<ConversationEntity>> =
        conversationDao.getAllConversations()

    fun getLocalMessages(conversationId: String): Flow<List<MessageEntity>> =
        messageDao.getMessagesForConversation(conversationId)

    suspend fun refreshConversations(): Result<Unit> {
        return try {
            val response = apiService.listConversations()
            if (response.isSuccessful && response.body() != null) {
                val entities = response.body()!!.map { dto ->
                    ConversationEntity(
                        id = dto.id,
                        title = dto.title,
                        createdAt = System.currentTimeMillis(),
                        updatedAt = System.currentTimeMillis()
                    )
                }
                conversationDao.insertConversations(entities)
                Result.success(Unit)
            } else {
                Result.failure(Exception("Failed to fetch conversations: ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun createConversation(title: String): Result<ConversationEntity> {
        return try {
            val response = apiService.createConversation(CreateConversationDto(title))
            if (response.isSuccessful && response.body() != null) {
                val dto = response.body()!!
                val entity = ConversationEntity(
                    id = dto.id,
                    title = dto.title,
                    createdAt = System.currentTimeMillis(),
                    updatedAt = System.currentTimeMillis()
                )
                conversationDao.insertConversation(entity)
                Result.success(entity)
            } else {
                Result.failure(Exception("Failed to create conversation"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun syncConversation(id: String): Result<Unit> {
        return try {
            val response = apiService.getConversation(id)
            if (response.isSuccessful && response.body() != null) {
                val detail = response.body()!!
                val convEntity = ConversationEntity(
                    id = detail.id,
                    title = detail.title,
                    latestPaperId = detail.latestPaperId,
                    createdAt = System.currentTimeMillis(),
                    updatedAt = System.currentTimeMillis()
                )
                conversationDao.insertConversation(convEntity)

                val messageEntities = detail.messages.map { m ->
                    MessageEntity(
                        id = m.id,
                        conversationId = m.conversationId,
                        role = m.role,
                        content = m.content,
                        metadataJson = m.metadataJson,
                        createdAt = System.currentTimeMillis()
                    )
                }
                messageDao.insertMessages(messageEntities)
                Result.success(Unit)
            } else {
                Result.failure(Exception("Sync failed"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun sendMessage(conversationId: String, content: String): Result<MessageEntity> {
        val tempId = UUID.randomUUID().toString()
        val userMsg = MessageEntity(
            id = tempId,
            conversationId = conversationId,
            role = "user",
            content = content
        )
        messageDao.insertMessage(userMsg)

        return try {
            val response = apiService.postMessage(conversationId, SendMessageDto(content))
            if (response.isSuccessful && response.body() != null) {
                val assistantDto = response.body()!!
                val assistantMsg = MessageEntity(
                    id = assistantDto.id,
                    conversationId = conversationId,
                    role = assistantDto.role,
                    content = assistantDto.content,
                    metadataJson = assistantDto.metadataJson,
                    createdAt = System.currentTimeMillis()
                )
                messageDao.insertMessage(assistantMsg)
                // Re-sync conversation to update latestPaperId if paper was generated
                syncConversation(conversationId)
                Result.success(assistantMsg)
            } else {
                Result.failure(Exception("Message failed: ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

package com.paperly.app.data.repository

import android.content.Context
import com.google.gson.Gson
import com.paperly.app.data.local.dao.PaperDao
import com.paperly.app.data.local.entity.PaperEntity
import com.paperly.app.data.remote.NetworkClient
import com.paperly.app.data.remote.PaperlyApiService
import com.paperly.app.data.remote.dto.EditPaperRequestDto
import com.paperly.app.data.remote.dto.PaperSchemaDto
import kotlinx.coroutines.flow.Flow
import java.io.File
import java.io.FileOutputStream

class PaperRepository(
    private val paperDao: PaperDao,
    private val apiService: PaperlyApiService = NetworkClient.getApiService(),
    private val gson: Gson = Gson()
) {

    fun getLocalPaper(id: String): Flow<PaperEntity?> = paperDao.getPaperById(id)

    fun getAllLocalPapers(): Flow<List<PaperEntity>> = paperDao.getAllPapers()

    suspend fun fetchPaper(id: String): Result<PaperSchemaDto> {
        return try {
            val response = apiService.getPaper(id)
            if (response.isSuccessful && response.body() != null) {
                val schema = response.body()!!
                val json = gson.toJson(schema)
                paperDao.insertPaper(
                    PaperEntity(
                        id = id,
                        conversationId = "", // Updated from relation
                        title = schema.metadata.title,
                        schemaJson = json
                    )
                )
                Result.success(schema)
            } else {
                Result.failure(Exception("Failed to fetch paper: ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun editPaper(id: String, instruction: String): Result<PaperSchemaDto> {
        return try {
            val response = apiService.editPaper(id, EditPaperRequestDto(instruction))
            if (response.isSuccessful && response.body() != null) {
                val editRes = response.body()!!
                val updatedSchema = editRes.paperSchema
                val json = gson.toJson(updatedSchema)
                paperDao.insertPaper(
                    PaperEntity(
                        id = id,
                        conversationId = "",
                        title = updatedSchema.metadata.title,
                        currentVersionNumber = editRes.versionNumber,
                        schemaJson = json
                    )
                )
                Result.success(updatedSchema)
            } else {
                Result.failure(Exception("Failed to apply edit: ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun downloadExport(
        context: Context,
        paperId: String,
        format: String,
        isSolutions: Boolean = false,
        includeAnswers: Boolean = false
    ): Result<File> {
        return try {
            val response = if (isSolutions) {
                apiService.exportSolutions(paperId, format)
            } else {
                apiService.exportPaper(paperId, format, includeAnswers)
            }

            if (!response.isSuccessful || response.body() == null) {
                return Result.failure(Exception("Export failed: ${response.message()}"))
            }

            val ext = if (format.lowercase() == "docx") "docx" else "pdf"
            val prefix = if (isSolutions) "Solutions" else "Paper"
            val outputFile = File(context.filesDir, "${prefix}_${paperId}.${ext}")

            response.body()!!.byteStream().use { input ->
                FileOutputStream(outputFile).use { output ->
                    input.copyTo(output)
                }
            }

            Result.success(outputFile)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

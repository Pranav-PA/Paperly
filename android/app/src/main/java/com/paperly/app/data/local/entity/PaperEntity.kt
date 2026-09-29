package com.paperly.app.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "papers")
data class PaperEntity(
    @PrimaryKey val id: String,
    val conversationId: String,
    val title: String,
    val currentVersionNumber: Int = 1,
    val schemaJson: String,
    val updatedAt: Long = System.currentTimeMillis()
)

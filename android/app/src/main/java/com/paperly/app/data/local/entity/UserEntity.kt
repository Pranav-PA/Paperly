package com.paperly.app.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "users")
data class UserEntity(
    @PrimaryKey val id: String,
    val username: String,
    val fullName: String?,
    val role: String,
    val token: String,
    val isActive: Boolean = true
)

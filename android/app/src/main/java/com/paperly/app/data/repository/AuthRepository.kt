package com.paperly.app.data.repository

import com.paperly.app.data.local.dao.UserDao
import com.paperly.app.data.local.entity.UserEntity
import com.paperly.app.data.remote.NetworkClient
import com.paperly.app.data.remote.PaperlyApiService
import com.paperly.app.data.remote.dto.LoginRequestDto
import kotlinx.coroutines.flow.Flow

class AuthRepository(
    private val userDao: UserDao,
    private val apiService: PaperlyApiService = NetworkClient.getApiService()
) {

    fun getActiveUser(): Flow<UserEntity?> = userDao.getActiveUser()

    suspend fun login(username: String, password: String):Result<UserEntity> {
        return try {
            val loginRes = apiService.login(LoginRequestDto(username, password))
            if (!loginRes.isSuccessful || loginRes.body() == null) {
                return Result.failure(Exception("Login failed: ${loginRes.message()}"))
            }

            val token = loginRes.body()!!.accessToken
            NetworkClient.authInterceptor.setToken(token)

            val profileRes = apiService.getMe()
            if (!profileRes.isSuccessful || profileRes.body() == null) {
                return Result.failure(Exception("Failed to fetch user profile"))
            }

            val userDto = profileRes.body()!!
            val userEntity = UserEntity(
                id = userDto.id,
                username = userDto.username,
                fullName = userDto.fullName,
                role = userDto.role,
                token = token,
                isActive = userDto.isActive
            )

            userDao.insertUser(userEntity)
            Result.success(userEntity)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun logout() {
        NetworkClient.authInterceptor.setToken(null)
        userDao.clearUsers()
    }
}

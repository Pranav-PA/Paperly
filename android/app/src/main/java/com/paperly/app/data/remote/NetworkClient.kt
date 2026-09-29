package com.paperly.app.data.remote

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object NetworkClient {
    // Default base URL for Android Emulator -> Host machine; configurable in app settings
    var baseUrl: String = "http://10.0.2.2:8000/"

    val authInterceptor = AuthInterceptor()

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(authInterceptor)
        .addInterceptor(loggingInterceptor)
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS) // Allow time for AI synthesis
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    fun getApiService(customUrl: String? = null): PaperlyApiService {
        val url = customUrl ?: baseUrl
        return Retrofit.Builder()
            .baseUrl(url)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(PaperlyApiService::class.java)
    }
}

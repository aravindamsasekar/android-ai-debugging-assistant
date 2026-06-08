package com.example.debugassistant.data.remote

import com.example.debugassistant.data.model.AnalyzeResponseDto
import retrofit2.http.GET
import retrofit2.http.Path

interface DebugApiService {
    @GET("analyze/{issueId}")
    suspend fun analyzeIssue(@Path("issueId") issueId: String): AnalyzeResponseDto
}

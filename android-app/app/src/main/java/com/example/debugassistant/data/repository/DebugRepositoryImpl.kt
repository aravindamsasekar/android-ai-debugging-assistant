package com.example.debugassistant.data.repository

import com.example.debugassistant.data.model.AnalyzeResponseDto
import com.example.debugassistant.data.remote.DebugApiService
import com.example.debugassistant.domain.model.DebugAnalysis
import com.example.debugassistant.domain.repository.DebugRepository

class DebugRepositoryImpl(
    private val api: DebugApiService,
) : DebugRepository {
    override suspend fun analyzeIssue(issueId: String): Result<DebugAnalysis> = try {
        val dto = api.analyzeIssue(issueId)
        Result.success(dto.toDomain())
    } catch (e: Exception) {
        Result.failure(e)
    }
}

private fun AnalyzeResponseDto.toDomain(): DebugAnalysis = DebugAnalysis(
    issueId = issueId,
    rootCause = rootCause,
    evidence = evidence,
    relevantFiles = relevantFiles,
    suggestedFix = suggestedFix,
    patchSuggestion = patchSuggestion,
    confidence = confidence,
)

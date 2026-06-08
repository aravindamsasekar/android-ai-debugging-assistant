package com.example.debugassistant.domain.usecase

import com.example.debugassistant.domain.model.DebugAnalysis
import com.example.debugassistant.domain.repository.DebugRepository

class AnalyzeIssueUseCase(
    private val repository: DebugRepository,
) {
    suspend operator fun invoke(issueId: String): Result<DebugAnalysis> {
        val trimmedIssueId = issueId.trim()
        if (trimmedIssueId.isBlank()) {
            return Result.failure(IllegalArgumentException("Issue ID cannot be empty"))
        }
        return repository.analyzeIssue(trimmedIssueId)
    }
}

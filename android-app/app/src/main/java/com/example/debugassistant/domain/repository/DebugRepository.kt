package com.example.debugassistant.domain.repository

import com.example.debugassistant.domain.model.DebugAnalysis

interface DebugRepository {
    suspend fun analyzeIssue(issueId: String): Result<DebugAnalysis>
}

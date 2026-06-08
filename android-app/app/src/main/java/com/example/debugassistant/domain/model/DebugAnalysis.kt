package com.example.debugassistant.domain.model

data class DebugAnalysis(
    val issueId: String,
    val rootCause: String,
    val evidence: List<String>,
    val relevantFiles: List<String>,
    val suggestedFix: String,
    val patchSuggestion: String,
    val confidence: String,
)

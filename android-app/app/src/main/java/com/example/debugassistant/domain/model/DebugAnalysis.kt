package com.example.debugassistant.domain.model

data class CodeSnippet(
    val file: String,
    val snippet: String,
)

data class DebugAnalysis(
    val issueId: String,
    val rootCause: String,
    val evidence: List<String>,
    val relevantFiles: List<String>,
    val relevantCode: List<CodeSnippet> = emptyList(),
    val suggestedFix: String,
    val patchSuggestion: String,
    val confidence: String,
)

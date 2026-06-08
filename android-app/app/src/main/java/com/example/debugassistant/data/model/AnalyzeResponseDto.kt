package com.example.debugassistant.data.model

import com.google.gson.annotations.SerializedName

data class AnalyzeResponseDto(
    @SerializedName("issueId") val issueId: String,
    @SerializedName("rootCause") val rootCause: String,
    @SerializedName("evidence") val evidence: List<String>,
    @SerializedName("relevantFiles") val relevantFiles: List<String>,
    @SerializedName("suggestedFix") val suggestedFix: String,
    @SerializedName("patchSuggestion") val patchSuggestion: String,
    @SerializedName("confidence") val confidence: String,
)

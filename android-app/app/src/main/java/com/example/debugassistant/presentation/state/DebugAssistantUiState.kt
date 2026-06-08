package com.example.debugassistant.presentation.state

import com.example.debugassistant.domain.model.DebugAnalysis

data class DebugAssistantUiState(
    val issueId: String = "",
    val isLoading: Boolean = false,
    val analysis: DebugAnalysis? = null,
    val errorMessage: String? = null,
)

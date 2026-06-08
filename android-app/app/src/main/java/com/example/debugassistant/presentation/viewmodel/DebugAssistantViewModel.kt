package com.example.debugassistant.presentation.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.debugassistant.domain.usecase.AnalyzeIssueUseCase
import com.example.debugassistant.presentation.state.DebugAssistantUiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class DebugAssistantViewModel(
    private val analyzeIssueUseCase: AnalyzeIssueUseCase,
) : ViewModel() {

    private val _uiState = MutableStateFlow(DebugAssistantUiState())
    val uiState: StateFlow<DebugAssistantUiState> = _uiState.asStateFlow()

    fun onIssueIdChange(issueId: String) {
        _uiState.update { it.copy(issueId = issueId) }
    }

    fun analyzeIssue() {
        val issueId = _uiState.value.issueId
        _uiState.update { it.copy(isLoading = true, errorMessage = null) }

        viewModelScope.launch {
            analyzeIssueUseCase(issueId)
                .onSuccess { analysis ->
                    _uiState.update {
                        it.copy(
                            analysis = analysis,
                            isLoading = false,
                            errorMessage = null,
                        )
                    }
                }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            errorMessage = error.message ?: "Failed to analyze issue",
                        )
                    }
                }
        }
    }
}

class DebugAssistantViewModelFactory(
    private val analyzeIssueUseCase: AnalyzeIssueUseCase,
) : ViewModelProvider.Factory {

    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(DebugAssistantViewModel::class.java)) {
            return DebugAssistantViewModel(analyzeIssueUseCase) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class: ${modelClass.name}")
    }
}

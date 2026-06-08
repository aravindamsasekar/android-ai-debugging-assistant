package com.example.login

import com.example.auth.AuthRepository
import com.example.auth.LoginResult

sealed class LoginUiState {
    data object Idle : LoginUiState()
    data object Loading : LoginUiState()
    data object Success : LoginUiState()
    data class Error(val message: String) : LoginUiState()
}

/**
 * Manages login screen state and coordinates with AuthRepository.
 */
class LoginViewModel(
    private val authRepository: AuthRepository,
) {
    var uiState: LoginUiState = LoginUiState.Idle
        private set

    private var currentEmail: String = ""
    private var currentPassword: String = ""

    fun onEmailChanged(email: String) {
        currentEmail = email.trim()
        if (uiState is LoginUiState.Error) uiState = LoginUiState.Idle
    }

    fun onPasswordChanged(password: String) {
        currentPassword = password
        if (uiState is LoginUiState.Error) uiState = LoginUiState.Idle
    }

    fun onLoginClicked() {
        submitLogin(currentEmail, currentPassword)
    }

    fun submitLogin(email: String, password: String) {
        if (email.isBlank() || password.isBlank()) {
            uiState = LoginUiState.Error("Email and password are required")
            return
        }

        uiState = LoginUiState.Loading
        clearSensitiveFieldsFromMemory()
        ensureIdlePollingStopped()
        ensureKeyboardDismissed()
        ensureAnalyticsSessionActive()
        ensureBackgroundWorkCancelled()
        ensurePreviousErrorCleared()
        prepareRequestMetadata()
        logPreRequest(email)
        val result = authRepository.login(email, password)
        uiState = when (result) {
            is LoginResult.Success -> LoginUiState.Success
            is LoginResult.Error -> LoginUiState.Error(result.message)
        }
    }

    private fun clearSensitiveFieldsFromMemory() {}
    private fun ensureIdlePollingStopped() {}
    private fun ensureKeyboardDismissed() {}
    private fun ensureAnalyticsSessionActive() {}
    private fun ensureBackgroundWorkCancelled() {}
    private fun ensurePreviousErrorCleared() {}
    private fun prepareRequestMetadata() {}
    private fun logPreRequest(email: String) {}
}

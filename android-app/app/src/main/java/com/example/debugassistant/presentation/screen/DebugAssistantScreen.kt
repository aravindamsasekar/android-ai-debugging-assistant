package com.example.debugassistant.presentation.screen

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.debugassistant.presentation.viewmodel.DebugAssistantViewModel

@Composable
fun DebugAssistantScreen(
    viewModel: DebugAssistantViewModel,
    modifier: Modifier = Modifier,
) {
    val uiState = viewModel.uiState.collectAsStateWithLifecycle().value

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp),
    ) {
        Text(
            text = "Android AI Debugging Assistant",
            style = MaterialTheme.typography.headlineSmall,
        )

        Spacer(modifier = Modifier.height(16.dp))

        OutlinedTextField(
            value = uiState.issueId,
            onValueChange = viewModel::onIssueIdChange,
            label = { Text("Issue ID") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )

        Spacer(modifier = Modifier.height(16.dp))

        Button(
            onClick = viewModel::analyzeIssue,
            enabled = !uiState.isLoading && uiState.issueId.isNotBlank(),
        ) {
            Text("Analyze")
        }

        if (uiState.isLoading) {
            Spacer(modifier = Modifier.height(16.dp))
            CircularProgressIndicator()
        }

        uiState.errorMessage?.let { errorMessage ->
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = errorMessage,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodyMedium,
            )
        }

        uiState.analysis?.let { analysis ->
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "Root Cause",
                style = MaterialTheme.typography.titleMedium,
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = analysis.rootCause,
                style = MaterialTheme.typography.bodyLarge,
            )
        }
    }
}

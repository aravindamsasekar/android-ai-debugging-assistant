package com.example.debugassistant.presentation.screen

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
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
            .verticalScroll(rememberScrollState())
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
            SectionTitle("Root Cause")
            Text(
                text = analysis.rootCause,
                style = MaterialTheme.typography.bodyLarge,
            )

            Spacer(modifier = Modifier.height(16.dp))
            SectionTitle("Evidence")
            BulletList(analysis.evidence)

            Spacer(modifier = Modifier.height(16.dp))
            SectionTitle("Relevant Files")
            BulletList(analysis.relevantFiles)

            if (analysis.relevantCode.isNotEmpty()) {
                Spacer(modifier = Modifier.height(16.dp))
                SectionTitle("Relevant Code")
                analysis.relevantCode.forEach { codeSnippet ->
                    Text(
                        text = "File: ${codeSnippet.file}",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Bold,
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = formatHighlightedSnippet(codeSnippet.snippet),
                        style = MaterialTheme.typography.bodySmall,
                        fontFamily = FontFamily.Monospace,
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                }
            }

            Spacer(modifier = Modifier.height(16.dp))
            SectionTitle("Suggested Fix")
            Text(
                text = analysis.suggestedFix,
                style = MaterialTheme.typography.bodyLarge,
            )

            Spacer(modifier = Modifier.height(16.dp))
            SectionTitle("Patch Suggestion")
            Text(
                text = analysis.patchSuggestion,
                style = MaterialTheme.typography.bodyMedium,
            )

            Spacer(modifier = Modifier.height(16.dp))
            SectionTitle("Confidence")
            Text(
                text = analysis.confidence,
                style = MaterialTheme.typography.bodyLarge,
            )
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleMedium,
    )
    Spacer(modifier = Modifier.height(8.dp))
}

@Composable
private fun BulletList(items: List<String>) {
    items.forEach { item ->
        Text(
            text = "• $item",
            style = MaterialTheme.typography.bodyLarge,
        )
    }
}

private val BUG_LINE_INDICATORS = listOf(
    "!!",
    "Intentional bug",
    "addMigrations",
    "SocketTimeoutException",
)

private fun isBugIndicatorLine(line: String): Boolean =
    BUG_LINE_INDICATORS.any { indicator -> line.contains(indicator) }

private fun formatHighlightedSnippet(snippet: String): String =
    snippet.lineSequence()
        .joinToString("\n") { line ->
            if (isBugIndicatorLine(line)) ">>> $line" else line
        }

"""Android AI Debugging Assistant — backend skeleton (phase 1).

The Android app will send an issue ID; this API will eventually analyze crash logs,
screenshot summaries, and Kotlin code, then return root-cause analysis and fix
suggestions. This file is a minimal placeholder with mock responses only.
"""

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="Android AI Debugging Assistant Backend",
    version="0.1.0",
)


class HealthResponse(BaseModel):
    status: str
    message: str


class AnalyzeResponse(BaseModel):
    issue_id: str = Field(serialization_alias="issueId")
    root_cause: str = Field(serialization_alias="rootCause")
    evidence: list[str]
    relevant_files: list[str] = Field(serialization_alias="relevantFiles")
    suggested_fix: str = Field(serialization_alias="suggestedFix")
    patch_suggestion: str = Field(serialization_alias="patchSuggestion")
    confidence: str


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Liveness probe — confirms the API process is up and reachable."""
    return HealthResponse(status="ok", message="Backend is running")


# Future architecture (not implemented yet):
# 1. Receive issue_id from the Android app
# 2. Fetch issue context (description, crash log, screenshot summary)
# 3. Retrieve relevant Kotlin files (future: FAISS / embeddings)
# 4. Analyze with an LLM (OpenAI / Gemini)
# 5. Return a structured AnalyzeResponse


@app.get("/analyze/{issue_id}", response_model=AnalyzeResponse)
def analyze_issue(issue_id: str) -> AnalyzeResponse:
    """Placeholder analyze endpoint — returns static mock debugging output."""
    return AnalyzeResponse(
        issue_id=issue_id,
        root_cause="NullPointerException caused by force-unwrapping nullable value",
        evidence=[
            "Crash log points to UserMapper.kt:24",
            "Code contains dto.name!!",
        ],
        relevant_files=["UserMapper.kt", "UserRepository.kt"],
        suggested_fix="Replace force unwrap with null-safe handling",
        patch_suggestion='displayName = dto.name ?: "Unknown User"',
        confidence="High",
    )


# Run from the backend directory:
#   uvicorn main:app --reload
#
# Then verify:
#   GET http://127.0.0.1:8000/health
#   GET http://127.0.0.1:8000/analyze/sample-issue-123
#   OpenAPI docs: http://127.0.0.1:8000/docs

"""Android AI Debugging Assistant — backend skeleton.

The Android app sends an issue ID; this API loads mock issue data and crash logs,
parses stack traces, retrieves relevant Kotlin files, then returns root-cause
analysis and fix suggestions. Semantic search (FAISS/embeddings) and LLM analysis
are planned for later phases.
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.code_retriever import retrieve_relevant_code
from services.log_parser import parse_log

app = FastAPI(
    title="Android AI Debugging Assistant Backend",
    version="0.1.0",
)

BASE_DIR = Path(__file__).parent
ISSUES_DIR = BASE_DIR / "mock_data" / "issues"
LOGS_DIR = BASE_DIR / "mock_data" / "logs"


class HealthResponse(BaseModel):
    status: str
    message: str


class CodeSnippet(BaseModel):
    file: str
    snippet: str


class AnalyzeResponse(BaseModel):
    issue_id: str = Field(serialization_alias="issueId")
    root_cause: str = Field(serialization_alias="rootCause")
    evidence: list[str]
    relevant_files: list[str] = Field(serialization_alias="relevantFiles")
    relevant_code: list[CodeSnippet] = Field(
        serialization_alias="relevantCode",
        default_factory=list,
    )
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
# 3. Retrieve relevant Kotlin files (exact match done; FAISS / embeddings future)
# 4. Analyze with an LLM (OpenAI / Gemini)
# 5. Return a structured AnalyzeResponse


def _load_issue(issue_id: str) -> dict:
    issue_path = ISSUES_DIR / f"{issue_id}.json"
    if not issue_path.is_file():
        raise HTTPException(status_code=404, detail=f"Issue not found: {issue_id}")
    return json.loads(issue_path.read_text(encoding="utf-8"))


def _load_log(issue_id: str) -> str:
    log_path = LOGS_DIR / f"{issue_id}.log"
    if not log_path.is_file():
        raise HTTPException(status_code=404, detail=f"Log not found for issue: {issue_id}")
    return log_path.read_text(encoding="utf-8")


def _build_analyze_response(issue: dict, log_text: str) -> AnalyzeResponse:
    issue_id = issue["issueId"]
    parsed = parse_log(log_text)

    evidence = [issue["title"]]

    if parsed["exceptionType"]:
        evidence.append(f"Exception: {parsed['exceptionType']}")

    if parsed["crashFile"] and parsed["crashLine"] is not None:
        evidence.append(f"Crash location: {parsed['crashFile']}:{parsed['crashLine']}")

    if parsed["importantLine"]:
        evidence.append(parsed["importantLine"])

    retrieved_code = retrieve_relevant_code(
        crash_file=parsed["crashFile"],
        relevant_files=issue["relevantFiles"],
        crash_line=parsed["crashLine"],
    )
    for item in retrieved_code:
        evidence.append(f"Retrieved code: {item['file']}")

    relevant_code = [
        CodeSnippet(file=item["file"], snippet=item["snippet"])
        for item in retrieved_code
    ]

    return AnalyzeResponse(
        issue_id=issue_id,
        root_cause=issue["expectedRootCause"],
        evidence=evidence,
        relevant_files=issue["relevantFiles"],
        relevant_code=relevant_code,
        suggested_fix=issue["suggestedFix"],
        patch_suggestion=issue["patchSuggestion"],
        confidence=issue["confidence"],
    )


@app.get("/analyze/{issue_id}", response_model=AnalyzeResponse)
def analyze_issue(issue_id: str) -> AnalyzeResponse:
    """Load issue-specific mock data from JSON and log files."""
    issue = _load_issue(issue_id)
    log_text = _load_log(issue_id)
    return _build_analyze_response(issue, log_text)


# Run from the backend directory:
#   uvicorn main:app --reload --host 0.0.0.0 --port 8001
#
# Then verify:
#   GET http://127.0.0.1:8001/health
#   GET http://127.0.0.1:8001/analyze/ISSUE-101
#   OpenAPI docs: http://127.0.0.1:8001/docs

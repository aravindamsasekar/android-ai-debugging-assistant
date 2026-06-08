# Android AI Debugging Assistant

A full-stack prototype that investigates Android crashes by combining structured log parsing, hybrid code retrieval (exact + semantic), and LLM-generated root-cause analysis.

> **Demo scope:** This project uses a **bundled sample Kotlin codebase** and **mock issue/log files**. It is not connected to live crash reporting (Crashlytics, Sentry, etc.) or a production repository. Suitable for learning, demos, and portfolio use — not production deployment as-is.

---

## Problem Statement

When an Android app crashes, developers must correlate stack traces, issue context, and source code to find the root cause. That workflow is repetitive and time-consuming, especially when:

- The failing line is clear, but related code (mappers, repositories, data models) is spread across multiple files
- Stack traces alone do not surface all semantically related symbols
- Manual triage does not scale as issue volume grows

This prototype explores whether a **retrieval-augmented** pipeline — parse the log, retrieve relevant Kotlin code, then reason with an LLM — can produce useful debugging output from a simple issue ID.

---

## What the App Does

1. User enters a demo issue ID (`ISSUE-101`, `ISSUE-102`, or `ISSUE-103`) in the Android app
2. The app calls `GET /analyze/{issueId}` on the FastAPI backend
3. The backend loads mock issue metadata and a crash log, parses the stack trace, retrieves Kotlin code, and asks **OpenAI `gpt-4.1-mini`** for analysis
4. The app displays:
   - Root cause
   - Evidence
   - Relevant files and code snippets (suspected bug lines prefixed with `>>> `)
   - Suggested fix and patch suggestion
   - Confidence level

If the LLM is unavailable, the backend returns deterministic fallback values from the mock issue JSON.

---

## End-to-End Architecture

```
Android App
    ↓
Jetpack Compose UI
    ↓
ViewModel + StateFlow
    ↓
Repository + Retrofit
    ↓
FastAPI  GET /analyze/{issueId}
    ↓
Issue JSON + Crash Log
    ↓
Log Parser
    ↓
Hybrid Retrieval
    ├── Exact retrieval (crash file + relevant files)
    └── FAISS HNSW semantic search over code chunks
    ↓
OpenAI gpt-4.1-mini LLM Orchestrator
    ↓
Root Cause + Evidence + Suggested Fix + Patch
    ↓
Android Result Screen
```

### Repository layout

| Path | Purpose |
|------|---------|
| `android-app/` | Jetpack Compose client (MVVM + Clean Architecture) |
| `backend/` | FastAPI API and analysis pipeline |
| `backend/services/` | Log parsing, retrieval, embeddings, FAISS, LLM orchestration |
| `backend/mock_data/` | Demo issue JSON and crash logs |
| `backend/sample_codebase/` | Sample Kotlin files with intentional bugs |
| `backend/vector_store/` | Precomputed embeddings and FAISS index |

---

## AI / RAG Pipeline

The backend implements a retrieval-augmented generation (RAG) flow over a fixed sample codebase.

### 1. Log Parser (`services/log_parser.py`)

Extracts structured fields from Android crash logs:

| Field | Description |
|-------|-------------|
| `exceptionType` | e.g. `NullPointerException`, `SocketTimeoutException`, `IllegalStateException` |
| `crashFile` / `crashLine` | From `com.example.*` stack frames when present |
| `importantLine` | First line matching crash keywords (`FATAL`, `Exception`, etc.) |

### 2. Exact Retrieval (`services/code_retriever.py`)

Loads Kotlin files from `sample_codebase/` by:

- Crash file from the stack trace (with line-context snippet)
- Files listed in issue `relevantFiles`

Provides high-trust, file-level anchors for the crash site.

### 3. Code Chunking (`services/code_chunker.py`)

Splits Kotlin sources into symbol-level chunks (`class`, `function`, `data class`, etc.). Large symbols are windowed with overlap. Each chunk carries `chunkId`, `file`, `symbol`, line range, and `content`.

### 4. Embeddings (`services/embedding_service.py`)

- Model: `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional vectors)
- Output: `vector_store/chunks_with_embeddings.json`
- Chunk metadata is preserved for citation in retrieval results

### 5. FAISS HNSW Semantic Search (`services/faiss_service.py`)

- Index: `IndexHNSWFlat` (`M=32`, `efConstruction=40`, `efSearch=32`)
- Persisted at `vector_store/code_chunks.faiss`
- Query-time comparison via L2 distance (lower = closer semantic match)

### 6. Hybrid Retrieval + Ranking (`services/hybrid_retriever.py`)

Merges exact and semantic results:

| Strategy | Role |
|----------|------|
| **Exact** | Crash file and `relevantFiles` first — highest trust |
| **Semantic** | FAISS nearest-neighbor over embedded chunks |

**Ranking improvements:**

- Raw FAISS `score` = semantic distance (lower is better)
- `adjustedScore` applies debugging boosts: crash file (−0.30), relevant file (−0.20), symbol mentioned in issue text (−0.10)
- Weak unrelated matches (not crash/relevant file, distance > 1.35) are filtered out
- Exact file-level and semantic symbol-level results can coexist; exact wins on dedupe

### 7. OpenAI LLM Orchestration (`services/llm_orchestrator.py`)

- Model: `gpt-4.1-mini`, temperature `0.2`
- Primary: OpenAI **Responses API**; fallback: Chat Completions
- Prompt includes issue metadata, parsed log, and retrieved code blocks
- Returns JSON: `rootCause`, `evidence`, `suggestedFix`, `patchSuggestion`, `confidence`
- On API/parse failure: `build_fallback_analysis()` using mock issue fields

---

## Android Architecture

**Stack:** Kotlin, Jetpack Compose, MVVM, Retrofit, Gson, Coroutines, StateFlow

| Layer | Key files | Responsibility |
|-------|-----------|----------------|
| Presentation | `DebugAssistantScreen`, `DebugAssistantViewModel`, `DebugAssistantUiState` | UI, loading/error state, user input |
| Domain | `AnalyzeIssueUseCase`, `DebugAnalysis`, `DebugRepository` | Business logic, domain models |
| Data | `DebugApiService`, `RetrofitClient`, `DebugRepositoryImpl`, `AnalyzeResponseDto` | HTTP calls, DTO mapping |
| Wiring | `MainActivity` | Manual DI: repository → use case → view model |

**Flow:** User taps Analyze → ViewModel invokes use case → Retrofit calls `/analyze/{issueId}` → response mapped to domain model → Compose screen renders sections.

**Relevant Code UI:** Lines containing bug indicators (`!!`, `Intentional bug`, `addMigrations`, `SocketTimeoutException`) are prefixed with `>>> ` in monospace.

---

## Backend Architecture

**Stack:** FastAPI, Uvicorn, Pydantic, python-dotenv, OpenAI Python SDK

| Component | File | Role |
|-----------|------|------|
| API entrypoint | `main.py` | `GET /health`, `GET /analyze/{issue_id}` |
| Log parser | `services/log_parser.py` | Stack trace extraction |
| Code retriever | `services/code_retriever.py` | Exact file/snippet loading |
| Code chunker | `services/code_chunker.py` | Kotlin symbol chunking |
| Embedding service | `services/embedding_service.py` | Vector generation |
| FAISS service | `services/faiss_service.py` | Index build/load/search |
| Hybrid retriever | `services/hybrid_retriever.py` | Merge, rank, cap results |
| LLM orchestrator | `services/llm_orchestrator.py` | Prompt, OpenAI call, JSON parse, fallback |

**`/analyze/{issue_id}` pipeline:**

```
_load_issue() + _load_log()
    → parse_log()
    → hybrid_retrieve(top_k=5)
    → analyze_with_llm()
    → AnalyzeResponse JSON
```

**Response fields:** `issueId`, `rootCause`, `evidence`, `relevantFiles`, `relevantCode`, `suggestedFix`, `patchSuggestion`, `confidence`

---

## Demo Issue IDs

| Issue ID | Scenario | Bug theme |
|----------|----------|-----------|
| `ISSUE-101` | Profile screen crash | `NullPointerException` — force-unwrapping nullable name in `UserMapper.kt` |
| `ISSUE-102` | Slow-network login | `SocketTimeoutException` not mapped to user-friendly UI state |
| `ISSUE-103` | Post-upgrade crash | Room database version change without migration |

Mock data: `backend/mock_data/issues/ISSUE-*.json`, `backend/mock_data/logs/ISSUE-*.log`

---

## How to Run the Backend

### Prerequisites

- Python 3.12+ recommended (use 3.12 if `sentence-transformers` fails on newer Python)
- OpenAI API key

### Setup

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

Create `backend/.env`:

```env
OPENAI_API_KEY=your_key_here
```

Prebuilt vector artifacts are in `backend/vector_store/`. To rebuild:

```bash
python -c "from services.embedding_service import build_embeddings_for_codebase; build_embeddings_for_codebase()"
python -c "from services.faiss_service import build_and_save_faiss_index; build_and_save_faiss_index()"
```

### Start server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

Verify:

```bash
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/analyze/ISSUE-101
```

OpenAPI docs: `http://127.0.0.1:8001/docs`

> Restart uvicorn after pulling code changes. A stale process may serve outdated responses.

First `/analyze` request may take 20–30 seconds while embedding and FAISS models load.

---

## How to Run the Android App

### Prerequisites

- Android Studio (recent version)
- Device or emulator (API 26+)
- Backend reachable on your LAN

### Setup

1. Open `android-app/` in Android Studio
2. Set your machine's LAN IP in `RetrofitClient.kt`:

```kotlin
private const val BASE_URL = "http://<YOUR_LAN_IP>:8001/"
```

3. `INTERNET` permission and cleartext HTTP are already configured for local dev

### Run

1. Start the backend on port `8001`
2. Confirm `http://<YOUR_LAN_IP>:8001/health` responds from the device
3. Run the app from Android Studio
4. Enter `ISSUE-101`, `ISSUE-102`, or `ISSUE-103` and tap **Analyze**

---

## Screenshots

<!-- Add screenshots after running the demo -->

| Analyze screen | Analysis result |
|----------------|-----------------|
| _Placeholder_ | _Placeholder_ |

---

## API Example

**Request:** `GET /analyze/ISSUE-101`

**Response shape:**

```json
{
  "issueId": "ISSUE-101",
  "rootCause": "...",
  "evidence": ["..."],
  "relevantFiles": ["UserMapper.kt", "UserRepository.kt"],
  "relevantCode": [
    { "file": "UserMapper.kt", "snippet": "..." }
  ],
  "suggestedFix": "...",
  "patchSuggestion": "...",
  "confidence": "High"
}
```

---

## Current Limitations

- **Mock data only** — issue metadata and logs are static files, not live crash reports
- **Fixed codebase** — retrieval searches `sample_codebase/`, not an arbitrary project repo
- **Local dev API** — no authentication; HTTP cleartext for LAN testing
- **Approximate search** — FAISS HNSW trades exact recall for speed
- **LLM dependency** — output quality and availability depend on OpenAI API key and network
- **Single-model stack** — one embedding model and one LLM; no evaluation harness or A/B testing
- **Manual Android config** — backend IP is hardcoded in `RetrofitClient.kt`

---

## Future Improvements

- Ingest real crash reports from Crashlytics, Sentry, or internal tooling
- Index an actual app repository (Git integration, incremental re-indexing)
- Richer ranking signals (crash-line proximity, recency, test coverage)
- Streaming LLM responses and citation links to exact file/line
- Authentication and HTTPS for non-local deployments
- Hilt/DI on Android; configurable backend URL (build flavors)
- Evaluation dataset with expected root causes and retrieval metrics
- Support for additional exception types and multi-module codebases

---

## Tech Stack

| Layer | Technologies |
|-------|----------------|
| Android | Kotlin, Jetpack Compose, MVVM, Retrofit, Gson, Coroutines, StateFlow |
| Backend | FastAPI, Uvicorn, Pydantic |
| Retrieval | sentence-transformers, faiss-cpu |
| LLM | OpenAI Python SDK (`gpt-4.1-mini`) |

---

## License

Add your license here.

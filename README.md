# Android AI Debugging Assistant

An end-to-end prototype that helps Android developers investigate crashes by combining crash-log parsing, Kotlin code retrieval, semantic search, and LLM-generated analysis.

The Android app sends an **issue ID** to a FastAPI backend. The backend loads mock issue metadata and crash logs, retrieves relevant Kotlin code, and returns structured debugging output: root cause, evidence, relevant code snippets, suggested fix, patch suggestion, and confidence.

> **Scope note:** This project uses a **sample Kotlin codebase** and **mock issue/log files** for demonstration. It is not connected to a live crash reporting system (Firebase Crashlytics, Sentry, etc.) or a production app repository.

---

## What It Does

Given an issue such as `ISSUE-101`, the system:

1. Loads issue context (title, description, relevant files) and a crash log
2. Parses the stack trace for exception type, crash file, and line number
3. Retrieves code using **exact file matching** and **FAISS semantic search**
4. Sends retrieved context to **OpenAI `gpt-4.1-mini`** for analysis
5. Returns a structured JSON response displayed in the Android UI

If the LLM is unavailable (missing API key, network error, invalid JSON), the backend falls back to deterministic values from the mock issue JSON.

---

## Architecture

End-to-end request flow:

```
Android App
    ↓
Compose UI
    ↓
ViewModel + StateFlow
    ↓
Repository + Retrofit
    ↓
FastAPI /analyze/{issueId}
    ↓
Issue JSON + Crash Log
    ↓
Log Parser
    ↓
Hybrid Retrieval
    ├── Exact Retrieval from crash file / relevant files
    └── FAISS HNSW Semantic Search over code chunks
    ↓
OpenAI gpt-4.1-mini LLM Orchestrator
    ↓
Root Cause + Evidence + Suggested Fix + Patch
    ↓
Android Result Screen
```

### Key backend components

| Component | File | Role |
|-----------|------|------|
| API entrypoint | `main.py` | Loads mock data, orchestrates pipeline, returns `AnalyzeResponse` |
| Log parser | `services/log_parser.py` | Extracts exception, crash file/line, important log line |
| Code chunker | `services/code_chunker.py` | Splits sample Kotlin files into symbol-level chunks |
| Embedding service | `services/embedding_service.py` | Generates 384-dim vectors (`all-MiniLM-L6-v2`) |
| FAISS service | `services/faiss_service.py` | HNSW index build, load, and semantic search |
| Hybrid retriever | `services/hybrid_retriever.py` | Merges exact + semantic retrieval results |
| LLM orchestrator | `services/llm_orchestrator.py` | Builds prompt, calls OpenAI, parses JSON, fallback |
| Mock data | `mock_data/issues/`, `mock_data/logs/` | Demo issue metadata and crash logs |
| Sample codebase | `sample_codebase/` | Kotlin files with intentional bugs for retrieval |
| Vector store | `vector_store/` | Precomputed embeddings and FAISS index |

### Key Android components

| Layer | Components | Role |
|-------|------------|------|
| Presentation | `DebugAssistantScreen`, `DebugAssistantViewModel`, `DebugAssistantUiState` | UI, state, user actions |
| Domain | `AnalyzeIssueUseCase`, `DebugAnalysis`, `DebugRepository` | Business logic and models |
| Data | `DebugApiService`, `RetrofitClient`, `DebugRepositoryImpl`, `AnalyzeResponseDto` | HTTP client and DTO mapping |
| Wiring | `MainActivity` | Manual DI: repository → use case → view model |

### Demo issue IDs

| Issue ID | Scenario |
|----------|----------|
| `ISSUE-101` | Profile crash — `NullPointerException` from force-unwrapping nullable name |
| `ISSUE-102` | Login timeout — `SocketTimeoutException` not mapped to UI error state |
| `ISSUE-103` | DB upgrade crash — Room version change without migration |

### Repository layout

| Path | Purpose |
|------|---------|
| `android-app/` | Jetpack Compose client (MVVM + Clean Architecture) |
| `backend/` | FastAPI API and analysis pipeline |
| `backend/services/` | Log parsing, retrieval, embeddings, FAISS, LLM orchestration |
| `backend/mock_data/` | Demo issue JSON files and crash logs |
| `backend/sample_codebase/` | Sample Kotlin files with intentional bugs |
| `backend/vector_store/` | Precomputed embeddings and FAISS index |

---

## Android App Flow

**Stack:** Kotlin, Jetpack Compose, MVVM, Retrofit, Gson, Coroutines, StateFlow

1. User enters an issue ID (e.g. `ISSUE-101`) and taps **Analyze**
2. `DebugAssistantViewModel` calls `AnalyzeIssueUseCase`
3. `DebugRepositoryImpl` requests `GET /analyze/{issueId}` via Retrofit
4. Response is mapped to domain models and shown in `DebugAssistantScreen`

**Layers:**

- **Presentation:** `DebugAssistantScreen`, `DebugAssistantViewModel`, `DebugAssistantUiState`
- **Domain:** `AnalyzeIssueUseCase`, `DebugAnalysis`, `DebugRepository`
- **Data:** `DebugApiService`, `RetrofitClient`, `AnalyzeResponseDto`, `DebugRepositoryImpl`

**Dependency injection:** Manual wiring in `MainActivity` (no Hilt/Koin).

**Relevant Code UI:** Suspected bug lines (e.g. containing `!!`, `Intentional bug`) are prefixed with `>>> ` in monospace for easier scanning.

---

## Backend Flow

**Endpoint:** `GET /analyze/{issue_id}`

```
issue JSON + crash log
        │
        ▼
   parse_log()
        │
        ▼
 hybrid_retrieve(top_k=5)
   ├── exact retrieval (crash file + relevant files)
   └── FAISS semantic search
        │
        ▼
 analyze_with_llm()
   ├── build context + prompt
   ├── OpenAI Responses API (gpt-4.1-mini)
   └── parse JSON (fallback on failure)
        │
        ▼
   AnalyzeResponse
```

**Other endpoint:** `GET /health` — liveness check

**Response fields:** `issueId`, `rootCause`, `evidence`, `relevantFiles`, `relevantCode`, `suggestedFix`, `patchSuggestion`, `confidence`

---

## Pipeline Components

### Log Parser (`services/log_parser.py`)

Extracts structured fields from Android crash logs:

- `exceptionType` — e.g. `NullPointerException`, `SocketTimeoutException`, `IllegalStateException`
- `crashFile` / `crashLine` — from `com.example.*` stack frames when present
- `importantLine` — first line containing crash-relevant keywords (`FATAL`, `Exception`, etc.)

### Code Chunking (`services/code_chunker.py`)

Splits Kotlin files in `sample_codebase/` into symbol-level chunks:

- Targets: `data class`, `class`, `object`, `interface`, `function`
- Large chunks are split into overlapping windows
- Output metadata: `chunkId`, `file`, `type`, `symbol`, `startLine`, `endLine`, `content`

### Embeddings (`services/embedding_service.py`)

- Model: `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional vectors)
- Embeds code chunks and stores them in `vector_store/chunks_with_embeddings.json`
- Metadata is preserved alongside each embedding for citation in retrieval results

### FAISS HNSW Semantic Search (`services/faiss_service.py`)

- Index type: `IndexHNSWFlat` (approximate nearest-neighbor search)
- Parameters: `M=32`, `efConstruction=40`, `efSearch=32`
- Persists index to `vector_store/code_chunks.faiss`
- Query embeddings are compared via L2 distance (lower = closer match)

### Hybrid Retrieval (`services/hybrid_retriever.py`)

Combines two strategies:

| Source | Strength |
|--------|----------|
| **Exact** | Anchors on crash file from stack trace and issue `relevantFiles` |
| **Semantic** | Finds related symbols by meaning (e.g. nullable name handling) |

Results are deduplicated, exact matches are kept first, semantic matches follow sorted by score, capped at `top_k`.

### OpenAI LLM Orchestration (`services/llm_orchestrator.py`)

- Model: `gpt-4.1-mini`, temperature `0.2`
- Primary API: OpenAI **Responses API** (`client.responses.create`)
- Fallback API: Chat Completions if Responses API fails
- Prompt includes issue metadata, parsed log fields, and retrieved code blocks
- Returns JSON: `rootCause`, `evidence`, `suggestedFix`, `patchSuggestion`, `confidence`
- On failure, returns mock issue fields via `build_fallback_analysis()`

---

## Screenshots

<!-- Add screenshots after running the demo -->

| Home / Analyze | Analysis Result |
|----------------|-----------------|
| _Screenshot placeholder_ | _Screenshot placeholder_ |

_Suggested captures: issue ID input, root cause + evidence, relevant code with `>>> ` bug-line highlighting._

---

## Setup

### Prerequisites

**Backend**

- Python 3.12+ recommended (3.14 may work; use 3.12 if `sentence-transformers` install fails)
- OpenAI API key

**Android**

- Android Studio (recent version)
- Physical device or emulator (API 26+)
- Device/emulator must reach the backend host on your LAN

### Backend setup

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

**Vector store (if rebuilding from scratch):**

```bash
cd backend
python -c "from services.embedding_service import build_embeddings_for_codebase; build_embeddings_for_codebase()"
python -c "from services.faiss_service import build_and_save_faiss_index; build_and_save_faiss_index()"
```

Prebuilt artifacts are already included in `backend/vector_store/` for the sample codebase.

### Android setup

1. Open `android-app/` in Android Studio
2. Update the backend base URL in `RetrofitClient.kt` to your machine's LAN IP:

```kotlin
private const val BASE_URL = "http://<YOUR_LAN_IP>:8001/"
```

Example: `http://192.168.0.103:8001/`

3. Ensure `INTERNET` permission and cleartext traffic are enabled (already configured in `AndroidManifest.xml` for local HTTP)

---

## How to Run

### Backend

From `backend/`:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

Verify:

```bash
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/analyze/ISSUE-101
```

OpenAPI docs: `http://127.0.0.1:8001/docs`

> **Important:** Restart uvicorn after pulling backend changes. A stale process may serve outdated mock responses (missing `relevantCode` or LLM analysis).

### Android app

1. Start the backend on port `8001`
2. Confirm the device can reach `http://<YOUR_LAN_IP>:8001/health`
3. Run the app from Android Studio on a device or emulator
4. Enter `ISSUE-101`, `ISSUE-102`, or `ISSUE-103` and tap **Analyze**

First analysis request may take 20–30 seconds while embedding and FAISS models warm up.

---

## API Example

**Request**

```
GET /analyze/ISSUE-101
```

**Response (shape)**

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

## Tech Stack

| Layer | Technologies |
|-------|----------------|
| Android | Kotlin, Jetpack Compose, MVVM, Retrofit, Gson, Coroutines |
| Backend | FastAPI, Uvicorn, Pydantic |
| Retrieval | sentence-transformers, faiss-cpu |
| LLM | OpenAI Python SDK (`gpt-4.1-mini`) |

---

## Limitations

- Issue and log data are **mock files**, not live crash reports
- Code retrieval targets the **bundled sample codebase**, not an arbitrary Git repo
- LLM output quality depends on retrieved context and API availability
- Semantic search uses approximate HNSW indexing (trade-off: speed vs. exact recall)
- No authentication on the API (local development only)

---

## License

Add your license here.

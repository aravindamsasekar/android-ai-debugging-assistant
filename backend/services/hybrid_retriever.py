"""Hybrid retrieval: exact crash-file matches plus FAISS semantic search.

Why hybrid retrieval is needed:
    Crash logs and issue metadata point to specific files and lines, but the
    root cause often spans related helpers, repositories, and data models that
    are not all named in the stack trace. Combining both strategies yields
    richer context than either approach alone.

Exact retrieval strengths:
    Stack traces provide a precise crash file and line number. Issue metadata
    adds known relevant files. This anchors debugging to the failure site.

Semantic retrieval strengths:
    Embedding search finds code by meaning, so related symbols (e.g.
    ``toDisplayName`` with ``dto.name!!``) surface even when the query does
    not quote the source verbatim.

Ranking:
    ``score`` is the raw FAISS L2 semantic distance (lower is better).
    ``adjustedScore`` subtracts debugging-specific boosts so crash-file and
    issue-relevant files rank above unrelated semantic matches. Crash file and
    relevant files are more trusted than distant unrelated chunks.

How the LLM will use merged results:
    The ranked list of file/symbol/content blocks is passed as debugging
    context so the LLM can reason across the crash site and semantically
    related code.

Verification example:
    from services.hybrid_retriever import hybrid_retrieve
    from services.log_parser import parse_log
    import json
    from pathlib import Path

    for issue_id in ("ISSUE-101", "ISSUE-102", "ISSUE-103"):
        issue = json.loads(Path(f"mock_data/issues/{issue_id}.json").read_text())
        log_text = Path(f"mock_data/logs/{issue_id}.log").read_text()
        parsed = parse_log(log_text)
        results = hybrid_retrieve(issue, parsed, top_k=5)
        for r in results:
            print(r["source"], r["file"], r["symbol"], r.get("adjustedScore", r["score"]))

    Expected ISSUE-101:
        exact UserMapper.kt
        exact UserRepository.kt
        semantic UserMapper / toDisplayName
        semantic UserRepository / getProfile
        DatabaseModule.kt should be filtered out or ranked lower

    Expected ISSUE-102:
        AuthRepository.kt, LoginViewModel.kt, AuthRepository / login

    Expected ISSUE-103:
        AppDatabase.kt, DatabaseModule.kt, AppDatabase / build
"""

from __future__ import annotations

from services.code_retriever import retrieve_relevant_code
from services.faiss_service import load_search_engine, search_similar_chunks

CRASH_FILE_BOOST = 0.30
RELEVANT_FILE_BOOST = 0.20
SYMBOL_MENTION_BOOST = 0.10
WEAK_SEMANTIC_THRESHOLD = 1.35


def _dedupe_key(file: str, symbol: str | None) -> str:
    return f"{file}:{symbol}" if symbol else file


def build_semantic_query(issue: dict, parsed_log: dict) -> str:
    """Build a text query from issue context and parsed crash log fields."""
    parts = [
        issue.get("title"),
        issue.get("description"),
        parsed_log.get("exceptionType"),
        parsed_log.get("crashFile"),
        parsed_log.get("importantLine"),
    ]
    return " ".join(part for part in parts if part)


def _symbol_mentioned_in_issue(symbol: str | None, issue: dict) -> bool:
    if not symbol:
        return False

    symbol_lower = symbol.lower()
    title = (issue.get("title") or "").lower()
    description = (issue.get("description") or "").lower()
    return symbol_lower in title or symbol_lower in description


def _compute_adjusted_score(item: dict, issue: dict, parsed_log: dict) -> float:
    adjusted = item["score"]
    crash_file = parsed_log.get("crashFile")
    relevant_files = issue.get("relevantFiles", [])

    if crash_file and item["file"] == crash_file:
        adjusted -= CRASH_FILE_BOOST

    if item["file"] in relevant_files:
        adjusted -= RELEVANT_FILE_BOOST

    if _symbol_mentioned_in_issue(item.get("symbol"), issue):
        adjusted -= SYMBOL_MENTION_BOOST

    return adjusted


def _is_weak_semantic_match(item: dict, issue: dict, parsed_log: dict) -> bool:
    crash_file = parsed_log.get("crashFile")
    relevant_files = issue.get("relevantFiles", [])

    if item["file"] == crash_file:
        return False

    if item["file"] in relevant_files:
        return False

    return item["score"] > WEAK_SEMANTIC_THRESHOLD


def _apply_semantic_ranking(
    semantic_raw: list[dict],
    issue: dict,
    parsed_log: dict,
) -> list[dict]:
    ranked: list[dict] = []

    for item in semantic_raw:
        if _is_weak_semantic_match(item, issue, parsed_log):
            continue

        ranked.append(
            {
                "file": item["file"],
                "symbol": item["symbol"],
                "startLine": item["startLine"],
                "endLine": item["endLine"],
                "content": item["content"],
                "source": "semantic",
                "score": item["score"],
                "adjustedScore": _compute_adjusted_score(item, issue, parsed_log),
            }
        )

    return ranked


def hybrid_retrieve(
    issue: dict,
    parsed_log: dict,
    top_k: int = 5,
) -> list[dict]:
    """Combine exact and semantic retrieval into a deduplicated result list."""
    exact_raw = retrieve_relevant_code(
        crash_file=parsed_log.get("crashFile"),
        relevant_files=issue.get("relevantFiles", []),
        crash_line=parsed_log.get("crashLine"),
    )

    exact_results = [
        {
            "file": item["file"],
            "symbol": None,
            "startLine": None,
            "endLine": None,
            "content": item["snippet"],
            "source": "exact",
            "score": 0.0,
        }
        for item in exact_raw
    ]

    index, chunks = load_search_engine()
    query = build_semantic_query(issue, parsed_log)
    faiss_top_k = min(top_k * 2, len(chunks))
    semantic_raw = search_similar_chunks(query, chunks, index, top_k=faiss_top_k)
    semantic_results = _apply_semantic_ranking(semantic_raw, issue, parsed_log)

    exact_keys = {_dedupe_key(r["file"], r["symbol"]) for r in exact_results}
    merged = list(exact_results)

    remaining_slots = top_k - len(merged)
    if remaining_slots <= 0:
        return merged[:top_k]

    filtered_semantic = [
        r
        for r in semantic_results
        if _dedupe_key(r["file"], r["symbol"]) not in exact_keys
    ]
    filtered_semantic.sort(key=lambda r: r["adjustedScore"])

    merged.extend(filtered_semantic[:remaining_slots])
    return merged[:top_k]

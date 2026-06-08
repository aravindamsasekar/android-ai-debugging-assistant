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

How the LLM will use merged results:
    In a later phase, the ranked list of file/symbol/content blocks will be
    passed as debugging context so the LLM can reason across the crash site
    and semantically related code.

Verification example:
    from services.hybrid_retriever import hybrid_retrieve
    from services.log_parser import parse_log
    import json
    from pathlib import Path

    issue = json.loads(Path("mock_data/issues/ISSUE-101.json").read_text())
    log_text = Path("mock_data/logs/ISSUE-101.log").read_text()
    parsed = parse_log(log_text)

    results = hybrid_retrieve(issue, parsed, top_k=5)

    for r in results:
        print(r["source"], r["file"], r["symbol"], r["score"])

    Expected:
        exact UserMapper.kt appears first
        exact UserRepository.kt appears near top
        semantic UserMapper/toDisplayName appears if not deduped
        semantic related chunks may follow
"""

from __future__ import annotations

from services.code_retriever import retrieve_relevant_code
from services.faiss_service import load_search_engine, search_similar_chunks


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
    semantic_raw = search_similar_chunks(query, chunks, index, top_k=top_k)

    semantic_results = [
        {
            "file": item["file"],
            "symbol": item["symbol"],
            "startLine": item["startLine"],
            "endLine": item["endLine"],
            "content": item["content"],
            "source": "semantic",
            "score": item["score"],
        }
        for item in semantic_raw
    ]

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
    filtered_semantic.sort(key=lambda r: r["score"])

    merged.extend(filtered_semantic[:remaining_slots])
    return merged[:top_k]

"""LLM orchestration for Android crash debugging analysis.

Why LLM orchestration is separate from main.py:
    Keeping prompts, API calls, JSON parsing, and fallback logic in a dedicated
    service lets the API layer stay thin and makes the analysis pipeline easy to
    test and swap (model, prompt, or provider) without touching routing code.

Why the prompt uses retrieved code context:
    Hybrid retrieval supplies exact crash-site snippets and semantically related
    Kotlin chunks. Grounding the model in that context reduces hallucinated file
    references and improves root-cause reasoning.

Why fallback exists:
    Missing API keys, network failures, or malformed model output must not break
    the debugging flow. Mock issue fields provide a deterministic safe default.

Phase 17 wiring:
    ``/analyze`` in main.py will call ``hybrid_retrieve()`` then
    ``analyze_with_llm()`` and map the returned dict into ``AnalyzeResponse``.

Verification example:
    from services.llm_orchestrator import analyze_with_llm
    from services.hybrid_retriever import hybrid_retrieve
    from services.log_parser import parse_log
    import json
    from pathlib import Path

    issue = json.loads(Path("mock_data/issues/ISSUE-101.json").read_text())
    log_text = Path("mock_data/logs/ISSUE-101.log").read_text()
    parsed = parse_log(log_text)
    retrieval = hybrid_retrieve(issue, parsed, top_k=5)

    result = analyze_with_llm(issue, parsed, retrieval)
    print(result)

    Expected:
        rootCause mentions nullable name force unwrap
        evidence mentions UserMapper.kt or dto.name!!
        suggestedFix mentions null-safe fallback
        patchSuggestion includes dto.name ?: "Unknown User"
        confidence is High/Medium/Low
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

MODEL = "gpt-4.1-mini"
TEMPERATURE = 0.2
REQUIRED_FIELDS = (
    "rootCause",
    "evidence",
    "suggestedFix",
    "patchSuggestion",
    "confidence",
)
VALID_CONFIDENCE = {"High", "Medium", "Low"}

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def build_llm_context(
    issue: dict,
    parsed_log: dict,
    retrieval_results: list[dict],
) -> str:
    """Build readable context from issue metadata, parsed log, and retrieved code."""
    lines = [
        "=== Issue ===",
        f"Issue ID: {issue.get('issueId', '')}",
        f"Title: {issue.get('title', '')}",
        f"Description: {issue.get('description', '')}",
        "",
        "=== Crash Log ===",
    ]

    if parsed_log.get("exceptionType"):
        lines.append(f"Exception Type: {parsed_log['exceptionType']}")
    if parsed_log.get("crashFile"):
        lines.append(f"Crash File: {parsed_log['crashFile']}")
    if parsed_log.get("crashLine") is not None:
        lines.append(f"Crash Line: {parsed_log['crashLine']}")
    if parsed_log.get("importantLine"):
        lines.append(f"Important Log Line: {parsed_log['importantLine']}")

    lines.append("")
    lines.append("=== Retrieved Code Context ===")

    for index, result in enumerate(retrieval_results, start=1):
        lines.append(f"--- Code Block {index} ---")
        lines.append(f"Source: {result.get('source', '')}")
        lines.append(f"File: {result.get('file', '')}")

        if result.get("symbol"):
            lines.append(f"Symbol: {result['symbol']}")

        start_line = result.get("startLine")
        end_line = result.get("endLine")
        if start_line is not None and end_line is not None:
            lines.append(f"Lines: {start_line}-{end_line}")

        lines.append("Content:")
        lines.append(result.get("content", ""))
        lines.append("")

    return "\n".join(lines).strip()


def build_analysis_prompt(context: str) -> str:
    """Build the user prompt instructing the model to return JSON analysis."""
    return f"""You are a senior Android debugging assistant.

Use ONLY the issue metadata, crash log details, and retrieved Kotlin code context provided below.
Do not invent files, symbols, or code that are not present in the context.
Base your root cause, evidence, and fix suggestions on the supplied information.

Return JSON only. Do not include markdown, explanations, or text outside the JSON object.

Required JSON schema:
{{
  "rootCause": "string",
  "evidence": ["string"],
  "suggestedFix": "string",
  "patchSuggestion": "string",
  "confidence": "High" | "Medium" | "Low"
}}

Context:
{context}
"""


def _strip_json_fences(raw_text: str) -> str:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        stripped = _JSON_FENCE_RE.sub("", stripped).strip()
    return stripped


def parse_llm_json(raw_text: str) -> dict:
    """Parse and validate JSON analysis from the model response."""
    if not raw_text or not raw_text.strip():
        raise ValueError("LLM response is empty")

    try:
        parsed = json.loads(_strip_json_fences(raw_text))
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object")

    missing = [field for field in REQUIRED_FIELDS if field not in parsed]
    if missing:
        raise ValueError(f"LLM response missing required fields: {', '.join(missing)}")

    evidence = parsed["evidence"]
    if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
        raise ValueError("LLM response field 'evidence' must be a list of strings")

    confidence = parsed["confidence"]
    if confidence not in VALID_CONFIDENCE:
        raise ValueError(
            f"LLM response field 'confidence' must be one of {sorted(VALID_CONFIDENCE)}"
        )

    for field in ("rootCause", "suggestedFix", "patchSuggestion"):
        if not isinstance(parsed[field], str) or not parsed[field].strip():
            raise ValueError(f"LLM response field '{field}' must be a non-empty string")

    return parsed


def build_fallback_analysis(issue: dict, parsed_log: dict) -> dict:
    """Return deterministic analysis from mock issue data when LLM fails."""
    evidence = [issue.get("title", "")]

    if parsed_log.get("exceptionType"):
        evidence.append(f"Exception: {parsed_log['exceptionType']}")

    crash_file = parsed_log.get("crashFile")
    crash_line = parsed_log.get("crashLine")
    if crash_file and crash_line is not None:
        evidence.append(f"Crash location: {crash_file}:{crash_line}")

    if parsed_log.get("importantLine"):
        evidence.append(parsed_log["importantLine"])

    return {
        "rootCause": issue.get("expectedRootCause", ""),
        "evidence": evidence,
        "suggestedFix": issue.get("suggestedFix", ""),
        "patchSuggestion": issue.get("patchSuggestion", ""),
        "confidence": issue.get("confidence", "Medium"),
    }


def _call_openai_responses(client: OpenAI, prompt: str) -> str:
    response = client.responses.create(
        model=MODEL,
        input=prompt,
        temperature=TEMPERATURE,
    )
    return response.output_text or ""


def _call_openai_chat_completions(client: OpenAI, prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        temperature=TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


def _call_openai(client: OpenAI, prompt: str) -> str:
    try:
        return _call_openai_responses(client, prompt)
    except Exception:
        return _call_openai_chat_completions(client, prompt)


def analyze_with_llm(
    issue: dict,
    parsed_log: dict,
    retrieval_results: list[dict],
) -> dict:
    """Generate debugging analysis using OpenAI, with fallback on failure."""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return build_fallback_analysis(issue, parsed_log)

        context = build_llm_context(issue, parsed_log, retrieval_results)
        prompt = build_analysis_prompt(context)

        client = OpenAI(api_key=api_key)
        raw_text = _call_openai(client, prompt)
        return parse_llm_json(raw_text)
    except (ValueError, Exception):
        return build_fallback_analysis(issue, parsed_log)

"""Exact file-based retrieval of Kotlin source from the sample codebase."""

from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SAMPLE_CODEBASE_DIR = BASE_DIR / "sample_codebase"
CONTEXT_LINES = 8
DEFAULT_LINES = 15


def load_file_content(file_name: str) -> dict | None:
    if not file_name.endswith(".kt"):
        return None

    file_path = SAMPLE_CODEBASE_DIR / file_name
    if not file_path.is_file():
        return None

    content = file_path.read_text(encoding="utf-8")
    return {
        "file": file_name,
        "content": content,
    }


def extract_relevant_snippet(
    file_name: str,
    content: str,
    crash_line: int | None,
) -> str:
    lines = content.splitlines()

    if crash_line is not None and crash_line >= 1:
        start = max(0, crash_line - CONTEXT_LINES - 1)
        end = min(len(lines), crash_line + CONTEXT_LINES)
        return "\n".join(lines[start:end])

    return "\n".join(lines[:DEFAULT_LINES])


def retrieve_relevant_code(
    crash_file: str | None,
    relevant_files: list[str],
    crash_line: int | None = None,
) -> list[dict]:
    seen: set[str] = set()
    results: list[dict] = []

    ordered_files: list[str] = []
    if crash_file:
        ordered_files.append(crash_file)
    ordered_files.extend(relevant_files)

    for file_name in ordered_files:
        if not file_name or file_name in seen:
            continue
        seen.add(file_name)

        loaded = load_file_content(file_name)
        if loaded is None:
            continue

        line_for_snippet = crash_line if file_name == crash_file else None
        snippet = extract_relevant_snippet(
            file_name=file_name,
            content=loaded["content"],
            crash_line=line_for_snippet,
        )
        results.append({
            "file": file_name,
            "snippet": snippet,
        })

    return results

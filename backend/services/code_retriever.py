"""Exact file-based retrieval of Kotlin source from the sample codebase."""

from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SAMPLE_CODEBASE_DIR = BASE_DIR / "sample_codebase"
MAX_CONTENT_CHARS = 1200


def load_file_content(file_name: str) -> dict | None:
    if not file_name.endswith(".kt"):
        return None

    file_path = SAMPLE_CODEBASE_DIR / file_name
    if not file_path.is_file():
        return None

    content = file_path.read_text(encoding="utf-8")
    return {
        "file": file_name,
        "content": content[:MAX_CONTENT_CHARS],
    }


def retrieve_relevant_code(
    crash_file: str | None,
    relevant_files: list[str],
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
        if loaded is not None:
            results.append(loaded)

    return results

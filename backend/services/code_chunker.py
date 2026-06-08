"""Kotlin source chunking for scalable code retrieval.

Why chunking is needed:
    Full Kotlin files are often too large for embedding models and dilute retrieval
    signal. Smaller symbol-level chunks improve semantic search quality.

Why metadata is stored:
    Each chunk carries file name, symbol, type, and line range so future retrieval
    can filter by crash location, rank nearby code, and cite sources in LLM prompts.

How chunks will be used:
    chunk_codebase() output will be embedded and indexed in FAISS (future phase).
    At query time, relevant chunks are retrieved by similarity and passed to an
    LLM for root-cause analysis.

Future improvement:
    Replace regex/brace parsing with AST or tree-sitter for accurate Kotlin nesting.

Example chunk_file("UserMapper.kt", content) returns:
[
  {
    "chunkId": "UserMapper_UserDto_6_10",
    "file": "UserMapper.kt",
    "type": "data_class",
    "symbol": "UserDto",
    "startLine": 6,
    "endLine": 10,
    "content": "data class UserDto(\\n    val id: String,\\n..."
  },
  {
    "chunkId": "UserMapper_toDisplayName_20_26",
    "file": "UserMapper.kt",
    "type": "function",
    "symbol": "toDisplayName",
    "startLine": 20,
    "endLine": 26,
    "content": "    fun toDisplayName(dto: UserDto): String {\\n...\\n        val displayName = dto.name!!\\n..."
  },
  ...
]
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MAX_CHUNK_LINES = 150
SPLIT_CHUNK_SIZE = 100
OVERLAP_LINES = 20
SPLIT_STEP = SPLIT_CHUNK_SIZE - OVERLAP_LINES

_SYMBOL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^\s*(data\s+class)\s+(\w+)"), "data_class"),
    (re.compile(r"^\s*(sealed\s+class)\s+(\w+)"), "class"),
    (re.compile(r"^\s*(class)\s+(\w+)"), "class"),
    (re.compile(r"^\s*(object)\s+(\w+)"), "object"),
    (re.compile(r"^\s*(interface)\s+(\w+)"), "interface"),
    (re.compile(r"^\s*fun\s+(\w+)"), "function"),
]

_PARENT_TYPES = {"class", "object", "interface"}


@dataclass(frozen=True)
class SymbolBlock:
    type: str
    symbol: str
    start_line: int
    end_line: int


def _file_stem(file_name: str) -> str:
    return Path(file_name).stem


def _find_block_end(lines: list[str], start_index: int) -> int:
    """Return inclusive 0-based end index for a symbol starting at start_index."""
    paren_balance = 0
    brace_balance = 0
    paren_started = False
    brace_started = False

    for index in range(start_index, len(lines)):
        for char in lines[index]:
            if char == "(":
                paren_balance += 1
                paren_started = True
            elif char == ")":
                paren_balance -= 1
            elif char == "{":
                brace_balance += 1
                brace_started = True
            elif char == "}":
                brace_balance -= 1

        if brace_started and brace_balance == 0:
            return index
        if paren_started and not brace_started and paren_balance == 0:
            return index

    return len(lines) - 1


def _find_symbol_blocks(lines: list[str]) -> list[SymbolBlock]:
    blocks: list[SymbolBlock] = []

    for index, line in enumerate(lines):
        for pattern, symbol_type in _SYMBOL_PATTERNS:
            match = pattern.match(line)
            if not match:
                continue

            symbol = match.group(match.lastindex or 2)
            start_line = index + 1
            end_line = _find_block_end(lines, index) + 1
            blocks.append(
                SymbolBlock(
                    type=symbol_type,
                    symbol=symbol,
                    start_line=start_line,
                    end_line=end_line,
                )
            )
            break

    return blocks


def _contains_inner_function(parent: SymbolBlock, functions: list[SymbolBlock]) -> bool:
    return any(
        parent.start_line < function.start_line and function.end_line <= parent.end_line
        for function in functions
    )


def _filter_parent_blocks(blocks: list[SymbolBlock]) -> list[SymbolBlock]:
    """Keep data_class chunks always; skip parent class/object/interface with inner fun."""
    functions = [block for block in blocks if block.type == "function"]
    filtered: list[SymbolBlock] = []

    for block in blocks:
        if block.type == "data_class":
            filtered.append(block)
            continue

        if block.type in _PARENT_TYPES and _contains_inner_function(block, functions):
            continue

        filtered.append(block)

    return filtered


def _make_chunk_id(
    file_name: str,
    symbol: str,
    start_line: int,
    end_line: int,
    part: int | None = None,
) -> str:
    stem = _file_stem(file_name)
    chunk_id = f"{stem}_{symbol}_{start_line}_{end_line}"
    if part is not None:
        chunk_id = f"{chunk_id}_part{part}"
    return chunk_id


def _build_chunk(
    file_name: str,
    symbol_type: str,
    symbol: str,
    start_line: int,
    end_line: int,
    lines: list[str],
    part: int | None = None,
) -> dict:
    content = "\n".join(lines[start_line - 1 : end_line])
    return {
        "chunkId": _make_chunk_id(file_name, symbol, start_line, end_line, part),
        "file": file_name,
        "type": symbol_type,
        "symbol": symbol,
        "startLine": start_line,
        "endLine": end_line,
        "content": content,
    }


def _split_large_chunk(chunk: dict) -> list[dict]:
    content_lines = chunk["content"].splitlines()
    line_count = len(content_lines)

    if line_count <= MAX_CHUNK_LINES:
        return [chunk]

    split_chunks: list[dict] = []
    part = 1
    window_start = 0

    while window_start < line_count:
        window_end = min(window_start + SPLIT_CHUNK_SIZE, line_count)
        absolute_start = chunk["startLine"] + window_start
        absolute_end = chunk["startLine"] + window_end - 1

        split_chunks.append(
            {
                "chunkId": _make_chunk_id(
                    chunk["file"],
                    chunk["symbol"],
                    absolute_start,
                    absolute_end,
                    part,
                ),
                "file": chunk["file"],
                "type": chunk["type"],
                "symbol": chunk["symbol"],
                "startLine": absolute_start,
                "endLine": absolute_end,
                "content": "\n".join(content_lines[window_start:window_end]),
            }
        )

        if window_end >= line_count:
            break

        window_start += SPLIT_STEP
        part += 1

    return split_chunks


def chunk_file(file_name: str, content: str) -> list[dict]:
    """Chunk a single Kotlin file into symbol-level retrieval units."""
    if not file_name.endswith(".kt"):
        return []

    lines = content.splitlines()
    if not lines:
        return []

    symbol_blocks = _filter_parent_blocks(_find_symbol_blocks(lines))
    if not symbol_blocks:
        return [
            _build_chunk(
                file_name=file_name,
                symbol_type="file",
                symbol=_file_stem(file_name),
                start_line=1,
                end_line=len(lines),
                lines=lines,
            )
        ]

    chunks: list[dict] = []
    for block in symbol_blocks:
        chunk = _build_chunk(
            file_name=file_name,
            symbol_type=block.type,
            symbol=block.symbol,
            start_line=block.start_line,
            end_line=block.end_line,
            lines=lines,
        )
        chunks.extend(_split_large_chunk(chunk))

    return chunks


def chunk_codebase(codebase_dir: Path) -> list[dict]:
    """Recursively scan a directory and chunk all Kotlin source files."""
    all_chunks: list[dict] = []

    for file_path in sorted(codebase_dir.rglob("*.kt")):
        content = file_path.read_text(encoding="utf-8")
        all_chunks.extend(chunk_file(file_path.name, content))

    return all_chunks

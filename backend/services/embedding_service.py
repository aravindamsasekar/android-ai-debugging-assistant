"""Embedding generation for Kotlin code chunks.

Why embeddings are needed:
    Code chunks are text. Embeddings convert each chunk into a dense numeric vector
    so semantically similar code can be found even when wording differs.

How FAISS will use them:
    In a future phase, vectors will be loaded into a FAISS index. At query time, a
    crash-log or issue-description embedding is compared against stored chunk vectors
    to retrieve the most relevant Kotlin symbols.

Why metadata is preserved:
    Embeddings alone are not enough for debugging. Keeping chunkId, file, symbol,
    line range, and content allows filtering, citation, and crash-line proximity
    ranking without re-reading the full codebase.

Note:
    If dependency installation fails on very new Python versions, use Python 3.12.
"""

from __future__ import annotations

import json
from pathlib import Path

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "vector_store" / "chunks_with_embeddings.json"

_model = None


def load_embedding_model():
    """Load the sentence-transformers model once and reuse it."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def generate_embedding(text: str) -> list[float]:
    """Generate an embedding vector for a single text input."""
    model = load_embedding_model()
    vector = model.encode(text, convert_to_numpy=True)
    return vector.tolist()


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Generate embeddings for code chunks while preserving all metadata."""
    if not chunks:
        return []

    model = load_embedding_model()
    texts = [chunk["content"] for chunk in chunks]
    vectors = model.encode(texts, convert_to_numpy=True)

    embedded_chunks: list[dict] = []
    for chunk, vector in zip(chunks, vectors):
        item = dict(chunk)
        item["embedding"] = vector.tolist()
        embedded_chunks.append(item)

    return embedded_chunks


def save_embeddings(embedded_chunks: list[dict], output_file: Path) -> None:
    """Persist embedded chunks as JSON for future FAISS indexing."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as file:
        json.dump(embedded_chunks, file, indent=2)


def build_embeddings_for_codebase(
    codebase_dir: Path,
    output_file: Path | None = None,
) -> list[dict]:
    """Chunk a codebase, embed all chunks, and save the result to JSON."""
    from services.code_chunker import chunk_codebase

    output = output_file or DEFAULT_OUTPUT
    chunks = chunk_codebase(codebase_dir)
    embedded_chunks = embed_chunks(chunks)
    save_embeddings(embedded_chunks, output)
    return embedded_chunks

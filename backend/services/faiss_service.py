"""FAISS HNSW semantic search over embedded Kotlin code chunks.

Why FAISS is used:
    It provides fast nearest-neighbor search over large collections of embedding
    vectors, which is needed once a codebase contains far more chunks than can be
    scanned linearly at query time.

Why HNSW is used instead of IndexFlatL2:
    IndexFlatL2 performs exact brute-force search with O(n) cost per query.
    IndexHNSWFlat uses a hierarchical navigable small-world graph for approximate
    search that scales better as the codebase grows.

Exact retrieval vs semantic retrieval:
    Exact retrieval matches known file names and crash locations from issue metadata.
    Semantic retrieval matches meaning in embedding space, so a query like
    "nullable profile name force unwrap" can find `dto.name!!` even when the exact
    phrase is not present in the source text.

Future use:
    Hybrid retrieval will combine exact file matches with FAISS semantic results.
    The top-ranked chunks will later be passed to an LLM as debugging context.

Verification example:
    from services.faiss_service import (
        build_and_save_faiss_index,
        load_search_engine,
        search_similar_chunks,
    )

    build_and_save_faiss_index()
    index, chunks = load_search_engine()
    results = search_similar_chunks(
        "NullPointerException caused by nullable profile name force unwrap",
        chunks,
        index,
        top_k=5,
    )

    for r in results:
        print(r["chunkId"], r["file"], r["symbol"], r["score"])

    Expected:
        UserMapper_toDisplayName should appear near the top.
"""

from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np

BASE_DIR = Path(__file__).parent.parent
DEFAULT_EMBEDDINGS_FILE = BASE_DIR / "vector_store" / "chunks_with_embeddings.json"
DEFAULT_FAISS_INDEX_FILE = BASE_DIR / "vector_store" / "code_chunks.faiss"

HNSW_M = 32
HNSW_EF_CONSTRUCTION = 40
HNSW_EF_SEARCH = 32


def load_embedded_chunks(embeddings_file: Path) -> list[dict]:
    """Load embedded chunks from JSON."""
    if not embeddings_file.is_file():
        raise FileNotFoundError(f"Embeddings file not found: {embeddings_file}")

    with embeddings_file.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_faiss_index(embedded_chunks: list[dict]):
    """Build a FAISS HNSW index from embedded chunk vectors."""
    if not embedded_chunks:
        raise ValueError("No embedded chunks to index")

    vectors = np.array(
        [chunk["embedding"] for chunk in embedded_chunks],
        dtype=np.float32,
    )
    dimension = vectors.shape[1]

    index = faiss.IndexHNSWFlat(dimension, HNSW_M)
    index.hnsw.efConstruction = HNSW_EF_CONSTRUCTION
    index.hnsw.efSearch = HNSW_EF_SEARCH
    index.add(vectors)
    return index


def save_faiss_index(index, output_file: Path) -> None:
    """Persist a FAISS index to disk."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(output_file))


def load_faiss_index(index_file: Path):
    """Load a FAISS index from disk."""
    if not index_file.is_file():
        raise FileNotFoundError(f"FAISS index file not found: {index_file}")

    return faiss.read_index(str(index_file))


def build_and_save_faiss_index(
    embeddings_file: Path = DEFAULT_EMBEDDINGS_FILE,
    index_file: Path = DEFAULT_FAISS_INDEX_FILE,
):
    """Load embedded chunks, build the FAISS index, and save it."""
    embedded_chunks = load_embedded_chunks(embeddings_file)
    index = build_faiss_index(embedded_chunks)
    save_faiss_index(index, index_file)
    return index


def load_search_engine(
    embeddings_file: Path = DEFAULT_EMBEDDINGS_FILE,
    index_file: Path = DEFAULT_FAISS_INDEX_FILE,
) -> tuple:
    """Load embedded chunks and the matching FAISS index for search."""
    embedded_chunks = load_embedded_chunks(embeddings_file)
    index = load_faiss_index(index_file)

    if index.ntotal != len(embedded_chunks):
        raise ValueError(
            "FAISS index size does not match embedded chunks: "
            f"index.ntotal={index.ntotal}, chunks={len(embedded_chunks)}"
        )

    return index, embedded_chunks


def search_similar_chunks(
    query: str,
    embedded_chunks: list[dict],
    index,
    top_k: int = 5,
) -> list[dict]:
    """Search for the most semantically similar code chunks to a query."""
    from services.embedding_service import generate_embedding

    if not embedded_chunks:
        return []

    top_k = min(top_k, len(embedded_chunks))
    query_vector = np.array([generate_embedding(query)], dtype=np.float32)
    distances, indices = index.search(query_vector, top_k)

    results: list[dict] = []
    for distance, idx in zip(distances[0], indices[0]):
        if idx < 0:
            continue

        chunk = embedded_chunks[idx]
        results.append(
            {
                "chunkId": chunk["chunkId"],
                "file": chunk["file"],
                "type": chunk["type"],
                "symbol": chunk["symbol"],
                "startLine": chunk["startLine"],
                "endLine": chunk["endLine"],
                "content": chunk["content"],
                # L2 distance from IndexHNSWFlat: lower score means closer match.
                "score": float(distance),
            }
        )

    return results

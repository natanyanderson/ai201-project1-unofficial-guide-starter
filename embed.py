"""
embed_and_retrieve.py

Builds a semantic-search index for the Mercy CS RAG project:

  1. Pulls chunks from ingest.build_corpus()        -> [{text, source_url, metadata}, ...]
  2. Embeds each chunk with all-MiniLM-L6-v2         (sentence-transformers)
  3. Stores embeddings + metadata in ChromaDB        (local, persistent, cosine distance)
  4. Exposes retrieve(query, k=4)                    -> top-k chunks with text/metadata/url/distance

Run directly to (re)build the index and print retrieval results for three
verification queries.

    python embed_and_retrieve.py
"""

from __future__ import annotations

import chromadb
from sentence_transformers import SentenceTransformer

from ingest import build_corpus

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
MODEL_NAME = "all-MiniLM-L6-v2"
DB_PATH = "./chroma_db"          # persistent ChromaDB lives here
COLLECTION_NAME = "mercy_cs"
DEFAULT_K = 4

# Loaded once at import so retrieve() can be reused from other scripts without
# re-loading the model or reconnecting to the DB.
_model = SentenceTransformer(MODEL_NAME)
_client = chromadb.PersistentClient(path=DB_PATH)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _clean_metadata(meta: dict) -> dict:
    """ChromaDB only accepts str/int/float/bool metadata values.

    Drop None values (e.g. a Coursicle chunk has no `professor`) and stringify
    anything else (lists, etc.) so the add() call never blows up on a single
    odd field.
    """
    clean: dict = {}
    for key, value in (meta or {}).items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
        else:
            clean[key] = str(value)
    return clean


def _warn_on_truncation(chunks: list[dict]) -> None:
    """all-MiniLM-L6-v2 truncates input at max_seq_length (256) word-pieces.

    Anything longer is silently cut before embedding, which is exactly the risk
    flagged in the planning doc for the multi-line semester blocks. Surface it
    here so you can see during verification whether it's actually happening.
    """
    max_seq = _model.max_seq_length
    tokenizer = _model.tokenizer
    oversized = []
    for i, c in enumerate(chunks):
        n_tokens = len(tokenizer.encode(c["text"], add_special_tokens=True))
        if n_tokens > max_seq:
            oversized.append((i, n_tokens, c.get("source_url", "")))

    if oversized:
        print(
            f"WARNING: {len(oversized)} of {len(chunks)} chunk(s) exceed the "
            f"model's {max_seq}-token limit and will be TRUNCATED before embedding:"
        )
        for idx, n, url in oversized:
            print(f"    chunk_{idx}: {n} tokens  ({url})")
        print()
    else:
        print(f"All {len(chunks)} chunks fit within the {max_seq}-token limit.\n")


# ----------------------------------------------------------------------------
# Index build
# ----------------------------------------------------------------------------
def build_index(rebuild: bool = True) -> "chromadb.Collection":
    """Embed the corpus and (re)populate the ChromaDB collection.

    rebuild=True drops any existing collection first so each run starts clean
    and you never get duplicate IDs. 124 chunks re-embed in a few seconds.
    """
    chunks = build_corpus()
    print(f"build_corpus() returned {len(chunks)} chunks.")
    _warn_on_truncation(chunks)

    if rebuild:
        try:
            _client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass  # collection didn't exist yet -> nothing to delete

    # Cosine distance is the right metric for normalized MiniLM embeddings;
    # without this Chroma defaults to squared-L2, which is harder to read.
    collection = _client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    texts = [c["text"] for c in chunks]
    embeddings = _model.encode(
        texts, show_progress_bar=True, convert_to_numpy=True
    ).tolist()

    ids = [f"chunk_{i}" for i in range(len(chunks))]
    metadatas = []
    for c in chunks:
        meta = _clean_metadata(c.get("metadata", {}))
        # Keep source_url inside metadata so it round-trips through Chroma;
        # retrieve() splits it back out.
        meta["source_url"] = c.get("source_url", "")
        metadatas.append(meta)

    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    print(f"Indexed {collection.count()} chunks into '{COLLECTION_NAME}'.\n")
    return collection


# ----------------------------------------------------------------------------
# Retrieval
# ----------------------------------------------------------------------------
def retrieve(query: str, k: int = DEFAULT_K) -> list[dict]:
    """Embed `query` and return the top-k most similar chunks.

    Each result: {text, metadata, source_url, distance}.
    Lower distance = more similar (cosine distance, 0 = identical).
    """
    collection = _client.get_collection(COLLECTION_NAME)
    query_embedding = _model.encode([query], convert_to_numpy=True).tolist()

    res = collection.query(query_embeddings=query_embedding, n_results=k)

    results = []
    n = len(res["ids"][0])
    for i in range(n):
        meta = dict(res["metadatas"][0][i] or {})
        source_url = meta.pop("source_url", "")  # pull url back out of metadata
        results.append(
            {
                "text": res["documents"][0][i],
                "metadata": meta,
                "source_url": source_url,
                "distance": res["distances"][0][i],
            }
        )
    return results


# ----------------------------------------------------------------------------
# Verification harness
# ----------------------------------------------------------------------------
def _print_results(query: str, results: list[dict]) -> None:
    print("=" * 88)
    print(f"QUERY: {query}")
    print("=" * 88)
    for rank, r in enumerate(results, 1):
        print(f"\n[{rank}] distance={r['distance']:.4f}")
        print(f"    source_url: {r['source_url']}")
        print(f"    metadata:   {r['metadata']}")
        text = " ".join(r["text"].split())  # collapse whitespace for readability
        if len(text) > 600:
            text = text[:600] + " ...[truncated for display]"
        print(f"    text:       {text}")
    print()


if __name__ == "__main__":
    build_index(rebuild=True)

    test_queries = [
        "Who teaches Object Structure Algorithm I at Mercy and what do students say about them?",
        "What courses do I need in my second semester as a CS major?",
        "What is the prerequisite for Artificial Intelligence at Mercy?",
    ]

    for q in test_queries:
        _print_results(q, retrieve(q, k=DEFAULT_K))

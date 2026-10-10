"""retrieval.py — embedding-based retrieval for the Annizon RAG chatbot.

Upgraded from keyword search: every chunk and every question is turned into
an embedding vector (Gemini text-embedding-004); relevance = dot product.
Same interface as before: find_relevant(question, top_k=3) -> top chunks.

How it works:
- Chunk vectors are embedded ONCE per app lifetime (one batch API call for
  all chunks) and cached in-process. Re-ingesting chunks.json takes effect
  on the next app restart.
- Each question costs one small embedContent call, then pure-Python dot
  products.
- If the embedding API is ever down, it falls back to the old keyword
  overlap scorer so the bot stays alive (worst case = today's behavior).

Needs GEMINI_API_KEY in the environment (same key the chatbot already uses).
"""
import json
import os
from functools import lru_cache
from pathlib import Path

import requests

EMBED_MODEL = "text-embedding-004"
EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
    f"/models/{EMBED_MODEL}:embedContent"
)
BATCH_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
    f"/models/{EMBED_MODEL}:batchEmbedContents"
)

# chunks.json sits next to this file (written by ingest.py, committed to git)
CHUNKS_PATH = Path(__file__).parent / "chunks.json"


def _headers():
    return {
        "x-goog-api-key": os.environ["GEMINI_API_KEY"],
        "Content-Type": "application/json",
    }


def _embed_one(text):
    """Embed a single text (used for the live question)."""
    r = requests.post(
        EMBED_URL,
        headers=_headers(),
        json={"content": {"parts": [{"text": text}]}},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["embedding"]["values"]


def _embed_many(texts):
    """Embed many texts in ONE batch call (used for chunks, once per lifetime)."""
    r = requests.post(
        BATCH_URL,
        headers=_headers(),
        json={
            "requests": [
                {
                    "model": f"models/{EMBED_MODEL}",
                    "content": {"parts": [{"text": t}]},
                }
                for t in texts
            ]
        },
        timeout=120,
    )
    r.raise_for_status()
    return [e["values"] for e in r.json()["embeddings"]]


@lru_cache(maxsize=1)
def _load_chunks():
    return json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _chunk_vectors():
    """Embed every chunk once; cached for the life of the process."""
    chunks = _load_chunks()
    return _embed_many([c["text"] for c in chunks])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _keyword_scored(question, chunks):
    """Old scorer, kept as the offline fallback."""
    q_words = set(question.lower().split())
    return [
        (len(q_words & set(c["text"].lower().split())), c) for c in chunks
    ]


def find_relevant(question, top_k=3):
    """Return the top_k most relevant chunks for question."""
    chunks = _load_chunks()
    try:
        vecs = _chunk_vectors()
        q_vec = _embed_one(question)
        scored = [(_dot(q_vec, v), c) for v, c in zip(vecs, chunks)]
    except Exception:
        # Embedding API down? Fall back to keyword overlap — bot stays alive.
        scored = _keyword_scored(question, chunks)
    scored.sort(key=lambda s: s[0], reverse=True)
    return [c for _, c in scored[:top_k]]

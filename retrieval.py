"""retrieval.py — embedding-based retrieval for the Annizon RAG chatbot.

Upgraded from keyword search: every chunk and every question is turned into
an embedding vector (Gemini text-embedding-004); relevance = dot product.
Same interface as before: find_relevant(question, top_k=3) -> top chunks.

How it works:
- Chunk vectors are embedded ONCE per store per app lifetime (one batch API
  call for all chunks) and cached in-process. Re-ingesting takes effect
  on the next app restart (or cache_clear).
- Multi-store: chunks live in chunks/<store_id>.json, one file per store.
  find_relevant(..., store_id="...") picks the right store. Falls back to
  the legacy chunks.json when no per-store file exists.
- Each question costs one small embedContent call, then pure-Python dot
  products.
- Three-layer fallback (never crashes, just gets dumber):
  1. Gemini embeddings (primary)
  2. Local sentence-transformers model (optional backup, no API needed)
  3. Keyword overlap (last resort)

Needs GEMINI_API_KEY in the environment (same key the chatbot already uses).
"""
import json
import math
import os
import re
from functools import lru_cache
from pathlib import Path

import requests

EMBED_MODEL = "gemini-embedding-001"  # text-embedding-004 was retired by Google
EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
    f"/models/{EMBED_MODEL}:embedContent"
)
BATCH_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
    f"/models/{EMBED_MODEL}:batchEmbedContents"
)
LOCAL_MODEL_NAME = "all-MiniLM-L6-v2"

# chunks.json sits next to this file (written by ingest.py, committed to git)
CHUNKS_PATH = Path(__file__).parent / "chunks.json"
# Multi-store: chunks/<store_id>.json, one file per store (written by crawler.py)
CHUNKS_DIR = Path(__file__).parent / "chunks"


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


@lru_cache(maxsize=32)
def _load_chunks(store_id="default"):
    """Load one store's chunks; falls back to legacy chunks.json."""
    path = CHUNKS_DIR / f"{store_id}.json"
    if not path.exists():
        path = CHUNKS_PATH
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=32)
def _chunk_vectors(store_id="default"):
    """Embed every chunk once per store; cached for the life of the process."""
    chunks = _load_chunks(store_id)
    return _embed_many([c["text"] for c in chunks])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _as_list(vec):
    """sentence-transformers returns numpy arrays; _dot wants plain lists."""
    return vec.tolist() if hasattr(vec, "tolist") else list(vec)


@lru_cache(maxsize=1)
def _local_model():
    """Lazily load the backup embedding model (ImportError if not installed)."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(LOCAL_MODEL_NAME)


@lru_cache(maxsize=32)
def _local_chunk_vectors(store_id="default"):
    """Embed every chunk with the LOCAL model (its own vector space)."""
    model = _local_model()
    chunks = _load_chunks(store_id)
    return [_as_list(v) for v in model.encode([c["text"] for c in chunks])]


def _local_scored(question, chunks, store_id="default"):
    """Score with the local backup model (no API key, no network needed)."""
    model = _local_model()
    q_vec = _as_list(model.encode(question))
    vecs = _local_chunk_vectors(store_id)
    return [(_dot(q_vec, v), c) for v, c in zip(vecs, chunks)]


_STOPWORDS = {
    "what", "is", "your", "the", "a", "an", "how", "long", "does", "do",
    "can", "i", "me", "my", "to", "of", "for", "and", "or", "in", "on",
    "it", "take", "takes",
    # Every page in this corpus IS a policy, so "policy" names no page -
    # left in, it made shipping questions match the privacy page, which
    # repeats the word most.
    "policy", "policies",
}


def _tokens(text):
    """Lowercase word tokens with punctuation stripped (policy? -> policy)."""
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS]


def _stem(word):
    """Crude stem: shipping / shipped / shipments all -> 'ship'.

    Needed because the policy chunks say 'shipped' and 'shipments' while
    customers ask about 'shipping' - exact-word matching scored the main
    shipping chunk 0 and the bot answered 'I don't know'.
    """
    return word[:4] if len(word) > 5 else word


def _keyword_scored(question, chunks):
    """Old scorer, kept as the offline fallback.

    Scores by how many of the question's meaningful word STEMS appear in
    the chunk (counted with repetition, so a chunk that talks about
    shipping five times beats one that mentions it once in passing).
    """
    q_stems = {_stem(w) for w in _tokens(question)}
    # Rarity weighting (IDF-lite): a stem found in nearly every chunk
    # ("policy" - privacy, terms and refund pages all repeat it) carries
    # almost no signal, while a rare stem ("ship") identifies its page.
    # Without this, "What is your shipping policy?" matched the privacy
    # chunks, which say "policy" far more often than the shipping page.
    chunk_stems = [[_stem(w) for w in _tokens(c["text"])] for c in chunks]
    n = max(len(chunks), 1)
    weights = {}
    for s in q_stems:
        df = sum(1 for stems in chunk_stems if s in stems)
        weights[s] = math.log(1 + n / max(df, 1))
    scored = []
    for stems, c in zip(chunk_stems, chunks):
        score = sum(weights[s] for s in stems if s in q_stems)
        scored.append((score, c))
    return scored


def find_relevant(question, top_k=3, store_id="default"):
    """Return the top_k most relevant chunks for question, from one store."""
    chunks = _load_chunks(store_id)
    try:
        vecs = _chunk_vectors(store_id)
        q_vec = _embed_one(question)
        scored = [(_dot(q_vec, v), c) for v, c in zip(vecs, chunks)]
    except Exception:
        try:
            # Gemini down? Local backup model — no API, no key needed.
            scored = _local_scored(question, chunks, store_id)
        except Exception:
            # Last resort: keyword overlap — bot stays alive.
            scored = _keyword_scored(question, chunks)
    scored.sort(key=lambda s: s[0], reverse=True)
    return [c for _, c in scored[:top_k]]

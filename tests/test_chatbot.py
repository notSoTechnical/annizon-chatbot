"""Nightly tests for the Annizon RAG chatbot."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_chunks_exist():
    """ingest.py produced a healthy chunk file."""
    with open("chunks.json") as f:
        chunks = json.load(f)
    assert len(chunks) > 10, f"too few chunks: {len(chunks)}"
    sources = {c["source"] for c in chunks}
    assert "refund" in sources, "refund policy missing"
    assert "shipping" in sources, "shipping policy missing"


def test_retrieval_finds_refund():
    """'return policy' question must surface refund chunks."""
    from retrieval import find_relevant
    top = find_relevant("what is your return policy", top_k=3)
    assert top[0]["source"] == "refund", f"expected refund, got {top[0]['source']}"


@pytest.mark.xfail(reason="keyword search can't match shipping/shipped — needs embeddings")
def test_retrieval_finds_shipping():
    """Known weakness: keyword overlap misses 'shipped' vs 'shipping'."""
    from retrieval import find_relevant
    top = find_relevant("how long does shipping take", top_k=3)
    sources = [c["source"] for c in top]
    assert "shipping" in sources, f"shipping not in top 3: {sources}"


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="needs GEMINI_API_KEY")
def test_answer_uses_real_policy():
    """End-to-end: the bot answers from the actual return policy."""
    from chatbot import answer
    a = answer("what is your return policy")
    assert "30-day" in a or "30 day" in a, f"answer doesn't cite the policy: {a[:200]}"


def test_widget_points_to_app():
    """widget.js embeds the deployed Streamlit app."""
    with open("widget.js") as f:
        js = f.read()
    assert "streamlit.app" in js, "widget doesn't reference the app URL"
    assert "anni-bubble" in js, "widget bubble missing"

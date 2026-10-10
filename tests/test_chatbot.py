"""Nightly tests for the Annizon RAG chatbot."""
import json
import os
import sys
from types import SimpleNamespace

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

@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="needs GEMINI_API_KEY")
def test_retrieval_finds_refund():
    """'return policy' question must surface refund chunks."""
    from retrieval import find_relevant
    top = find_relevant("what is your return policy", top_k=3)
    assert top[0]["source"] == "refund", f"expected refund, got {top[0]['source']}"


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="needs GEMINI_API_KEY")
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


def test_system_prompt_has_guardrail():
    """# 反幻觉防线第一道:系统提示词里必须有"不知道就承认"的规则
    # 不用调 API 就能跑 —— 纯粹检查代码里的那句话还在不在"""
    with open("chatbot.py", encoding="utf-8") as f:
        src = f.read().lower()
    assert "only" in src and "don't know" in src, "guardrail sentence missing from chatbot.py"


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="needs GEMINI_API_KEY")
def test_answer_refuses_out_of_policy():
    """# 反幻觉测试(Anni 自己的点子!):问政策里根本没有的东西,
    # 机器人必须说"不知道",而不是编一个答案"""
    from chatbot import answer
    a = answer("what is the capital of France").lower()
    refusal = ("don't know" in a or "do not know" in a
               or "cannot answer" in a or "can't answer" in a
               or "no information" in a)
    assert refusal, f"bot hallucinated instead of refusing: {a[:300]}"


def test_categorize_routes_with_stub_client():
    """AI triage: stub the LLM (no API key needed), check routing + fallbacks."""
    from triage import categorize, TEAMS

    class StubCompletions:
        def __init__(self, text):
            self.text = text

        def create(self, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=self.text))]
            )

    class StubClient:
        def __init__(self, text):
            self.chat = SimpleNamespace(completions=StubCompletions(text))

    team, category = categorize("where is my package, it's been a week", StubClient("shipping"))
    assert category == "shipping"
    assert team == TEAMS["other"]  # fake inboxes off → everything lands in info@

    team, category = categorize("whatever", StubClient("banana"))
    assert (category, team) == ("other", TEAMS["other"])  # weird output → safe fallback


def test_widget_points_to_app():
    """widget.js embeds the deployed Streamlit app."""
    with open("widget.js") as f:
        js = f.read()
    assert "streamlit.app" in js, "widget doesn't reference the app URL"
    assert "anni-bubble" in js, "widget bubble missing"

"""Tests for tools.py — the order-lookup tool (function calling demo).

No API key needed: lookup_order is pure Python over mock data, and the
tool loop is exercised with a stub client, same pattern as the triage
test in tests/test_chatbot.py.
"""
import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_lookup_order_found():
    """A known demo order id returns its status and tracking."""
    from tools import lookup_order
    r = lookup_order("A1001")
    assert r["found"] is True
    assert r["order_id"] == "A1001"
    assert r["tracking"], "shipped order should have a tracking number"
    assert r["carrier"], "shipped order should name a carrier"


def test_lookup_order_normalizes_input():
    """Messy customer typing (spaces, lowercase) still finds the order."""
    from tools import lookup_order
    assert lookup_order("  a1002 ")["found"] is True


def test_lookup_order_not_found():
    """Unknown id -> polite not-found dict, never an exception."""
    from tools import lookup_order
    r = lookup_order("ZZZ999")
    assert r["found"] is False
    assert "couldn't find" in r["message"]


def _message(content=None, tool_calls=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))]
    )


def _tool_call(order_id):
    return SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="lookup_order",
            arguments=json.dumps({"order_id": order_id}),
        ),
    )


class StubToolClient:
    """Pretends to be Gemini: first create() requests the tool call,
    second create() returns the final sentence. Records what it was fed."""

    def __init__(self, order_id="A1001"):
        self.calls = []
        outer = self

        class Completions:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                if len(outer.calls) == 1:
                    return _message(tool_calls=[_tool_call(order_id)])
                return _message(content="Your order A1001 is in transit with UPS.")

        self.chat = SimpleNamespace(completions=Completions())


def test_tool_loop_runs_lookup_and_answers():
    """Full loop: model requests tool -> our code runs it -> result fed
    back -> model produces the final answer."""
    from tools import answer_with_tools
    stub = StubToolClient()
    a = answer_with_tools("where is my order A1001", stub)
    assert a == "Your order A1001 is in transit with UPS."
    # the second API call must carry the tool result back to the model
    fed_back = stub.calls[1]["messages"][-1]
    assert fed_back["role"] == "tool"
    assert json.loads(fed_back["content"])["found"] is True


def test_tool_loop_skips_rag_questions():
    """No tool request from the model -> None, so app.py uses RAG."""
    from tools import answer_with_tools

    class PlainClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            return _message(content="some direct text")

    assert answer_with_tools("what is your return policy", PlainClient()) is None


def test_tool_loop_never_crashes():
    """API failure inside the tool path -> None (graceful fallback)."""
    from tools import answer_with_tools

    class BrokenClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            raise RuntimeError("api down")

    assert answer_with_tools("where is order A1001", BrokenClient()) is None

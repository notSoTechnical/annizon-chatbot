"""Tools the chatbot can DO, not just SAY — starting with order lookup.

Until now the bot could only answer from policy text (RAG). A "tool" is
a plain Python function the AI model may ask to run when a question needs
live data instead of policy text — e.g. "where is my order A1001?".

The loop (this is the pattern every AI agent uses):
  1. We hand the model a tool LIST: name + description + parameters.
  2. The model decides "this needs the tool" and replies with a CALL
     REQUEST (which tool, what arguments) instead of an answer.
  3. OUR code runs the function and hands the result back to the model.
  4. The model turns the result into a normal sentence for the customer.

Demo data: MOCK_ORDERS below is fake, hard-coded data. Real order lookup
needs the store's Shopify access (OAuth), which is a later step — the
function signature and the loop stay exactly the same when we swap the
dict for a real API call.
"""
import json

# The store's tracking page (Shopify + the 17TRACK app). Customers paste
# a tracking number there and see live delivery progress. We hand this
# link out with every order answer: it is where "live tracking" happens,
# and it is the rescue path when we can't find someone's order.
TRACKING_PAGE_URL = "https://annizon.com/apps/17TRACK"

# ---------------------------------------------------------------------------
# DEMO DATA — fake orders so the demo works with no Shopify connection.
# A real version would fetch this from the Shopify API instead.
# ---------------------------------------------------------------------------
MOCK_ORDERS = {
    "A1001": {
        "item": "Ceramic Vase Set (x2)",
        "status": "Shipped — in transit",
        "carrier": "UPS",
        "tracking": "1Z8842W90311745061",
        "eta": "Thursday, Oct 15",
    },
    "A1002": {
        "item": "Linen Throw Pillow Cover",
        "status": "Delivered",
        "carrier": "USPS",
        "tracking": "9400111899223817452070",
        "eta": "Delivered on Oct 9",
    },
    "A1003": {
        "item": "Walnut Wall Shelf",
        "status": "Processing — not shipped yet",
        "carrier": None,
        "tracking": None,
        "eta": "Ships within 2 business days",
    },
}


def lookup_order(order_id):
    """Look up one order by id. Always returns a dict, never raises.

    Found   -> {"found": True, "order_id": ..., "status": ..., ...}
    Missing -> {"found": False, ...} with a polite message the model
    can pass on (or rephrase) instead of inventing a status.
    Both carry "tracking_page": the link the customer can open to see
    live tracking (or to search by tracking number when we can't help).
    """
    key = str(order_id).strip().upper()
    order = MOCK_ORDERS.get(key)
    if order is None:
        return {
            "found": False,
            "order_id": key,
            "tracking_page": TRACKING_PAGE_URL,
            "message": (
                "We couldn't find an order with that id. Please double-check "
                "the order id in your confirmation email — it looks like 'A1001'."
            ),
        }
    return {"found": True, "order_id": key, "tracking_page": TRACKING_PAGE_URL, **order}


# The tool LIST we hand to the model (step 1 of the loop). This is just a
# description — the model never sees the Python code, only this menu.
ORDER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": (
                "Look up the delivery status of a customer's order. "
                "Use this when the customer asks where their order/package "
                "is, or about tracking or delivery of a specific order. "
                "The result includes a tracking_page link: always share "
                "that link in your answer so the customer can follow "
                "live tracking on the store's tracking page."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order id given by the customer, e.g. 'A1001'.",
                    }
                },
                "required": ["order_id"],
            },
        },
    }
]


def answer_with_tools(question, client, site_name="Annizon"):
    """Answer via the tool loop, or return None to use the normal RAG path.

    Returns the model's final text when it used the tool. Returns None
    when the model did NOT ask for the tool — policy questions keep
    going through the regular RAG path, untouched (this matters: RAG is
    the anti-hallucination guardrail, the model must not freestyle
    policy answers here). Any failure also returns None: the chat must
    never crash because a tool call went wrong.
    """
    messages = [
        {
            "role": "system",
            "content": (
                f"You are {site_name}'s customer service assistant. "
                "If the customer asks about a specific order or package, "
                "use the lookup_order tool to check it. After the tool "
                "answers, report ONLY what the tool returned — never "
                "invent a status, carrier, or delivery date. "
                f"Always give the customer the store's tracking page, "
                f"{TRACKING_PAGE_URL}: when the order is found, share it "
                "as the live-tracking link; when the order is not found "
                "or the customer has no order number, point them to that "
                "page to search with their tracking number."
            ),
        },
        {"role": "user", "content": question},
    ]
    try:
        # Step 2: offer the tool list; the model may request a call.
        resp = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=messages,
            tools=ORDER_TOOLS,
        )
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            return None  # not an order question → normal RAG path

        call = tool_calls[0]
        if call.function.name != "lookup_order":
            return None  # a tool we don't have → let RAG handle it

        # Step 3: run the real function, hand the result back.
        args = json.loads(call.function.arguments or "{}")
        result = lookup_order(args.get("order_id", ""))
        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": "lookup_order",
                            "arguments": call.function.arguments,
                        },
                    }
                ],
            }
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result),
            }
        )

        # Step 4: the model turns the tool result into a friendly sentence.
        final = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=messages,
        )
        return final.choices[0].message.content
    except Exception:
        return None  # tool path failed → caller falls back to RAG, no crash

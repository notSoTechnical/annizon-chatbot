"""AI ticket triage: categorize a customer message, route it to a team.

Big-company support desks do exactly this: a classifier decides what the
issue is about, then a routing table sends it to the right team.
"""

TEAMS = {
    "shipping": "shipping@annizon.com",
    "refund": "refund@annizon.com",
    "return": "return@annizon.com",
    "product": "product@annizon.com",
    "other": "info@annizon.com",
}

# The team addresses above don't exist as real mailboxes yet, so for now
# everything is delivered to info@annizon.com with a [category] tag in the
# subject (filter by tag in your inbox). Once you create the aliases at your
# mail host, flip this to True and mail routes for real.
USE_TEAM_INBOXES = False


def classify_issue(issue, client):
    """Ask the LLM to classify the issue. Returns just the category name.

    Split out of categorize() so multi-store app.py can do its own
    per-store email routing (see store_config.resolve_team_email).
    """
    try:
        resp = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a support ticket router for an online store. "
                        "Classify the customer message into exactly one category: "
                        "shipping, refund, return, product, other. "
                        "shipping = delivery, tracking, speed; "
                        "refund = money back; return = sending items back; "
                        "product = questions about items; other = anything else. "
                        "Reply with ONLY the category name, nothing else."
                    ),
                },
                {"role": "user", "content": issue},
            ],
        )
        category = resp.choices[0].message.content.strip().lower()
    except Exception:
        category = "other"  # AI call failed → safe fallback, the form never crashes
    if category not in TEAMS:  # model got creative → safe fallback
        category = "other"
    return category


def categorize(issue, client):
    """Ask the LLM to classify the issue. Returns (team_email, category).

    `client` is passed in (not imported as a global) so this function
    stays testable without a real API key — see tests/test_chatbot.py.
    Kept for backward compatibility; new code should use classify_issue()
    + store_config.resolve_team_email() for per-store routing.
    """
    category = classify_issue(issue, client)
    team = TEAMS[category] if USE_TEAM_INBOXES else TEAMS["other"]
    return team, category

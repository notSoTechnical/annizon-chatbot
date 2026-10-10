import os
import re
import streamlit as st
import requests
from openai import OpenAI
from retrieval import find_relevant
from triage import categorize

client = OpenAI(
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

# NOTE: the destination inbox now comes from triage.py (TEAMS + USE_TEAM_INBOXES),
# so there is no hardcoded SUPPORT_EMAIL here anymore.


def answer(question):
    chunks = find_relevant(question, top_k=3)
    context = "\n\n".join(c["text"] for c in chunks)
    resp = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[
            {"role": "system", "content": "You are Annizon's customer service assistant. Answer ONLY using the policy excerpts below. If the answer is not in the excerpts, say you don't know."},
            {"role": "user", "content": "Policy excerpts:\n" + context + "\n\nQuestion: " + question},
        ],
    )
    return resp.choices[0].message.content


def send_to_support(user_email, issue):
    """Email the customer's question to the right team via Resend.

    AI triage (triage.py) picks the team; Resend delivers it.
    Needs RESEND_API_KEY in Streamlit Secrets, and the sending
    domain (annizon.com) verified in the Resend dashboard.
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return False, "Email service isn't set up yet — please try again later."
    user_email = user_email.strip()
    issue = issue.strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", user_email):
        return False, "That email address doesn't look valid."
    if not issue:
        return False, "Please describe your question first."
    team_email, category = categorize(issue, client)  # AI triage: which team?
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from": "Annizon Support <support@annizon.com>",
                "to": [team_email],
                "reply_to": user_email,
                "subject": f"[{category}] Customer question from {user_email}",
                "text": f"From: {user_email}\n\n{issue}",
            },
            timeout=20,
        )
    except requests.RequestException:
        return False, "Couldn't reach the email service — please try again later."
    if resp.status_code >= 400:
        return False, "The message couldn't be sent — please try again later."
    return True, f"Sent to our {category} team! We'll reply to your email soon."


st.title("Annizon 客服")
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])

q = st.chat_input("问问退货、配送政策…")
if q:
    st.session_state.messages.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.write(q)
    a = answer(q)
    st.session_state.messages.append({"role": "assistant", "content": a})
    with st.chat_message("assistant"):
        st.write(a)
    if "don't know" in a.lower():
        st.info("I couldn't find that in our policies — leave your email below and a human will reply.")

with st.expander("📧 Still need help? Email a human"):
    contact_email = st.text_input("Your email", key="contact_email")
    contact_issue = st.text_area("Your question / issue", key="contact_issue")
    if st.button("Send to support"):
        ok, msg = send_to_support(contact_email, contact_issue)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

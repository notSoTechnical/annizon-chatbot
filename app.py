import json
import os
import re
import streamlit as st
import requests
from openai import OpenAI
import retrieval
from retrieval import CHUNKS_DIR, CHUNKS_PATH, find_relevant
from triage import classify_issue
from store_config import get_store_config, resolve_team_email, save_store_config
from crawler import crawl, chunk as chunk_text, slug, store_id_for_url

client = OpenAI(
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

# NOTE: the destination inbox now comes from triage.py (TEAMS + USE_TEAM_INBOXES),
# so there is no hardcoded SUPPORT_EMAIL here anymore.


def available_stores():
    """Store ids with their own chunks file, plus legacy default."""
    stores = []
    if CHUNKS_DIR.exists():
        stores = sorted(p.stem for p in CHUNKS_DIR.glob("*.json"))
    if CHUNKS_PATH.exists():
        stores = ["default (annizon.com)"] + stores
    return stores or ["default (annizon.com)"]


def resolve_store_id(choice):
    """Sidebar choice -> store_id used by retrieval."""
    if choice.startswith("default"):
        return "default"
    return choice


def answer(question, store_id="default", store_name="Annizon"):
    chunks = find_relevant(question, top_k=3, store_id=store_id)
    context = "\n\n".join(c["text"] for c in chunks)
    resp = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[
            {"role": "system", "content": f"You are {store_name}'s customer service assistant. Answer ONLY using the policy excerpts below. If the answer is not in the excerpts, say you don't know."},
            {"role": "user", "content": "Policy excerpts:\n" + context + "\n\nQuestion: " + question},
        ],
    )
    return resp.choices[0].message.content


def send_to_support(user_email, issue, store_id="default"):
    """Email the customer's question to the right team via Resend.

    AI triage picks the category; store_config picks the inbox for
    THIS store. Needs RESEND_API_KEY in Streamlit Secrets, and the
    store's sending domain verified in the Resend dashboard.
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
    cfg = get_store_config(store_id)
    category = classify_issue(issue, client)  # AI triage: which category?
    team_email = resolve_team_email(store_id, category)  # this store's inbox
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from": f"{cfg['store_name']} Support <{cfg['support_email']}>",
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
    a = answer(q, store_id=store_id, store_name=store_name)
    st.session_state.messages.append({"role": "assistant", "content": a})
    with st.chat_message("assistant"):
        st.write(a)
    if "don't know" in a.lower():
        st.info("I couldn't find that in our policies — leave your email below and a human will reply.")

with st.expander("📧 Still need help? Email a human"):
    contact_email = st.text_input("Your email", key="contact_email")
    contact_issue = st.text_area("Your question / issue", key="contact_issue")
    if st.button("Send to support"):
        ok, msg = send_to_support(contact_email, contact_issue, store_id)
        if ok:
            st.success(msg)
        else:
            st.error(msg)


# ---- Store picker: whose policies is this chat answering from? ----
with st.sidebar:
    st.header("\U0001f3ea Current store")
    store_choice = st.selectbox("Answering as", available_stores(), key="store_pick")
    store_id = resolve_store_id(store_choice)
    store_name = store_choice.replace("default (annizon.com)", "Annizon").replace("-", " ").title()

# ---- Merchant onboarding: enter a URL, get a chatbot (password-gated) ----
with st.sidebar:
    st.header("\U0001f3ea Onboard a new store")
    _admin_ok = st.secrets.get("ADMIN_PASSWORD", "")
    _pw = st.text_input("Merchant password", type="password", key="onboard_pw")
    if not _admin_ok:
        st.caption("Onboarding disabled — set ADMIN_PASSWORD in Streamlit Secrets.")
    elif _pw != _admin_ok:
        st.caption("Merchant-only area.")
    else:
        site_url = st.text_input("Website URL", placeholder="https://example.com", key="onboard_url")
        store_name_in = st.text_input("Store name", placeholder="H&M", key="onboard_name")
        support_email_in = st.text_input("Support email", placeholder="support@hm.com", key="onboard_email")
        max_pages = st.slider("Max pages to crawl", 5, 100, 40, key="onboard_pages")
        if st.button("Build chatbot", key="onboard_go"):
            site_url = (site_url or "").strip()
            support_email = (support_email_in or "").strip()
            if not site_url.startswith(("http://", "https://")):
                st.error("Please enter a full URL starting with https://")
            elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", support_email):
                st.error("Please enter a valid support email.")
            else:
                with st.spinner(f"Crawling {site_url} — this takes a minute or two..."):
                    try:
                        pages = crawl(site_url, max_pages=max_pages)
                    except Exception as e:
                        st.error(f"Crawl failed: {e}")
                        pages = []
                if pages:
                    new_store_id = store_id_for_url(site_url)
                    save_store_config(new_store_id, {
                        "store_name": (store_name_in or "").strip() or new_store_id.replace("-", " ").title(),
                        "support_email": support_email,
                    })
                    CHUNKS_DIR.mkdir(exist_ok=True)
                    all_chunks = [{"text": c, "source": slug(u)}
                                  for u, t in pages for c in chunk_text(t)]
                    with open(CHUNKS_DIR / f"{new_store_id}.json", "w") as f:
                        json.dump(all_chunks, f, ensure_ascii=False, indent=2)
                    # retrieval.py caches chunks in-process — clear it so the new
                    # chunks take effect without restarting the app.
                    retrieval._load_chunks.cache_clear()
                    retrieval._chunk_vectors.cache_clear()
                    retrieval._local_chunk_vectors.cache_clear()
                    st.success(f"Done! {len(all_chunks)} chunks from {len(pages)} pages "
                               f"saved as store '{new_store_id}'. Pick it above \U0001f447")
                else:
                    st.warning("No usable pages found — check the URL and try again.")

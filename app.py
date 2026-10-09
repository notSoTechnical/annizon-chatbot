import os
import streamlit as st
from openai import OpenAI
from retrieval import find_relevant

client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

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

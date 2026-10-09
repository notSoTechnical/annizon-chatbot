import os
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

while True:
    q = input("You: ")
    if q == "quit":
        break
    print("Bot:", answer(q))

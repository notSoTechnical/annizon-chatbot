import os, sys
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
question = " ".join(sys.argv[1:]) or input("问点什么: ")
resp = client.chat.completions.create(
    model="gemini-2.5-flash",
    messages=[
        {"role": "system", "content": "用简体中文回答，简短。"},
        {"role": "user", "content": question},
    ],
)
print(resp.choices[0].message.content)

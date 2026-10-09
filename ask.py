from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
resp = client.chat.completions.create(
    model="gemini-2.5-flash",
    messages=[{"role": "user", "content": "用一句话介绍Python"}],
)
print(resp.choices[0].message.content)

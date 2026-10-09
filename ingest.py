import json
import requests
from bs4 import BeautifulSoup

POLICIES = {
    "shipping": "https://annizon.com/policies/shipping-policy",
    "refund": "https://annizon.com/policies/refund-policy",
    "privacy": "https://annizon.com/policies/privacy-policy",
    "terms": "https://annizon.com/policies/terms-of-service",
}

def get_text(url):
    r = requests.get(url, timeout=20)
    if r.status_code != 200:
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    body = soup.find("div", class_="shopify-policy__body")
    if not body:
        return ""
    return body.get_text(separator="\n", strip=True)

def chunk(text, size=500):
    parts = []
    for i in range(0, len(text), size):
        parts.append(text[i:i + size])
    return parts

all_chunks = []
for name, url in POLICIES.items():
    text = get_text(url)
    print(name, "->", len(text), "chars")
    for c in chunk(text):
        all_chunks.append({"text": c, "source": name})

with open("chunks.json", "w") as f:
    json.dump(all_chunks, f, ensure_ascii=False, indent=2)
print("saved", len(all_chunks), "chunks")

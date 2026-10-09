import json
import re

with open("chunks.json") as f:
    chunks = json.load(f)

def get_score(pair):
    return pair[0]

def find_relevant(question, top_k=3):
    qwords = set(re.findall(r"\w+", question.lower()))
    scored = []
    for c in chunks:
        cwords = set(re.findall(r"\w+", c["text"].lower()))
        score = len(qwords & cwords)
        scored.append((score, c))
    scored.sort(key=get_score, reverse=True)
    return [c for _, c in scored[:top_k]]

if __name__ == "__main__":
    for c in find_relevant("how long does shipping take"):
        print("[" + c["source"] + "]", c["text"][:120])
        print("---")

"""Auto-crawl a website into chunks.json — no manual policy URLs needed.

Usage:
    python crawler.py https://example.com --max-pages 40 --out chunks.json

The output format matches ingest.py, so retrieval.py works unchanged.
Honest crawler: respects robots.txt, stays on the same domain, 0.5s delay.
"""
import argparse
import json
import sys
import time
from collections import deque
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

# URL hints that a page is policy/FAQ-like (crawled first).
PRIORITY_HINTS = (
    "shipping", "return", "refund", "exchange",
    "faq", "frequently-asked", "help", "support",
    "policy", "policies", "terms", "privacy",
    "about", "contact", "delivery",
)

SKIP_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg",
                   ".mp4", ".zip", ".css", ".js", ".ico",
                   ".woff", ".woff2")

HEADERS = {"User-Agent": "AnnizonBot/1.0 (+https://annizon.com) policy crawler"}


def allowed_by_robots(site_root):
    rp = RobotFileParser()
    try:
        rp.set_url(urljoin(site_root, "/robots.txt"))
        rp.read()
        return rp
    except Exception:
        return None  # no robots.txt -> proceed politely


def clean_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    body = (soup.find("div", class_="shopify-policy__body")
            or soup.find("main") or soup.find("article") or soup.body)
    if not body:
        return ""
    text = body.get_text(separator="\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


def priority(url):
    low = url.lower()
    return sum(h in low for h in PRIORITY_HINTS)


def crawl(start_url, max_pages=40, delay=0.5):
    parsed = urlparse(start_url)
    domain = parsed.netloc
    site_root = f"{parsed.scheme}://{domain}"
    rp = allowed_by_robots(site_root)

    seen = set()
    queue = deque([start_url])
    pages = []

    while queue and len(pages) < max_pages:
        queue = deque(sorted(queue, key=priority, reverse=True))
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        if rp and not rp.can_fetch(HEADERS["User-Agent"], url):
            continue
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
        except Exception as e:
            print(f"skip {url}: {e}", file=sys.stderr)
            continue
        if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", ""):
            continue
        text = clean_text(r.text)
        if len(text) >= 200:
            pages.append((url, text))
            print(f"+ {url} ({len(text)} chars)")
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"]).split("#")[0].split("?")[0]
            p = urlparse(link)
            if p.scheme not in ("http", "https"):
                continue
            if p.netloc != domain:
                continue
            if p.path.lower().endswith(SKIP_EXTENSIONS):
                continue
            if link not in seen:
                queue.append(link)
        time.sleep(delay)
    return pages


def chunk(text, size=500):
    return [text[i:i + size] for i in range(0, len(text), size)]


def slug(url):
    path = urlparse(url).path.strip("/").replace("/", "-")
    return path or "home"


def store_id_for_url(url):
    """Turn a website URL into a filesystem-safe store id: H&M -> hm-com."""
    import re
    netloc = urlparse(url).netloc.lower()
    netloc = re.sub(r"^www\.", "", netloc)  # www.hm.com -> hm.com
    return re.sub(r"[^a-z0-9]+", "-", netloc).strip("-") or "default"


def main():
    ap = argparse.ArgumentParser(description="Crawl a site into chunks.json")
    ap.add_argument("url", help="site root URL, e.g. https://example.com")
    ap.add_argument("--max-pages", type=int, default=40)
    ap.add_argument("--out", default="chunks.json")
    args = ap.parse_args()

    pages = crawl(args.url, max_pages=args.max_pages)
    all_chunks = []
    for url, text in pages:
        for c in chunk(text):
            all_chunks.append({"text": c, "source": slug(url)})
    with open(args.out, "w") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)
    print(f"saved {len(all_chunks)} chunks from {len(pages)} pages -> {args.out}")


if __name__ == "__main__":
    main()

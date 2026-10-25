"""OPTIONAL real photo fetcher (ART stage 4) - OFF BY DEFAULT.

Run by hand only:   python tools/fetch_stock_photos.py
Never at app start and never in tests.

Needs a free Pexels API key in the environment variable PEXELS_API_KEY
(get one at https://www.pexels.com/api/). The key is read from the
environment for each request header and is never written to any file.

For every entry in tools/photo_queries.json the script searches Pexels,
picks the first photo with a sensible size, downloads its medium file,
re-encodes it with Pillow (EXIF stripped, max 1200 px, JPEG quality 82)
and saves it as static/demo_photos/stock/<category>/<subcategory_key>.jpg
plus one credit line in static/demo_photos/CREDITS.txt. Existing files are
skipped, a short sleep respects rate limits and at most 150 requests run
per pass. Images are stored locally - the site never hotlinks them.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUERIES_PATH = os.path.join(BASE_DIR, "tools", "photo_queries.json")
STOCK_DIR = os.path.join(BASE_DIR, "static", "demo_photos", "stock")
CREDITS_PATH = os.path.join(BASE_DIR, "static", "demo_photos", "CREDITS.txt")

SEARCH_URL = "https://api.pexels.com/v1/search"
MAX_REQUESTS = 150
SLEEP_SECONDS = 1.0          # between searches (rate-limit courtesy)
RETRY_429_SLEEP = 10.0       # back-off when Pexels answers 429
TIMEOUT = 15                 # seconds per HTTP call
MAX_DIMENSION = 1200
JPEG_QUALITY = 82

NO_KEY_MSG = (
    "PEXELS_API_KEY is not set, so no photos were fetched (this is fine -\n"
    "the app uses generated art). To enable real photos:\n"
    "  1. get a free key at https://www.pexels.com/api/\n"
    "  2. set it for this shell:  $env:PEXELS_API_KEY=\"your-key\"\n"
    "  3. run: python tools/fetch_stock_photos.py")


def load_queries(path=QUERIES_PATH):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _dest_path(query):
    return os.path.join(STOCK_DIR, query["category"],
                        query["subcategory_key"] + ".jpg")


def _pick_photo(data):
    """First photo with a medium file and a sensible size."""
    for ph in data.get("photos", []):
        medium = (ph.get("src") or {}).get("medium") or ""
        if medium and max(ph.get("width", 0), ph.get("height", 0)) >= 800:
            return ph
    return None


def _reencode(content):
    """RGB JPEG, EXIF stripped (pixels are re-saved), max 1200 px, q82."""
    from PIL import Image
    img = Image.open(io.BytesIO(content))
    img = img.convert("RGB")
    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


def _append_credit(dest_rel, photo):
    photographer = (photo.get("user") or {}).get("name", "Unknown")
    page = photo.get("url", "")
    line = (f"{dest_rel}\tphotographer: {photographer}\tpage: {page}\t"
            f"source: Pexels\tlicence: Pexels License\n")
    os.makedirs(os.path.dirname(CREDITS_PATH), exist_ok=True)
    with open(CREDITS_PATH, "a", encoding="utf-8") as fh:
        fh.write(line)


def run(queries, api_key, session, sleep_s=SLEEP_SECONDS,
        max_requests=MAX_REQUESTS, retry_s=RETRY_429_SLEEP):
    """Fetch and save photos; returns a summary dict. Never raises per-query."""
    summary = {"downloaded": 0, "skipped": 0, "failed": 0, "requests": 0}
    headers = {"Authorization": api_key}
    for q in queries[:max_requests]:
        dest = _dest_path(q)
        if os.path.exists(dest):
            summary["skipped"] += 1
            continue
        try:
            resp = session.get(
                SEARCH_URL,
                params={"query": q["phrase"], "per_page": 15, "size": "large"},
                headers=headers, timeout=TIMEOUT)
            summary["requests"] += 1
            if resp.status_code == 429:            # rate limited: back off once
                time.sleep(retry_s)
                resp = session.get(
                    SEARCH_URL,
                    params={"query": q["phrase"], "per_page": 15, "size": "large"},
                    headers=headers, timeout=TIMEOUT)
                summary["requests"] += 1
            if resp.status_code != 200:
                summary["failed"] += 1
                print(f"  ! {q['category']}/{q['subcategory_key']}: "
                      f"search HTTP {resp.status_code}")
                continue
            photo = _pick_photo(resp.json())
            if not photo:
                summary["failed"] += 1
                print(f"  ! {q['category']}/{q['subcategory_key']}: no usable photo")
                continue
            medium = photo["src"]["medium"]
            img = session.get(medium, headers={}, timeout=TIMEOUT)
            summary["requests"] += 1
            if img.status_code != 200 or not img.content:
                summary["failed"] += 1
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(_reencode(img.content))
            rel = os.path.relpath(dest, BASE_DIR).replace("\\", "/")
            _append_credit(rel, photo)
            summary["downloaded"] += 1
            print(f"  + {rel}")
        except Exception as exc:                   # noqa: BLE001 - keep going
            summary["failed"] += 1
            print(f"  ! {q['category']}/{q['subcategory_key']}: {exc}")
        time.sleep(sleep_s)
    return summary


def main(argv=None):
    argv = list(argv or [])
    if "--emit-queries" in argv:         # offline helper, needs no key
        queries = build_queries()
        with open(QUERIES_PATH, "w", encoding="utf-8") as fh:
            json.dump(queries, fh, indent=1, ensure_ascii=False)
        print(f"Wrote {len(queries)} queries to {QUERIES_PATH}")
        return 0
    api_key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not api_key:
        print(NO_KEY_MSG)
        return 1
    if not os.path.exists(QUERIES_PATH):
        print(f"Missing {QUERIES_PATH}. Regenerate it with:\n"
              f"  python tools/fetch_stock_photos.py --emit-queries")
        return 1
    import requests
    queries = load_queries()
    print(f"Pexels fetch: {len(queries)} queries (max {MAX_REQUESTS} per run). "
          f"Existing files are skipped.")
    t0 = time.time()
    summary = run(queries, api_key, requests)
    print(f"Done in {time.time() - t0:.0f}s - downloaded {summary['downloaded']}, "
          f"skipped {summary['skipped']}, failed {summary['failed']}, "
          f"requests {summary['requests']}.")
    print("Please read Pexels' API terms and keep the CREDITS.txt attributions.")
    return 0


# ---------------------------------------------------------------------------
# Query generation from config (run: python tools/fetch_stock_photos.py
#                              --emit-queries)
# ---------------------------------------------------------------------------
PHRASES = {
    # clothes
    "lehenga": "bridal lehenga", "saree": "saree silk",
    "sherwani": "sherwani groom", "kurta": "kurta men",
    "kurta_set": "kurta set women", "kids_wear": "kids ethnic wear",
    "western": "women western dress", "gown": "party gown",
    "blazer": "formal blazer men", "frock": "kids party frock",
    "anarkali": "anarkali dress",
    # books
    "comedy": "funny book stack", "spiritual": "spiritual books",
    "motivation": "motivational books", "self_help": "self help book",
    "fiction": "novel books stack", "biography": "biography book",
    "mythology": "mythology books", "children_books": "children picture books",
    "education": "textbook stack", "business_books": "business books",
    "health": "health fitness book", "poetry": "poetry book",
    "other_books": "open book stack",
    # farm tools
    "tractor": "tractor field", "attachments": "farm plough implement",
    "water_tank": "water storage tank", "sprayer": "hand sprayer farm",
    "harvesting": "harvesting crops farm", "hand_tools": "garden hand tools",
    "power_tools": "power tools drill", "soil": "farm soil cultivation",
    "transport": "farm cart transport",
    # electronics
    "camera": "dslr camera", "laptop": "laptop computer",
    "projector": "projector presentation", "speaker": "bluetooth speaker",
    "microphone": "microphone stage", "drone": "camera drone",
    "lights": "led string lights", "generator": "power generator",
    "console": "gaming console", "screen": "led tv screen",
    # event items
    "decoration": "flower decoration stage", "chairs": "plastic chairs event",
    "tent": "wedding tent decoration", "stage_lighting": "stage lighting concert",
    "catering": "catering buffet setup", "stage": "event stage backdrop",
    "festival_items": "diya diwali lights", "photobooth": "photobooth frame props",
}


def build_queries():
    """One {category, subcategory_key, phrase} row per config sub-category."""
    sys.path.insert(0, BASE_DIR)
    import config
    rows = []
    for cat, meta in config.CATEGORIES.items():
        for sc in meta.get("subcategories", []):
            key = sc["key"]
            rows.append({"category": cat, "subcategory_key": key,
                         "phrase": PHRASES.get(key, sc.get("label", key))})
    return rows


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

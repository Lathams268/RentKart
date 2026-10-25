"""Case-insensitive, partial and fuzzy item search.

The original browse filter only matched ``title``/``description`` with a single
``%whole query%`` pattern, so "dress" found nothing (no such title), "dres" only
worked from the left, "party dress" needed the exact phrase, and category/tags
were ignored. This module builds a searchable haystack per item (title,
description, category, sub-category, tags, attributes and owner shop) and scores
each query token with exact → prefix → substring → fuzzy matching.

Everything is pure Python on purpose: the catalogue is small, and this keeps the
ranking identical on SQLite, Postgres and MySQL.
"""
import difflib
import re

from config import CATEGORIES, KEYWORD_MAP

WORD_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "a", "an", "the", "for", "with", "and", "or", "of", "to", "in", "on", "at",
    "my", "me", "is", "are", "any", "some", "rent", "rental", "rentals", "hire",
    "need", "want", "looking", "near", "cheap", "best", "good",
}

# Minimum per-token score for an item to count as a match. 0.6 == fuzzy only.
MATCH_THRESHOLD = 0.6


def normalize(text) -> str:
    value = str(text or "").lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def tokens(text) -> list:
    return [w for w in normalize(text).split() if w and w not in STOPWORDS]


def stem(word: str) -> str:
    """Very small plural stemmer: dresses→dress, cameras→camera, cycles→cycle."""
    word = str(word or "")
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("ses", "xes", "zes", "ches", "shes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _variants(word: str) -> set:
    base = stem(word)
    return {word, base}


def category_label(key: str) -> str:
    return str((CATEGORIES.get(key) or {}).get("label") or key or "")


def subcategory_label(item) -> str:
    category = getattr(item, "category", "") or ""
    attrs = {}
    if hasattr(item, "get_attributes"):
        try:
            attrs = item.get_attributes() or {}
        except Exception:  # pragma: no cover - defensive
            attrs = {}
    for sub in (CATEGORIES.get(category) or {}).get("subcategories", []):
        value = attrs.get(sub.get("field"))
        if value is None:
            continue
        text = str(value).strip().lower()
        target = str(sub.get("value") or "").strip().lower()
        if text and target and (text == target or target in text):
            return str(sub.get("label") or "")
    return ""


def item_tags(item) -> list:
    if hasattr(item, "get_tags"):
        try:
            return item.get_tags()
        except Exception:  # pragma: no cover - defensive
            return []
    return []


def item_haystack(item) -> str:
    """All human-searchable text for one item, normalized to lowercase words."""
    parts = [
        getattr(item, "title", "") or "",
        getattr(item, "description", "") or "",
        getattr(item, "category", "") or "",
        category_label(getattr(item, "category", "") or ""),
        subcategory_label(item),
        " ".join(item_tags(item)),
    ]
    if hasattr(item, "get_attributes"):
        try:
            for key, value in (item.get_attributes() or {}).items():
                parts.append(str(key).replace("_", " "))
                parts.append(str(value))
        except Exception:  # pragma: no cover - defensive
            pass
    owner = getattr(item, "owner", None)
    if owner is not None:
        parts.extend([
            getattr(owner, "shop_name", "") or "",
            getattr(owner, "name", "") or "",
            getattr(owner, "village_or_city", "") or "",
        ])
    return normalize(" ".join(str(p) for p in parts if p))


def _token_score(token: str, words: list) -> float:
    best = 0.0
    token_forms = _variants(token)
    for word in words:
        word_forms = _variants(word)
        for tf in token_forms:
            if tf in word_forms:
                return 1.0
            if word.startswith(tf) or tf.startswith(word):
                best = max(best, 0.9)
            elif len(tf) >= 4 and len(word) >= 4 and (tf in word or word in tf):
                best = max(best, 0.78)
            elif len(tf) >= 4 and abs(len(word) - len(tf)) <= 3:
                ratio = difflib.SequenceMatcher(None, tf, word).ratio()
                if ratio >= 0.8:
                    best = max(best, 0.65 + (ratio - 0.8))
    return best


def score_item(item, query_tokens, haystack=None) -> float:
    """0 when any token is missing; otherwise the average token score."""
    if not query_tokens:
        return 0.0
    text = haystack if haystack is not None else item_haystack(item)
    words = text.split()
    total = 0.0
    for token in query_tokens:
        token_score = _token_score(token, words)
        if token_score < MATCH_THRESHOLD:
            return 0.0
        total += token_score
    return total / len(query_tokens)


def matches(item, query) -> bool:
    query_tokens = tokens(query)
    if not query_tokens:
        return True
    return score_item(item, query_tokens) > 0


def search_items(items, query) -> list:
    """Filter + rank items by relevance (best first). Empty query returns input."""
    query_tokens = tokens(query)
    if not query_tokens:
        return list(items)
    scored = []
    for item in items:
        value = score_item(item, query_tokens)
        if value > 0:
            scored.append((value, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _score, item in scored]


def keyword_category(query):
    """Category suggested by the spoken-keyword map, if any.

    ``dress`` → ``clothes``, ``bike`` → ``bikes`` … The browse route uses this
    to *pre-select* a filter while keeping the typed text as a search term.
    """
    normalized = normalize(query)
    if not normalized:
        return None
    if normalized in KEYWORD_MAP:
        return KEYWORD_MAP[normalized]
    for token in normalized.split():
        if token in KEYWORD_MAP:
            return KEYWORD_MAP[token]
    return None


def highlight_terms(query) -> list:
    return tokens(query)

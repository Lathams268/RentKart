"""Trending books logic and book genre metadata helpers."""
from datetime import datetime, timedelta
from flask import current_app
from models import Item, Booking

# Metadata for each genre: emoji, clean short label, and Tailwind color classes
GENRE_METADATA = {
    "Comedy / Humor": {
        "emoji": "😂",
        "short_label": "Comedy",
        "color": "bg-yellow-100 text-yellow-800 border border-yellow-300",
    },
    "Inspirational / Motivation": {
        "emoji": "✨",
        "short_label": "Inspirational",
        "color": "bg-purple-100 text-purple-800 border border-purple-300",
    },
    "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)": {
        "emoji": "🙏",
        "short_label": "Spiritual",
        "color": "bg-amber-100 text-amber-900 border border-amber-300",
    },
    "Self-Help": {
        "emoji": "🌱",
        "short_label": "Self-Help",
        "color": "bg-emerald-100 text-emerald-800 border border-emerald-300",
    },
    "Fiction / Novel": {
        "emoji": "📖",
        "short_label": "Fiction",
        "color": "bg-blue-100 text-blue-800 border border-blue-300",
    },
    "Biography": {
        "emoji": "👤",
        "short_label": "Biography",
        "color": "bg-indigo-100 text-indigo-800 border border-indigo-300",
    },
    "Mythology": {
        "emoji": "🏹",
        "short_label": "Mythology",
        "color": "bg-orange-100 text-orange-800 border border-orange-300",
    },
    "Children": {
        "emoji": "🧸",
        "short_label": "Children",
        "color": "bg-pink-100 text-pink-800 border border-pink-300",
    },
    "Education / Exam Prep": {
        "emoji": "🎓",
        "short_label": "Education",
        "color": "bg-sky-100 text-sky-800 border border-sky-300",
    },
    "Business / Finance": {
        "emoji": "💼",
        "short_label": "Business",
        "color": "bg-teal-100 text-teal-800 border border-teal-300",
    },
    "Health / Fitness": {
        "emoji": "🧘",
        "short_label": "Health",
        "color": "bg-rose-100 text-rose-800 border border-rose-300",
    },
    "Poetry": {
        "emoji": "✍️",
        "short_label": "Poetry",
        "color": "bg-violet-100 text-violet-800 border border-violet-300",
    },
    "Other": {
        "emoji": "📚",
        "short_label": "Other",
        "color": "bg-gray-100 text-gray-800 border border-gray-300",
    },
}

DEFAULT_GENRE_INFO = {
    "genre": "General",
    "emoji": "📖",
    "short_label": "General",
    "color": "bg-gray-100 text-gray-700 border border-gray-300",
}


def matches_genre(item_genre: str, requested_genre: str) -> bool:
    """Check if a book's genre matches the requested genre filter flexibly."""
    if not requested_genre:
        return True
    req = requested_genre.strip().lower()
    if req in ("all", ""):
        return True
    if not item_genre:
        return req in ("general", "other")

    ig = item_genre.strip().lower()
    if req == ig:
        return True
    if req in ig or ig in req:
        return True
    # Word prefix matching (e.g. 'comedy' matches 'comedy / humor')
    req_words = [w.strip("(),/") for w in req.split() if w.strip("(),/")]
    ig_words = [w.strip("(),/") for w in ig.split() if w.strip("(),/")]
    if any(rw in ig_words for rw in req_words):
        return True
    return False


def get_book_genre_info(item_or_genre) -> dict:
    """Return dictionary with genre, emoji, short_label, color for a book item or genre string."""
    if not item_or_genre:
        return dict(DEFAULT_GENRE_INFO)

    if isinstance(item_or_genre, str):
        genre = item_or_genre.strip()
    elif hasattr(item_or_genre, "category") and item_or_genre.category != "books":
        return dict(DEFAULT_GENRE_INFO)
    elif hasattr(item_or_genre, "get_attributes"):
        attrs = item_or_genre.get_attributes() or {}
        genre = attrs.get("genre")
    elif isinstance(item_or_genre, dict):
        genre = item_or_genre.get("genre")
    else:
        genre = getattr(item_or_genre, "genre", None)

    if not genre:
        return dict(DEFAULT_GENRE_INFO)

    if genre in GENRE_METADATA:
        info = dict(GENRE_METADATA[genre])
        info["genre"] = genre
        return info

    for k, v in GENRE_METADATA.items():
        if matches_genre(k, genre) or matches_genre(genre, k):
            info = dict(v)
            info["genre"] = genre
            return info

    return {
        "genre": genre,
        "emoji": "📚",
        "short_label": genre.split("/")[0].strip(),
        "color": "bg-gray-100 text-gray-700 border border-gray-300",
    }


def get_trending_books(limit: int = 10, days: int = 30, min_qualify: int = 3, items=None, now=None):
    """Rank books by bookings created in the last `days` with valid statuses.

    Valid statuses: requested, approved, picked_up, returned.
    If fewer than `min_qualify` qualify, fills with most recently added books.
    """
    valid_statuses = {"requested", "approved", "picked_up", "returned"}
    current_time = now or datetime.utcnow()
    cutoff = current_time - timedelta(days=days)

    if items is not None:
        candidate_books = [it for it in items if getattr(it, "category", None) == "books" and it.is_available]
    else:
        candidate_books = Item.query.filter_by(category="books", is_available=True).all()

    # Calculate count of qualifying bookings for each book
    booking_counts = {}
    for book in candidate_books:
        count = 0
        for b in book.bookings:
            if b.status in valid_statuses:
                b_created = getattr(b, "created_at", None)
                if b_created and b_created >= cutoff:
                    count += 1
        booking_counts[book.id] = count

    # Qualified books have at least 1 recent booking
    qualified = [b for b in candidate_books if booking_counts.get(b.id, 0) > 0]
    # Rank by booking count desc, then item creation date desc
    qualified.sort(
        key=lambda b: (
            booking_counts.get(b.id, 0),
            b.created_at.timestamp() if getattr(b, "created_at", None) else 0,
            b.id,
        ),
        reverse=True,
    )

    result = list(qualified[:limit])

    # If fewer than min_qualify qualify, fill with most recently added books
    if len(result) < min_qualify:
        seen_ids = set(b.id for b in result)
        remaining = [b for b in candidate_books if b.id not in seen_ids]
        remaining.sort(
            key=lambda b: (
                b.created_at.timestamp() if getattr(b, "created_at", None) else 0,
                b.id,
            ),
            reverse=True,
        )
        for b in remaining:
            result.append(b)
            if len(result) >= min_qualify and len(result) >= limit:
                break

    return result[:limit]


def is_book_trending(item, days: int = 30, limit: int = 10, now=None) -> bool:
    """Return True if item is in the top trending books."""
    if not item or getattr(item, "category", None) != "books":
        return False
    trending = get_trending_books(limit=limit, days=days, now=now)
    return any(b.id == item.id for b in trending)

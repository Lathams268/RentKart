"""Pricing helpers – smart price suggestions and seasonal demand boosts."""
from datetime import date
from config import PRICE_HINTS, SEASONS


def suggest_price(category: str, today: date | None = None) -> dict:
    """Return min, max price hints, season name (or None), and boosted range when in season."""
    if today is None:
        today = date.today()

    hint = PRICE_HINTS.get(category, {"min": 100, "max": 500})
    base_min = hint["min"]
    base_max = hint["max"]

    month = today.month
    matched_season = None
    for s in SEASONS:
        if category in s["categories"] and month in s["months"]:
            matched_season = s
            break

    if matched_season:
        season_name = matched_season["name"]
        boost = matched_season.get("boost_percent", 20)
        boosted_min = int(round(base_min * (1 + boost / 100.0)))
        boosted_max = int(round(base_max * (1 + boost / 100.0)))
    else:
        season_name = None
        boost = 0
        boosted_min = None
        boosted_max = None

    return {
        "category": category,
        "min": base_min,
        "max": base_max,
        "range": [base_min, base_max],
        "season_name": season_name,
        "season": season_name,
        "boost_percent": boost,
        "boosted_min": boosted_min,
        "boosted_max": boosted_max,
        "boosted_range": [boosted_min, boosted_max] if boosted_min is not None else None,
        "in_season": bool(matched_season),
    }


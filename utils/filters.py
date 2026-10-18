"""Filter validation, dependent options, and empty-state suggestion helpers for RentKart."""
import re
import urllib.parse
from flask import url_for

KIDS_AGE_GROUPS = {"0–2", "0-2", "3–5", "3-5", "6–8", "6-8", "9–12", "9-12", "13–17", "13-17"}
ADULT_AGE_GROUPS = {"18+", "18"}

KIDS_SIZES = {
    "0-6M", "6-12M", "1-2Y", "2-3Y", "3-4Y", "4-5Y", "5-6Y",
    "6-8Y", "7-8Y", "8-10Y", "9-12Y", "10-12Y", "12-14Y", "13-16Y", "14-16Y", "Free Size"
}
ADULT_SIZES = {"XS", "S", "M", "L", "XL", "XXL", "Free Size"}

GIRL_WOMEN_ONLY_TYPES = {
    "lehenga", "saree", "salwar suit", "anarkali", "pattu pavadai",
    "kurti", "palazzo set", "gown", "frock", "crop top lehenga",
    "cape lehenga", "saree gown", "cocktail dress", "skirt"
}
BOY_MEN_ONLY_TYPES = {
    "sherwani", "tuxedo", "angavastram", "indo western sherwani"
}


def norm_str(s):
    if s is None:
        return ""
    return str(s).strip().lower().replace("–", "-").replace("—", "-")


def is_valid_size(age_group: str, size: str) -> bool:
    """Validate whether size is consistent with chosen age group."""
    if not age_group or not size or size.lower() == "all":
        return True
    ag = norm_str(age_group)
    s = str(size).strip()
    if s == "Free Size":
        return True
    if ag in ("18+", "18"):
        return s in ADULT_SIZES
    if ag in KIDS_AGE_GROUPS:
        return s in KIDS_SIZES
    return True


def is_valid_clothing_type(gender: str, style: str, clothing_type: str) -> bool:
    """Validate whether clothing_type is consistent with gender and style."""
    if not clothing_type or clothing_type.lower() == "all":
        return True
    ct = norm_str(clothing_type)
    g = norm_str(gender)
    if g in ("boys", "boy", "men", "man"):
        if ct in GIRL_WOMEN_ONLY_TYPES:
            return False
    elif g in ("girls", "girl", "women", "woman"):
        if ct in BOY_MEN_ONLY_TYPES:
            return False
    return True


def build_remove_filter_url(request_args: dict, key_to_remove: str) -> str:
    """Return URL query string with a specific filter key removed."""
    params = {}
    for k, v in request_args.items():
        if k == key_to_remove:
            continue
        # Also clean related attr_ prefix if applicable
        if key_to_remove.startswith("attr_") and k == key_to_remove[5:]:
            continue
        if not key_to_remove.startswith("attr_") and k == f"attr_{key_to_remove}":
            continue
        params[k] = v
    if not params:
        return url_for("main.browse")
    return url_for("main.browse") + "?" + urllib.parse.urlencode(params)


def compute_best_filter_to_remove(candidate_filters: list, evaluate_fn) -> tuple:
    """
    Given active filters and an evaluation function f(active_filters_without_i) -> count,
    returns (best_filter_dict, max_count, removal_url).
    """
    if not candidate_filters:
        return None, 0, ""

    best_filter = None
    best_count = 0

    for cand in candidate_filters:
        count = evaluate_fn(cand["key"])
        if count > best_count:
            best_count = count
            best_filter = cand

    if best_filter and best_count > 0:
        return best_filter, best_count, best_filter.get("remove_url", "")
    return None, 0, ""


def get_you_might_like(available_items: list, limit: int = 4) -> list:
    """Return top nearby/popular items to display on empty state."""
    if not available_items:
        return []
    # Sort with distance first, then ID
    sorted_items = sorted(
        available_items,
        key=lambda i: (getattr(i, "distance_km", None) is None, getattr(i, "distance_km", 9999), -i.id)
    )
    return sorted_items[:limit]

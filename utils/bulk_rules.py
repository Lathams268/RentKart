"""Bulk-listing pricing-rule lookup (additive feature, Stage 1).

Resolution order for every price column (price_per_day / deposit /
late_fee_per_day):

    1. the value typed in the row itself, else
    2. the MOST SPECIFIC matching rule (a rule whose match_field appears in the
       row and whose match_value equals the row's value, case-insensitive), else
    3. the category DEFAULT rule (match_field/match_value empty), else
    4. nothing -> a missing price is reported as an error by the caller.

Only the shop owner's own rules are ever considered.
"""
from models import PricingRule

PRICE_COLUMNS = ("price_per_day", "deposit", "late_fee_per_day")


def _norm(value):
    return str(value or "").strip().lower()


def load_rules(owner_id, category):
    """Return all PricingRule rows for one owner + category."""
    return PricingRule.query.filter_by(
        owner_id=owner_id, category=category
    ).all()


def pick_default_rule(rules):
    """The category default rule (no match_field), if any."""
    for r in rules:
        if r.is_default:
            return r
    return None


def find_specific_rule(rules, row_attrs):
    """Most specific rule whose (match_field, match_value) matches the row."""
    best = None
    best_score = -1
    for r in rules:
        if r.is_default:
            continue
        field = r.match_field
        if not field:
            continue
        row_val = row_attrs.get(field)
        if row_val is None:
            # match_field may be a base column (rare) - also check flat row
            continue
        if _norm(row_val) == _norm(r.match_value):
            # Prefer rules that actually set a price (more complete = specific)
            score = 1 + (1 if r.price_per_day else 0)
            if score > best_score:
                best, best_score = r, score
    return best


def _explicit(explicit, col):
    """Return the explicit row value for a column when it is a usable number."""
    if not explicit:
        return None
    val = explicit.get(col)
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    return f


def resolve_price(owner_id, category, row_attrs, explicit=None):
    """Resolve the three price columns for one row.

    row_attrs: dict of category field name -> value (e.g. {"genre": "Comedy"}).
    explicit:  dict that may carry row-typed price_per_day/deposit/late_fee.
    Returns {col: float|None, "source": {col: str}, "missing_price": bool}.
    """
    rules = load_rules(owner_id, category)
    specific = find_specific_rule(rules, row_attrs or {})
    default = pick_default_rule(rules)

    out = {"source": {}}
    for col in PRICE_COLUMNS:
        val = _explicit(explicit, col)
        if val is not None:
            out[col], out["source"][col] = val, "row"
            continue
        if specific is not None and getattr(specific, col) is not None:
            out[col], out["source"][col] = float(getattr(specific, col)), "rule"
            continue
        if default is not None and getattr(default, col) is not None:
            out[col], out["source"][col] = float(getattr(default, col)), "default"
            continue
        out[col], out["source"][col] = None, None

    # A deposit / late fee of "None" is acceptable (treated as 0 downstream),
    # but a missing PRICE is a hard error for the row.
    out["missing_price"] = out["price_per_day"] is None or out["price_per_day"] <= 0
    return out

"""TrustShield penalty rules (whole rupees, Decimal-safe).

propose_cost turns a category damage rule into a repair-cost RANGE plus a
default (the minimum). The owner may pick any value inside the range freely; a
value ABOVE the range maximum requires an attached quote/invoice AND admin
approval (enforced in the route). Totals are capped at
DAMAGE_CAP_PERCENT_OF_DEPOSIT of the deposit. NOTHING here charges a customer.
"""
from decimal import Decimal, ROUND_HALF_UP


def _rupees(value) -> int:
    return int(Decimal(str(value or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def find_rule(category, rule_key):
    import config as _c
    rules = _c.TS_DAMAGE_RULES.get(category) or _c.TS_DAMAGE_RULES["default"]
    for r in rules:
        if r["key"] == rule_key:
            return r
    return None


def propose_cost(category, rule_key, deposit):
    """Return {min, max, default, percent_of_deposit, key, label, severity}.

    For a 'percent_of_deposit' rule (e.g. lost) the amount is that percent of the
    deposit and min == max == default.
    """
    rule = find_rule(category, rule_key)
    if rule is None:
        return None
    deposit = float(deposit or 0)
    if "percent_of_deposit" in rule:
        amt = _rupees(deposit * float(rule["percent_of_deposit"]) / 100.0)
        return {
            "key": rule["key"], "label": rule.get("label", rule["key"]),
            "severity": rule.get("severity", "major"),
            "min": amt, "max": amt, "default": amt,
            "percent_of_deposit": float(rule["percent_of_deposit"]),
        }
    lo = _rupees(rule.get("min", 0))
    hi = _rupees(rule.get("max", lo))
    if hi < lo:
        hi = lo
    return {
        "key": rule["key"], "label": rule.get("label", rule["key"]),
        "severity": rule.get("severity", "minor"),
        "min": lo, "max": hi, "default": lo,
        "percent_of_deposit": None,
    }


def above_range(category, rule_key, amount, deposit) -> bool:
    """True when the chosen amount exceeds the rule's maximum (needs a quote)."""
    p = propose_cost(category, rule_key, deposit)
    if p is None:
        return False
    return _rupees(amount) > p["max"]


def cap_amount(amount, deposit, cap_percent):
    """Clamp a whole-rupee amount to cap_percent of the deposit."""
    cap = Decimal(str(float(deposit or 0))) * Decimal(str(float(cap_percent))) / Decimal("100")
    cap = _rupees(cap)
    return min(_rupees(amount), cap)


def deposit_status_text(booking, case=None, settlement=None) -> str:
    """Human refund-status line for a TrustShield booking."""
    from models import ReturnRecord
    deposit = float(getattr(booking, "deposit", 0) or 0)
    if deposit <= 0:
        return "No deposit held"

    rec = settlement
    if rec is None:
        rec = ReturnRecord.query.filter_by(booking_id=booking.id).first()
    if rec is not None:
        refunded = _rupees(rec.refund_amount)
        deducted = _rupees(rec.total_deductions)
        if deducted <= 0:
            return f"Refunded Rs {refunded:,}"
        if refunded > 0:
            return f"Partly refunded (Rs {refunded:,} refunded, Rs {deducted:,} deducted)"
        return f"Refunded Rs {refunded:,}"

    # Not settled yet.
    if case is not None and case.status == "disputed":
        return "Held: under dispute"
    if case is not None and case.status == "awaiting_customer":
        return "Held: waiting for condition review"
    # No case but booking on TrustShield and not returned:
    if booking.status in ("picked_up", "awaiting_customer_confirmation"):
        return "Held: waiting for condition review"
    if booking.status in ("approved",):
        return "Held: waiting for condition review"
    return "Held: waiting for condition review"

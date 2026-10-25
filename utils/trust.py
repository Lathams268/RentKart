"""Trust score and smart deposit calculations."""
import config
from models import Booking


def calculate_trust_score(user) -> int:
    """Calculate a user's trust score (0 to 100) based on rental history."""
    if user is None:
        return 50

    score = 50
    clean_count = 0
    penalty = 0

    # Inspect all returned bookings as a renter
    returned_bookings = Booking.query.filter_by(renter_id=user.id, status="returned").all()

    for b in returned_bookings:
        rec = b.return_record
        if not rec:
            continue

        is_late = rec.late_days > 0
        damage = rec.damage_level

        if not is_late and damage == "none":
            clean_count += 1
        else:
            if is_late:
                penalty += 10
            if damage == "minor":
                penalty += 15
            elif damage in ("major", "lost"):
                penalty += 30

    clean_bonus = min(30, clean_count * 10)
    total_score = score + clean_bonus - penalty
    return max(0, min(100, total_score))


def get_trust_level(score: int) -> dict:
    """Return the TRUST_LEVELS tier matching the given score."""
    for lvl in config.TRUST_LEVELS:
        if lvl["min"] <= score <= lvl["max"]:
            return lvl
    return config.TRUST_LEVELS[0]


def get_user_trust(user) -> dict:
    """Return trust score and tier for a user."""
    score = calculate_trust_score(user)
    level = get_trust_level(score)
    return {
        "score": score,
        "level": level,
        "multiplier": level["deposit_multiplier"],
        "label": level["label"],
        "color": level["color"],
    }

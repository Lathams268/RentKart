"""Subscription plan utilities and feature gating."""
from config import PLANS


def get_plan(user) -> dict:
    """Return the active plan dictionary for a given user."""
    if not user:
        return PLANS["free"]
    plan_key = getattr(user, "current_plan", lambda: "free")()
    return PLANS.get(plan_key, PLANS["free"])


def can_add_item(user) -> bool:
    """Check if the user is allowed to list another item under their current plan limit."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    from models import Item
    plan = get_plan(user)
    current_count = Item.query.filter_by(owner_id=user.id).count()
    return current_count < plan.get("max_items", 5)


def has_feature(user, name: str) -> bool:
    """Check if the user's active plan grants a specific boolean feature."""
    plan = get_plan(user)
    return bool(plan.get(name, False))


def commission_for(user) -> float:
    """Return the platform commission percentage for the user's active plan."""
    plan = get_plan(user)
    return float(plan.get("commission_percent", 10))

"""Shop utilities for RentKart – slug generation and shop helpers."""
import re
from models import User


def generate_shop_slug(shop_name: str, user_id: int = None) -> str:
    """Auto-generate a clean, unique slug from shop_name.
    
    Transforms name to lowercase, replaces non-alphanumeric chars with hyphens,
    and appends a number if the slug is already taken.
    """
    clean_name = (shop_name or "").lower().strip()
    base_slug = re.sub(r"[^a-z0-9]+", "-", clean_name).strip("-")
    if not base_slug:
        base_slug = "shop"

    slug = base_slug
    counter = 1
    while True:
        query = User.query.filter_by(shop_slug=slug)
        if user_id is not None:
            query = query.filter(User.id != user_id)
        if not query.first():
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1

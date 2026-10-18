"""tools/photo_report.py - report RentKart demo-photo coverage.

Reads config.py and the database and prints, for every category / sub-category
and for the first 30 seeded items, whether a real photo file exists. For every
missing one it prints the exact file path to create and a suggested free-stock
search phrase. It also validates existing files (size, width, image integrity,
CREDITS.txt coverage).

Usage:
    python tools/photo_report.py            # report only
    python tools/photo_report.py --resize   # shrink oversized photos in place
"""
import argparse
import os
import shutil
import sys

# Make the project importable when run as `python tools/photo_report.py`.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config
from utils.illustrations import (
    DEMO_PHOTOS_DIR,
    PHOTO_EXTS,
    item_slug,
    item_picture,
    match_subcategory,
    _demo_photo_for_slug,
    _stock_photo,
)

MAX_BYTES = 800 * 1024          # warn above 800 KB
MAX_WIDTH = 1600                # warn above 1600 px
TARGET_WIDTH = 1200             # --resize shrinks to this width
JPEG_QUALITY = 82

# Suggested free-stock search phrases per category / sub-category key.
SUGGESTIONS = {
    # categories
    "clothes": "folded indian ethnic outfit on plain background",
    "books": "stack of books on wooden table",
    "farm_tools": "farm tractor in field",
    "electronics": "camera and gadgets flat lay",
    "event_items": "wedding stage decoration",
    # clothes
    "lehenga": "colorful embroidered lehenga folded",
    "saree": "silk saree draped on mannequin",
    "sherwani": "groom sherwani on hanger",
    "kurta": "cotton kurta pajama set",
    "kurta_set": "kids festive kurta set",
    "kids_wear": "children ethnic clothing",
    "western": "formal western dress shirt",
    "gown": "evening party gown",
    "blazer": "navy blazer suit jacket",
    "frock": "girls party frock dress",
    "anarkali": "anarkali suit flared gown",
    # books
    "comedy": "open book with a laughing face doodle",
    "spiritual": "open book with a diya",
    "motivation": "open book with a sunrise background",
    "self_help": "self help book with notebook",
    "fiction": "novel book on cozy reading chair",
    "biography": "hardcover biography book portrait",
    "mythology": "indian mythology story book",
    "children_books": "colorful children picture book",
    "education": "textbook stack with study notes",
    "business_books": "business finance book on desk",
    "health": "yoga and health book with mat",
    "poetry": "poetry book with fountain pen",
    "other_books": "assorted books on a shelf",
    # farm_tools
    "tractor": "green tractor in farm field",
    "attachments": "tractor rotavator implement",
    "water_tank": "plastic water storage tank",
    "sprayer": "knapsack power sprayer",
    "harvesting": "combine harvester in crop field",
    "hand_tools": "spade and hand farm tools",
    "power_tools": "cordless power drill",
    "soil": "farmer preparing soil bed",
    "transport": "wooden farm cart trolley",
    # electronics
    "camera": "dslr camera with lens",
    "laptop": "open laptop on desk",
    "projector": "home cinema projector",
    "speaker": "bluetooth party speaker",
    "microphone": "studio condenser microphone",
    "drone": "camera quadcopter drone",
    "lights": "led string stage lights",
    "generator": "portable petrol generator",
    "console": "gaming console with controller",
    "screen": "flat screen led tv",
    # event_items
    "decoration": "flower balloon event decoration",
    "chairs": "rows of banquet chairs",
    "tent": "marriage pandal tent shamiyana",
    "stage_lighting": "stage lighting truss",
    "catering": "catering serving utensils",
    "stage": "event stage backdrop",
    "festival_items": "diwali diya festival decor",
    "photobooth": "photo booth with props",
}


def _suggest(key, category=""):
    return SUGGESTIONS.get(key) or SUGGESTIONS.get(category) or \
        f"{str(key).replace('_', ' ')} photo"


def _find(dir_path, base):
    """Return (abs_path, rel_posix) for the first matching extension, else None."""
    for ext in PHOTO_EXTS:
        full = os.path.join(dir_path, base + ext)
        if os.path.isfile(full):
            return full, os.path.relpath(full, ROOT).replace("\\", "/")
    return None, None


def load_credits():
    """Basenames listed in CREDITS.txt (blank/`#` lines skipped)."""
    path = os.path.join(DEMO_PHOTOS_DIR, "CREDITS.txt")
    names = set()
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                fname = line.split(",")[0].strip().lower()
                if fname:
                    names.add(fname)
    return names


def _open_image(full):
    from PIL import Image
    with Image.open(full) as im:
        im.load()
        return im.size  # (width, height)


def inspect_file(full, credits):
    """Return a list of warning strings for one photo file."""
    warns = []
    try:
        size = os.path.getsize(full)
    except OSError:
        return ["could not read file"]
    if size > MAX_BYTES:
        warns.append(f"TOO BIG {size // 1024} KB (limit {MAX_BYTES // 1024} KB)")
    try:
        width, _ = _open_image(full)
        if width > MAX_WIDTH:
            warns.append(f"TOO WIDE {width} px (limit {MAX_WIDTH} px)")
    except Exception:
        warns.append("INVALID image (could not open)")
    if os.path.basename(full).lower() not in credits:
        warns.append("NO CREDITS.txt line")
    return warns


def iter_photo_files():
    """All real photo files under demo_photos/ (excluding _originals backups)."""
    if not os.path.isdir(DEMO_PHOTOS_DIR):
        return
    for dirpath, dirnames, filenames in os.walk(DEMO_PHOTOS_DIR):
        dirnames[:] = [d for d in dirnames if d != "_originals"]
        for name in filenames:
            if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                yield os.path.join(dirpath, name)


def report_categories():
    print("=" * 70)
    print("CATEGORY / SUB-CATEGORY STOCK PHOTOS")
    print("=" * 70)
    for cat_key, cat in config.CATEGORIES.items():
        stock_dir = os.path.join(DEMO_PHOTOS_DIR, "stock", cat_key)
        print(f"\n[{cat_key}]")
        # category default
        full, rel = _find(stock_dir, "default")
        if full:
            print(f"  OK      default -> {rel}")
        else:
            create = f"static/demo_photos/stock/{cat_key}/default.jpg"
            print(f"  MISSING {create}  (search: {_suggest(cat_key)})")
        # sub-categories
        for sc in cat.get("subcategories", []):
            key = sc["key"]
            full, rel = _find(stock_dir, key)
            if full:
                print(f"  OK      {key} -> {rel}")
            else:
                create = f"static/demo_photos/stock/{cat_key}/{key}.jpg"
                print(f"  MISSING {create}  (search: {_suggest(key, cat_key)})")


def report_items():
    print("\n" + "=" * 70)
    print("FIRST 30 SEEDED ITEMS")
    print("=" * 70)
    from app import create_app
    from models import Item
    app = create_app()
    with app.app_context():
        items = Item.query.order_by(Item.id).limit(30).all()
    if not items:
        print("(no items in the database - run: python seed.py)")
        return
    for it in items:
        pic = item_picture(it)
        slug = item_slug(it)
        line = f"  {it.title[:44]:44} [{it.category:11}] -> {pic['kind']:12} {pic['path']}"
        print(line)
        if pic["kind"] in ("illustration", "category", "initials"):
            sc = match_subcategory(it.category, it.get_attributes())
            key = sc["key"] if sc else it.category
            own = f"static/demo_photos/{slug}.jpg"
            print(f"      (no photo, using drawing; add {own}  search: {_suggest(key, it.category)})")


def report_files_and_credits():
    print("\n" + "=" * 70)
    print("PHOTO FILE CHECKS (size / width / validity / credits)")
    print("=" * 70)
    credits = load_credits()
    found = False
    for full in iter_photo_files():
        found = True
        rel = os.path.relpath(full, ROOT).replace("\\", "/")
        warns = inspect_file(full, credits)
        if warns:
            print(f"  WARN  {rel}: " + "; ".join(warns))
        else:
            print(f"  OK    {rel}")
    if not found:
        print("  (no photo files yet under static/demo_photos/)")


def resize_photos():
    print("\n" + "=" * 70)
    print("RESIZING (target width %d px, JPEG quality %d)" % (TARGET_WIDTH, JPEG_QUALITY))
    print("=" * 70)
    from PIL import Image
    originals_dir = os.path.join(DEMO_PHOTOS_DIR, "_originals")
    changed = 0
    for full in iter_photo_files():
        try:
            size = os.path.getsize(full)
            width, height = _open_image(full)
        except Exception:
            print(f"  SKIP  {os.path.relpath(full, ROOT)} (invalid image)")
            continue
        if width <= TARGET_WIDTH and size <= MAX_BYTES:
            continue
        # backup keeping the relative layout
        rel = os.path.relpath(full, DEMO_PHOTOS_DIR)
        backup = os.path.join(originals_dir, rel)
        os.makedirs(os.path.dirname(backup), exist_ok=True)
        shutil.copy2(full, backup)
        # resize
        with Image.open(full) as im:
            if width > TARGET_WIDTH:
                new_h = int(round(height * TARGET_WIDTH / width))
                im = im.resize((TARGET_WIDTH, new_h), Image.LANCZOS)
            ext = os.path.splitext(full)[1].lower()
            if ext in (".jpg", ".jpeg"):
                im.convert("RGB").save(full, "JPEG", quality=JPEG_QUALITY, optimize=True)
            elif ext == ".webp":
                im.save(full, "WEBP", quality=JPEG_QUALITY)
            else:  # png
                im.save(full, "PNG", optimize=True)
        changed += 1
        print(f"  DONE  {os.path.relpath(full, ROOT)} (was {width}px, {size // 1024} KB)")
    if not changed:
        print("  (nothing oversized to resize)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="RentKart demo photo coverage report")
    ap.add_argument("--resize", action="store_true",
                    help="shrink oversized photos in place (backups to static/demo_photos/_originals/)")
    args = ap.parse_args(argv)

    print(f"demo_photos root: {DEMO_PHOTOS_DIR}\n")
    report_categories()
    report_files_and_credits()
    report_items()
    if args.resize:
        resize_photos()
    return 0


if __name__ == "__main__":
    sys.exit(main())

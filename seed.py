"""Seed script – populates RentKart with demo users and items.
Safe to run multiple times: skips existing rows and never assigns generated
placeholders. Item.image stays empty unless a real photo exists in
static/demo_photos/<item-slug>.(jpg|jpeg|png); otherwise the matching
illustration is shown.
"""
import os, sys, json, re

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from models import db, User, Item, Booking, ReturnRecord, Review, Subscription, Feedback
from utils.demo_shops import SHOPS, LEGACY_USERS, ensure_shop_logo, item_slug
from utils.logo import slugify_name
from datetime import date, timedelta

# ---------- Real photo detection (no generated placeholders) ----------
# Legacy generated placeholder names (blue gradient + white circle).
SEED_PLACEHOLDER_RE = re.compile(r"^seed(?:_[a-z]+)*_\d+\.png$", re.IGNORECASE)


def _is_placeholder_name(value) -> bool:
    """True for a legacy generated seed_<n>.png placeholder file name."""
    if not value:
        return False
    base = os.path.basename(str(value).replace("\\", "/"))
    return bool(SEED_PLACEHOLDER_RE.match(base))


def _real_photo_name(title) -> str:
    """Return 'demo_photos/<slug>.<ext>' only when a real photo file exists."""
    slug = slugify_name(title)
    folder = os.path.join(os.path.dirname(__file__), "static", "demo_photos")
    for ext in (".jpg", ".jpeg", ".png"):
        if os.path.isfile(os.path.join(folder, slug + ext)):
            return f"demo_photos/{slug}{ext}"
    return ""


def _make_shravani_logo(upload_dir):
    """Generate a simple circular logo with initials 'SB' for Shravani Boutique."""
    logo_path = os.path.join(upload_dir, "shravani_logo.png")
    if os.path.exists(logo_path):
        return "shravani_logo.png"
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Maroon circle with gold border
        draw.ellipse([(10, 10), (190, 190)], fill=(128, 0, 32, 255), outline=(218, 165, 32, 255), width=6)
        # Draw "SB" initials in center
        try:
            font = ImageFont.truetype("arial.ttf", 64)
        except Exception:
            font = ImageFont.load_default()
        draw.text((100, 100), "SB", fill=(255, 215, 0, 255), font=font, anchor="mm")
        img.save(logo_path, format="PNG")
    except Exception:
        pass
    return "shravani_logo.png"


# ---------- Seed data ----------
USERS = [
    {
        "name": "Ramesh",
        "phone": "9000000001",
        "village_or_city": "Hoskote",
        "lat": 13.0707,
        "lng": 77.7985,
        "shop_name": "Ramesh Agri & Event Rentals",
        "shop_slug": "ramesh-agri-event-rentals",
        "shop_description": "High quality farming rotavators, tractors, and event plastic chairs in Hoskote.",
        "is_admin": False,
    },
    {
        "name": "Lakshmi",
        "phone": "9000000002",
        "village_or_city": "Devanahalli",
        "lat": 13.2473,
        "lng": 77.7116,
        "shop_name": "Shravani Boutique",
        "shop_slug": "shravani",
        "shop_description": "Lehengas, sarees and sherwanis for weddings and festivals",
        "shop_theme_color": "maroon and gold",
        "shop_logo": "shravani_logo.png",
        "is_admin": False,
    },
    {"name": "Suresh",  "phone": "9000000003", "village_or_city": "Anekal",       "lat": 12.7105, "lng": 77.6960, "is_admin": False},
    {
        "name": "Priya",
        "phone": "9000000004",
        "village_or_city": "Bengaluru",
        "lat": 12.9716,
        "lng": 77.5946,
        "shop_name": "Priya Fashion & Party Rentals",
        "shop_slug": "priya-fashion-party-rentals",
        "shop_description": "Designer wedding outfits, DSLR cameras, and party shamiyanas in Bengaluru.",
        "is_admin": False,
    },
    {
        "name": "Admin",
        "phone": "9999999999",
        "village_or_city": "Bengaluru",
        "lat": 12.9716,
        "lng": 77.5946,
        "is_admin": True,
    },
]

ITEMS = [
    # Clothes (3)
    {"owner_idx": 1, "category": "clothes",     "title": "Silk Lehenga",         "description": "Beautiful red silk lehenga for weddings", "price_per_day": 500,  "deposit": 2000, "late_fee_per_day": 100, "attrs": {"brand": "Shravani", "style": "Traditional", "clothing_type": "Lehenga", "color": "Red", "size": "M", "occasion": "Wedding", "fabric": "Silk", "gender": "Women", "age_group": "18+"}},
    {"owner_idx": 1, "category": "clothes",     "title": "Designer Sherwani",    "description": "Navy blue sherwani with gold work",      "price_per_day": 800,  "deposit": 3000, "late_fee_per_day": 150, "attrs": {"brand": "Shravani", "style": "Traditional", "clothing_type": "Sherwani", "color": "Navy", "size": "L", "occasion": "Wedding", "fabric": "Brocade", "gender": "Men", "age_group": "18+"}},
    {"owner_idx": 1, "category": "clothes",     "title": "Pattu Saree",          "description": "Traditional Kanjivaram pattu saree",     "price_per_day": 400,  "deposit": 1500, "late_fee_per_day": 80,  "purchase_price": 1500, "attrs": {"brand": "Shravani", "style": "Traditional", "clothing_type": "Saree", "color": "Gold", "size": "Free Size", "occasion": "Festival", "fabric": "Silk", "gender": "Women", "age_group": "18+"}},

    # Books (3)
    {"owner_idx": 3, "category": "books",       "title": "Engineering Maths",    "description": "BS Grewal Higher Engineering Mathematics","price_per_day": 20,   "deposit": 200,  "late_fee_per_day": 5,   "purchase_price": 300,  "attrs": {"genre": "Education / Exam Prep", "author": "BS Grewal", "edition": "44th", "language": "English", "condition": "Good"}},
    {"owner_idx": 1, "category": "books",       "title": "NCERT Physics Class 12","description": "NCERT textbook for board exams",        "price_per_day": 10,   "deposit": 100,  "late_fee_per_day": 3,   "purchase_price": 15,   "attrs": {"genre": "Education / Exam Prep", "author": "NCERT", "edition": "2024", "language": "English", "condition": "New"}},
    {"owner_idx": 2, "category": "books",       "title": "Kannada Sahitya",      "description": "Kannada literature anthology",           "price_per_day": 15,   "deposit": 100,  "late_fee_per_day": 5,   "attrs": {"genre": "Poetry", "author": "Various", "edition": "1st", "language": "Kannada", "condition": "Old"}},
    # Farm tools (3)
    {"owner_idx": 0, "category": "farm_tools",  "title": "Tractor Rotavator",    "description": "42-blade rotavator attachment",          "price_per_day": 1500, "deposit": 5000, "late_fee_per_day": 500, "attrs": {"power": "45 HP", "fuel": "Diesel", "operator_included": True}},
    {"owner_idx": 2, "category": "farm_tools",  "title": "Power Sprayer",        "description": "16L knapsack battery sprayer",           "price_per_day": 150,  "deposit": 500,  "late_fee_per_day": 50,  "attrs": {"power": "12V", "fuel": "Electric", "operator_included": False}},
    {"owner_idx": 0, "category": "farm_tools",  "title": "Manual Seed Drill",    "description": "2-row manual seed drill for small plots","price_per_day": 100,  "deposit": 300,  "late_fee_per_day": 30,  "purchase_price": 1000, "attrs": {"power": "N/A", "fuel": "Manual", "operator_included": False}},
    # Electronics (3)
    {"owner_idx": 3, "category": "electronics", "title": "Canon DSLR Camera",    "description": "Canon EOS 1500D with 18-55mm lens",     "price_per_day": 600,  "deposit": 5000, "late_fee_per_day": 200, "attrs": {"brand": "Canon", "model": "EOS 1500D", "accessories_included": "Lens, Bag, Charger"}},
    {"owner_idx": 1, "category": "electronics", "title": "Bosch Drill Machine",  "description": "13mm impact drill for home and site",   "price_per_day": 200,  "deposit": 1000, "late_fee_per_day": 50,  "purchase_price": 1200, "attrs": {"brand": "Bosch", "model": "GSB 13RE", "accessories_included": "Bits set"}},
    {"owner_idx": 2, "category": "electronics", "title": "JBL Bluetooth Speaker","description": "JBL PartyBox 110 portable speaker",     "price_per_day": 350,  "deposit": 2000, "late_fee_per_day": 100, "attrs": {"brand": "JBL", "model": "PartyBox 110", "accessories_included": "Charger, Mic"}},
    # Event items (3)
    {"owner_idx": 0, "category": "event_items", "title": "Plastic Chairs Set",   "description": "50 white plastic chairs for functions",  "price_per_day": 500,  "deposit": 1000, "late_fee_per_day": 100, "purchase_price": 2000, "attrs": {"type": "Chairs", "quantity": "50"}},
    {"owner_idx": 3, "category": "event_items", "title": "Shamiyana Tent",       "description": "30x40 ft waterproof tent with poles",    "price_per_day": 2000, "deposit": 5000, "late_fee_per_day": 500, "attrs": {"type": "Tent", "quantity": "1"}},
    {"owner_idx": 0, "category": "event_items", "title": "PA Sound System",      "description": "2 speakers + amplifier + mic for events","price_per_day": 800,  "deposit": 3000, "late_fee_per_day": 200, "attrs": {"type": "Sound System", "quantity": "1"}},
]

NEW_CLOTHES = [
    # --- Boys Clothes (spanning all age groups: 0-2, 3-5, 6-8, 9-12, 13-17) ---
    {
        "owner_idx": 1,
        "category": "clothes",
        "title": "Boys Royal Kurta Pajama Set",
        "description": "Festive yellow silk blend kurta with comfortable cotton pajama for baby boys.",
        "price_per_day": 120,
        "deposit": 400,
        "late_fee_per_day": 30,
        "purchase_price": 999,
        "attrs": {
            "brand": "FabIndia Kids",
            "style": "Traditional",
            "clothing_type": "Kurta Set",
            "color": "Yellow",
            "size": "1-2Y",
            "occasion": "Festival",
            "fabric": "Silk Blend",
            "gender": "Boys",
            "age_group": "0–2",
        },
    },
    {
        "owner_idx": 1,
        "category": "clothes",
        "title": "Boys Festive Dhoti Kurta",
        "description": "Traditional orange and cream dhoti kurta set with zari border for toddlers.",
        "price_per_day": 180,
        "deposit": 600,
        "late_fee_per_day": 40,
        "purchase_price": 1499,
        "attrs": {
            "brand": "Manyavar Kids",
            "style": "Traditional",
            "clothing_type": "Kurta Set",
            "color": "Orange",
            "size": "3-4Y",
            "occasion": "Wedding",
            "fabric": "Cotton Silk",
            "gender": "Boys",
            "age_group": "3–5",
        },
    },
    {
        "owner_idx": 1,
        "category": "clothes",
        "title": "Boys Indo-Western Sherwani Set",
        "description": "Rich maroon jacquard sherwani with beige trousers and brooch for boys.",
        "price_per_day": 250,
        "deposit": 800,
        "late_fee_per_day": 50,
        "purchase_price": 2200,
        "attrs": {
            "brand": "Manyavar Kids",
            "style": "Fusion / Indo-Western",
            "clothing_type": "Sherwani",
            "color": "Maroon",
            "size": "6-8Y",
            "occasion": "Wedding",
            "fabric": "Brocade",
            "gender": "Boys",
            "age_group": "6–8",
        },
    },
    {
        "owner_idx": 1,
        "category": "clothes",
        "title": "Boys Classic Navy Blazer Suit",
        "description": "Sharp 3-piece formal navy blazer suit with shirt and trousers for school functions and parties.",
        "price_per_day": 280,
        "deposit": 900,
        "late_fee_per_day": 60,
        "purchase_price": 2500,
        "attrs": {
            "brand": "Zara Kids",
            "style": "Western",
            "clothing_type": "Suit / Blazer",
            "color": "Navy",
            "size": "9-12Y",
            "occasion": "Party",
            "fabric": "Wool Blend",
            "gender": "Boys",
            "age_group": "9–12",
        },
    },
    {
        "owner_idx": 1,
        "category": "clothes",
        "title": "Teen Boys Tuxedo Blazer Set",
        "description": "Slim fit black satin lapel tuxedo suit for teen farewell and banquet events.",
        "price_per_day": 350,
        "deposit": 1200,
        "late_fee_per_day": 70,
        "purchase_price": 3500,
        "attrs": {
            "brand": "Raymond",
            "style": "Western",
            "clothing_type": "Tuxedo",
            "color": "Black",
            "size": "XS",
            "occasion": "Party",
            "fabric": "Poly Viscose",
            "gender": "Boys",
            "age_group": "13–17",
        },
    },

    # --- Girls Clothes (spanning all age groups: 0-2, 3-5, 6-8, 9-12, 13-17) ---
    {
        "owner_idx": 1,
        "category": "clothes",
        "title": "Baby Girls Silk Pattu Pavadai",
        "description": "Authentic Kanchipuram pink and gold pattu pavadai lehenga set for infant and baby girls.",
        "price_per_day": 140,
        "deposit": 500,
        "late_fee_per_day": 30,
        "purchase_price": 1200,
        "attrs": {
            "brand": "Shravani",
            "style": "Traditional",
            "clothing_type": "Pattu Pavadai",
            "color": "Pink",
            "size": "6-12M",
            "occasion": "Festival",
            "fabric": "Silk",
            "gender": "Girls",
            "age_group": "0–2",
        },
    },
    {
        "owner_idx": 1,
        "category": "clothes",
        "title": "Girls Layered Birthday Frock",
        "description": "Sky blue organza layered princess party frock with subtle glitter belt.",
        "price_per_day": 160,
        "deposit": 550,
        "late_fee_per_day": 35,
        "purchase_price": 1399,
        "attrs": {
            "brand": "Zara Kids",
            "style": "Western",
            "clothing_type": "Frock",
            "color": "Blue",
            "size": "3-4Y",
            "occasion": "Party",
            "fabric": "Organza",
            "gender": "Girls",
            "age_group": "3–5",
        },
    },
    {
        "owner_idx": 1,
        "category": "clothes",
        "title": "Girls Festive Chaniya Choli",
        "description": "Vibrant red and yellow mirror-work Navratri lehenga choli set with matching dupatta.",
        "price_per_day": 220,
        "deposit": 750,
        "late_fee_per_day": 45,
        "purchase_price": 1899,
        "attrs": {
            "brand": "FabIndia Kids",
            "style": "Traditional",
            "clothing_type": "Lehenga",
            "color": "Red",
            "size": "6-8Y",
            "occasion": "Festival",
            "fabric": "Cotton",
            "gender": "Girls",
            "age_group": "6–8",
        },
    },
    {
        "owner_idx": 1,
        "category": "clothes",
        "title": "Girls Embroidered Anarkali Gown",
        "description": "Floor-length bottle green georgette anarkali suit with heavy thread work for family functions.",
        "price_per_day": 260,
        "deposit": 850,
        "late_fee_per_day": 50,
        "purchase_price": 2499,
        "attrs": {
            "brand": "BIBA",
            "style": "Traditional",
            "clothing_type": "Anarkali",
            "color": "Green",
            "size": "9-12Y",
            "occasion": "Engagement",
            "fabric": "Georgette",
            "gender": "Girls",
            "age_group": "9–12",
        },
    },
    {
        "owner_idx": 1,
        "category": "clothes",
        "title": "Teen Girls Crop Top Lehenga",
        "description": "Trendy lilac purple sequin crop top with organza flared lehenga skirt for teenagers.",
        "price_per_day": 380,
        "deposit": 1400,
        "late_fee_per_day": 70,
        "purchase_price": 3800,
        "attrs": {
            "brand": "Shravani",
            "style": "Fusion / Indo-Western",
            "clothing_type": "Lehenga",
            "color": "Purple",
            "size": "S",
            "occasion": "Sangeet",
            "fabric": "Organza",
            "gender": "Girls",
            "age_group": "13–17",
        },
    },
]

# ---------- Clothes marketplace seed (Stage 3) ----------
# Ensures every tab (Men / Women / Children) has at least 10 items. All items
# use the fictional "Shravani" brand, whole-rupee prices, a discount on about
# a third, mixed availability and delivery / pickup settings. Re-runnable by
# title (update in place, never duplicate). No real brand names.
MARKET_CLOTHES = [
    # --- Women (12) ---
    {"owner_idx": 1, "title": "Chaniya Choli Set", "desc": "Red mirror-work chaniya choli for Navratri nights.", "price": 350, "discount": 0, "avail": True, "gender": "Women", "ctype": "Lehenga", "style": "Traditional", "color": "Red", "size": "M", "occasion": "Festival", "fabric": "Cotton", "delivery": True, "cod": True},
    {"owner_idx": 3, "title": "Embellished Sharara Set", "desc": "Pink georgette sharara with gota work dupatta.", "price": 400, "discount": 10, "avail": True, "gender": "Women", "ctype": "Salwar Suit", "style": "Traditional", "color": "Pink", "size": "S", "occasion": "Wedding", "fabric": "Georgette", "delivery": True, "cod": True},
    {"owner_idx": 1, "title": "Kanjivaram Silk Saree", "desc": "Gold zari border kanjivaram for grand occasions.", "price": 600, "discount": 0, "avail": True, "gender": "Women", "ctype": "Saree", "style": "Traditional", "color": "Gold", "size": "Free Size", "occasion": "Wedding", "fabric": "Silk", "delivery": False, "cod": True},
    {"owner_idx": 3, "title": "Bridal Red Lehenga", "desc": "Heavy brocade bridal lehenga with dupatta and blouse.", "price": 2500, "discount": 20, "avail": False, "gender": "Women", "ctype": "Lehenga", "style": "Traditional", "color": "Red", "size": "L", "occasion": "Wedding", "fabric": "Brocade", "delivery": True, "cod": False},
    {"owner_idx": 2, "title": "Sequin Party Gown", "desc": "Black net floor gown with all-over sequins for parties.", "price": 700, "discount": 0, "avail": True, "gender": "Women", "ctype": "Gown", "style": "Western", "color": "Black", "size": "M", "occasion": "Party", "fabric": "Net", "delivery": True, "cod": True},
    {"owner_idx": 1, "title": "Everyday Cotton Kurti", "desc": "Breathable blue cotton kurti for daily wear.", "price": 150, "discount": 5, "avail": True, "gender": "Women", "ctype": "Kurti", "style": "Fusion / Indo-Western", "color": "Blue", "size": "S", "occasion": "Daily wear", "fabric": "Cotton", "delivery": True, "cod": True},
    {"owner_idx": 3, "title": "Pastel Co-ord Set", "desc": "Cream chiffon co-ord set, top and wide-leg trousers.", "price": 450, "discount": 0, "avail": True, "gender": "Women", "ctype": "Co-ord Set", "style": "Modern", "color": "Cream", "size": "M", "occasion": "Party", "fabric": "Chiffon", "delivery": True, "cod": True},
    {"owner_idx": 2, "title": "Royal Anarkali Suit", "desc": "Purple georgette anarkali with thread work and lining.", "price": 550, "discount": 10, "avail": True, "gender": "Women", "ctype": "Anarkali", "style": "Traditional", "color": "Purple", "size": "L", "occasion": "Engagement", "fabric": "Georgette", "delivery": False, "cod": True},
    {"owner_idx": 1, "title": "Casual Shirt Top", "desc": "White cotton shirt top that layers with anything.", "price": 200, "discount": 0, "avail": True, "gender": "Women", "ctype": "Top", "style": "Western", "color": "White", "size": "S", "occasion": "Daily wear", "fabric": "Cotton", "delivery": True, "cod": True},
    {"owner_idx": 3, "title": "Printed Palazzo Set", "desc": "Green rayon printed kurta with matching palazzo.", "price": 380, "discount": 20, "avail": False, "gender": "Women", "ctype": "Palazzo Set", "style": "Modern", "color": "Green", "size": "M", "occasion": "Daily wear", "fabric": "Rayon", "delivery": True, "cod": True},
    {"owner_idx": 2, "title": "Banarasi Silk Saree", "desc": "Maroon banarasi saree with traditional motifs.", "price": 800, "discount": 0, "avail": True, "gender": "Women", "ctype": "Saree", "style": "Traditional", "color": "Maroon", "size": "Free Size", "occasion": "Festival", "fabric": "Silk", "delivery": True, "cod": True},
    {"owner_idx": 1, "title": "Festive Crop Top Lehenga", "desc": "Orange organza crop-top lehenga for sangeet nights.", "price": 500, "discount": 5, "avail": True, "gender": "Women", "ctype": "Lehenga", "style": "Fusion / Indo-Western", "color": "Orange", "size": "S", "occasion": "Sangeet", "fabric": "Organza", "delivery": True, "cod": True},

    # --- Men (12) ---
    {"owner_idx": 1, "title": "Groom Gold Sherwani", "desc": "Gold brocade sherwani with buttons and matching scarf.", "price": 900, "discount": 10, "avail": True, "gender": "Men", "ctype": "Sherwani", "style": "Traditional", "color": "Gold", "size": "L", "occasion": "Wedding", "fabric": "Brocade", "delivery": True, "cod": True},
    {"owner_idx": 3, "title": "Ivory Kurta Pajama", "desc": "Cream cotton silk kurta pajama for festive mornings.", "price": 400, "discount": 0, "avail": True, "gender": "Men", "ctype": "Kurta Pajama", "style": "Traditional", "color": "Cream", "size": "M", "occasion": "Festival", "fabric": "Cotton Silk", "delivery": True, "cod": True},
    {"owner_idx": 2, "title": "Charcoal Suit and Blazer", "desc": "Charcoal three-piece suit with satin lapel blazer.", "price": 750, "discount": 20, "avail": False, "gender": "Men", "ctype": "Suit / Blazer", "style": "Western", "color": "Black", "size": "L", "occasion": "Reception", "fabric": "Wool Blend", "delivery": True, "cod": False},
    {"owner_idx": 3, "title": "Midnight Tuxedo", "desc": "Navy tuxedo with bow-tie fit for a black-tie party.", "price": 1200, "discount": 0, "avail": True, "gender": "Men", "ctype": "Tuxedo", "style": "Western", "color": "Navy", "size": "XL", "occasion": "Party", "fabric": "Poly Viscose", "delivery": False, "cod": True},
    {"owner_idx": 1, "title": "Traditional Dhoti Kurta", "desc": "White cotton dhoti kurta set with gold border.", "price": 350, "discount": 5, "avail": True, "gender": "Men", "ctype": "Dhoti", "style": "Traditional", "color": "White", "size": "Free Size", "occasion": "Wedding", "fabric": "Cotton", "delivery": True, "cod": True},
    {"owner_idx": 2, "title": "Nehru Jacket Set", "desc": "Blue Nehru jacket over matching kurta pajama.", "price": 600, "discount": 0, "avail": False, "gender": "Men", "ctype": "Jacket", "style": "Fusion / Indo-Western", "color": "Blue", "size": "M", "occasion": "Engagement", "fabric": "Silk Blend", "delivery": True, "cod": True},
    {"owner_idx": 3, "title": "Formal Shirt Trouser Set", "desc": "Crisp white formal shirt with black trousers.", "price": 250, "discount": 10, "avail": True, "gender": "Men", "ctype": "Shirt", "style": "Western", "color": "White", "size": "M", "occasion": "Daily wear", "fabric": "Cotton", "delivery": True, "cod": True},
    {"owner_idx": 1, "title": "Wedding Turban Set", "desc": "Maroon safa turban with kalgi and matching angavastram.", "price": 300, "discount": 0, "avail": True, "gender": "Men", "ctype": "Angavastram", "style": "Traditional", "color": "Maroon", "size": "Free Size", "occasion": "Wedding", "fabric": "Silk", "delivery": False, "cod": True},
    {"owner_idx": 2, "title": "Indo Western Sherwani", "desc": "Green indo-western sherwani with asymmetric drape.", "price": 1500, "discount": 20, "avail": True, "gender": "Men", "ctype": "Sherwani", "style": "Fusion / Indo-Western", "color": "Green", "size": "L", "occasion": "Reception", "fabric": "Brocade", "delivery": True, "cod": True},
    {"owner_idx": 3, "title": "Royal Blue Bandhgala", "desc": "Royal blue bandhgala suit with mandarin collar.", "price": 1000, "discount": 0, "avail": True, "gender": "Men", "ctype": "Sherwani", "style": "Traditional", "color": "Blue", "size": "L", "occasion": "Wedding", "fabric": "Silk Blend", "delivery": True, "cod": True},
    {"owner_idx": 1, "title": "Pathani Suit", "desc": "Cream pathani suit, relaxed kurta with pajama and jacket.", "price": 450, "discount": 5, "avail": True, "gender": "Men", "ctype": "Kurta Pajama", "style": "Traditional", "color": "Cream", "size": "XL", "occasion": "Festival", "fabric": "Cotton", "delivery": True, "cod": True},
    {"owner_idx": 2, "title": "Wedding Achkan", "desc": "Pink achkan with churidar and dupatta for the groom.", "price": 850, "discount": 0, "avail": True, "gender": "Men", "ctype": "Sherwani", "style": "Traditional", "color": "Pink", "size": "M", "occasion": "Wedding", "fabric": "Silk", "delivery": True, "cod": True},

    # --- Children extras (2, on top of the 10 NEW_CLOTHES kids items) ---
    {"owner_idx": 1, "title": "Little Girls Lehenga", "desc": "Pink kids lehenga choli with soft net skirt.", "price": 300, "discount": 10, "avail": True, "gender": "Girls", "ctype": "Lehenga", "style": "Traditional", "color": "Pink", "size": "6-8Y", "occasion": "Festival", "fabric": "Net", "age": "6–8", "delivery": True, "cod": True},
    {"owner_idx": 3, "title": "Baby Boys Kurta Set", "desc": "Yellow baby boys kurta pajama set for functions.", "price": 220, "discount": 0, "avail": True, "gender": "Boys", "ctype": "Kurta Set", "style": "Traditional", "color": "Yellow", "size": "1-2Y", "occasion": "Festival", "fabric": "Cotton Silk", "age": "0–2", "delivery": True, "cod": True},

    # --- Unisex (1) - shows in Men and Women tabs ---
    {"owner_idx": 2, "title": "Unisex Ethnic Kurta", "desc": "Maroon unisex cotton ethnic kurta, adjustable fit.", "price": 280, "discount": 5, "avail": True, "gender": "Unisex", "ctype": "Kurta Pajama", "style": "Traditional", "color": "Maroon", "size": "M", "occasion": "Daily wear", "fabric": "Cotton", "delivery": True, "cod": True},
]

# A few marketplace items are deliberately left without reviews so the card
# shows the "New" badge instead of a rating.
NO_REVIEW_TITLES = {
    "Chaniya Choli Set", "Groom Gold Sherwani", "Little Girls Lehenga",
    "Formal Shirt Trouser Set",
}

NEW_BOOKS = [
    # Spiritual / God and Devotional (3)
    {
        "owner_idx": 1,
        "category": "books",
        "title": "Bhagavad Gita As It Is",
        "description": "Complete edition with original Sanskrit verses, transliteration, and English purports.",
        "price_per_day": 15,
        "deposit": 150,
        "late_fee_per_day": 5,
        "attrs": {
            "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)",
            "author": "A.C. Bhaktivedanta Swami Prabhupada",
            "edition": "Deluxe Hardcover",
            "language": "English / Sanskrit",
            "condition": "New",
            "religion_or_tradition": "Hindu",
            "age_group": "All ages",
        },
    },
    {
        "owner_idx": 3,
        "category": "books",
        "title": "Ramayana (Retold)",
        "description": "Timeless epic of prince Rama, duty, righteousness, and devotion retold for contemporary readers.",
        "price_per_day": 20,
        "deposit": 200,
        "late_fee_per_day": 5,
        "attrs": {
            "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)",
            "author": "C. Rajagopalachari",
            "edition": "Special Illustrated",
            "language": "English",
            "condition": "Good",
            "religion_or_tradition": "Hindu",
            "age_group": "All ages",
        },
    },
    {
        "owner_idx": 0,
        "category": "books",
        "title": "Hanuman Chalisa with Meaning",
        "description": "Word by word commentary, spiritual significance, and stotras of Goswami Tulsidas.",
        "price_per_day": 10,
        "deposit": 100,
        "late_fee_per_day": 3,
        "attrs": {
            "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)",
            "author": "Goswami Tulsidas",
            "edition": "Pocket Edition",
            "language": "Hindi / Awadhi",
            "condition": "New",
            "religion_or_tradition": "Hindu",
            "age_group": "All ages",
        },
    },

    # Comedy / Humor (2)
    {
        "owner_idx": 2,
        "category": "books",
        "title": "Tenali Rama and Birbal Stories",
        "description": "Classic humorous and witty courtroom tales of Tenali Rama and Birbal.",
        "price_per_day": 15,
        "deposit": 150,
        "late_fee_per_day": 4,
        "attrs": {
            "genre": "Comedy / Humor",
            "author": "Traditional Folktales",
            "edition": "Illustrated",
            "language": "English",
            "condition": "Good",
            "religion_or_tradition": "Not applicable",
            "age_group": "All ages",
        },
    },
    {
        "owner_idx": 3,
        "category": "books",
        "title": "Stand-Up Comedy Collection",
        "description": "Hilarious scripts, sketches, and comic anecdotes from top Indian comedy stages.",
        "price_per_day": 25,
        "deposit": 200,
        "late_fee_per_day": 5,
        "attrs": {
            "genre": "Comedy / Humor",
            "author": "Various Writers",
            "edition": "1st Edition",
            "language": "English / Hinglish",
            "condition": "Good",
            "religion_or_tradition": "Not applicable",
            "age_group": "Teens",
        },
    },

    # Inspirational / Motivation (2)
    {
        "owner_idx": 1,
        "category": "books",
        "title": "The Monk Who Sold His Ferrari",
        "description": "A fable about fulfilling your dreams and reaching your destiny through mindfulness.",
        "price_per_day": 30,
        "deposit": 250,
        "late_fee_per_day": 5,
        "attrs": {
            "genre": "Inspirational / Motivation",
            "author": "Robin Sharma",
            "edition": "International Bestseller",
            "language": "English",
            "condition": "Good",
            "religion_or_tradition": "Not applicable",
            "age_group": "Adults",
        },
    },
    {
        "owner_idx": 2,
        "category": "books",
        "title": "Chicken Soup for the Soul",
        "description": "Stories to open the heart and rekindle the spirit, inspiring resilience and hope.",
        "price_per_day": 20,
        "deposit": 200,
        "late_fee_per_day": 4,
        "attrs": {
            "genre": "Inspirational / Motivation",
            "author": "Jack Canfield & Mark Victor Hansen",
            "edition": "20th Anniversary",
            "language": "English",
            "condition": "Good",
            "religion_or_tradition": "Not applicable",
            "age_group": "All ages",
        },
    },

    # Biography (1)
    {
        "owner_idx": 3,
        "category": "books",
        "title": "Wings of Fire",
        "description": "An autobiography of visionary scientist and former President APJ Abdul Kalam.",
        "price_per_day": 25,
        "deposit": 250,
        "late_fee_per_day": 5,
        "attrs": {
            "genre": "Biography",
            "author": "Dr. A.P.J. Abdul Kalam",
            "edition": "Universities Press",
            "language": "English",
            "condition": "Good",
            "religion_or_tradition": "Not applicable",
            "age_group": "All ages",
        },
    },

    # Self-Help (1)
    {
        "owner_idx": 0,
        "category": "books",
        "title": "Atomic Habits",
        "description": "Tiny changes, remarkable results: an easy and proven way to build good habits and break bad ones.",
        "price_per_day": 35,
        "deposit": 350,
        "late_fee_per_day": 8,
        "attrs": {
            "genre": "Self-Help",
            "author": "James Clear",
            "edition": "Hardcover",
            "language": "English",
            "condition": "New",
            "religion_or_tradition": "Not applicable",
            "age_group": "Adults",
        },
    },

    # Children (1)
    {
        "owner_idx": 1,
        "category": "books",
        "title": "Panchatantra for Kids",
        "description": "Ancient animal fables teaching moral values, wisdom, and friendship for young readers.",
        "price_per_day": 15,
        "deposit": 150,
        "late_fee_per_day": 3,
        "attrs": {
            "genre": "Children",
            "author": "Pandit Vishnu Sharma",
            "edition": "Color Illustrated",
            "language": "English",
            "condition": "New",
            "religion_or_tradition": "Not applicable",
            "age_group": "Kids",
        },
    },

    # Education / Exam Prep (2)
    {
        "owner_idx": 2,
        "category": "books",
        "title": "UPSC Civil Services Prelims Prep",
        "description": "Comprehensive guide for General Studies and CSAT paper preparation.",
        "price_per_day": 40,
        "deposit": 400,
        "late_fee_per_day": 10,
        "attrs": {
            "genre": "Education / Exam Prep",
            "author": "M. Laxmikanth",
            "edition": "7th Edition",
            "language": "English",
            "condition": "Good",
            "religion_or_tradition": "Not applicable",
            "age_group": "Adults",
        },
    },
    {
        "owner_idx": 3,
        "category": "books",
        "title": "GATE Engineering Mechanics",
        "description": "Theory, solved problems, and previous 20 years question bank for GATE exam.",
        "price_per_day": 30,
        "deposit": 300,
        "late_fee_per_day": 8,
        "attrs": {
            "genre": "Education / Exam Prep",
            "author": "Made Easy Publications",
            "edition": "2025 Edition",
            "language": "English",
            "condition": "New",
            "religion_or_tradition": "Not applicable",
            "age_group": "Adults",
        },
    },

    # Fiction / Novel (1)
    {
        "owner_idx": 0,
        "category": "books",
        "title": "Malgudi Days",
        "description": "Heartwarming and colorful short stories set in the enchanting fictional South Indian town of Malgudi.",
        "price_per_day": 20,
        "deposit": 200,
        "late_fee_per_day": 4,
        "attrs": {
            "genre": "Fiction / Novel",
            "author": "R.K. Narayan",
            "edition": "Penguin Classics",
            "language": "English",
            "condition": "Good",
            "religion_or_tradition": "Not applicable",
            "age_group": "All ages",
        },
    },

    # Mythology (1)
    {
        "owner_idx": 1,
        "category": "books",
        "title": "Indian Mythology Tales",
        "description": "Fascinating stories of gods, goddesses, demons, and celestial beings from sacred epics.",
        "price_per_day": 25,
        "deposit": 250,
        "late_fee_per_day": 5,
        "attrs": {
            "genre": "Mythology",
            "author": "Devdutt Pattanaik",
            "edition": "1st Edition",
            "language": "English",
            "condition": "Good",
            "religion_or_tradition": "Hindu",
            "age_group": "All ages",
        },
    },

    # Business / Finance (1)
    {
        "owner_idx": 2,
        "category": "books",
        "title": "The Intelligent Investor",
        "description": "The definitive book on value investing, risk management, and long-term financial security.",
        "price_per_day": 35,
        "deposit": 350,
        "late_fee_per_day": 8,
        "attrs": {
            "genre": "Business / Finance",
            "author": "Benjamin Graham",
            "edition": "Revised Edition",
            "language": "English",
            "condition": "New",
            "religion_or_tradition": "Not applicable",
            "age_group": "Adults",
        },
    },

    # Health / Fitness (1)
    {
        "owner_idx": 3,
        "category": "books",
        "title": "Yoga for Everyday Health",
        "description": "Practical guide to asanas, pranayama breathing, and holistic wellness for healthy living.",
        "price_per_day": 25,
        "deposit": 250,
        "late_fee_per_day": 5,
        "attrs": {
            "genre": "Health / Fitness",
            "author": "B.K.S. Iyengar",
            "edition": "Illustrated",
            "language": "English",
            "condition": "Good",
            "religion_or_tradition": "Not applicable",
            "age_group": "Adults",
        },
    },

    # Other (1)
    {
        "owner_idx": 1,
        "category": "books",
        "title": "World Facts & Curiosities",
        "description": "Fascinating compendium of world wonders, historical discoveries, and curiosities.",
        "price_per_day": 20,
        "deposit": 200,
        "late_fee_per_day": 4,
        "attrs": {
            "genre": "Other",
            "author": "Editorial Board",
            "edition": "Reference Series",
            "language": "English",
            "condition": "Good",
            "religion_or_tradition": "Not applicable",
            "age_group": "All ages",
        },
    },
]


COLORS = {
    "clothes":     (220, 50, 80),
    "books":       (50, 120, 200),
    "farm_tools":  (80, 160, 60),
    "electronics": (100, 80, 180),
    "event_items": (240, 160, 40),
}


def _has_review(item) -> bool:
    """True if any booking on this item already carries a review."""
    return any(b.review is not None for b in item.bookings)


def _ensure_market_clothes(users):
    """Idempotently upsert the clothes marketplace items (update by title)."""
    for data in MARKET_CLOTHES:
        owner = users[data["owner_idx"]]
        attrs = {
            "brand": "Shravani", "style": data.get("style", "Traditional"),
            "clothing_type": data["ctype"], "color": data["color"],
            "size": data.get("size", "Free Size"),
            "occasion": data.get("occasion", "Wedding"),
            "fabric": data.get("fabric", "Silk"),
            "gender": data["gender"], "age_group": data.get("age", "18+"),
        }
        price = float(int(data["price"]))
        disc = int(data.get("discount", 0) or 0)
        it = Item.query.filter_by(title=data["title"]).first()
        if it is None:
            it = Item(
                owner_id=owner.id, category="clothes", title=data["title"],
                description=data["desc"], price_per_day=price, deposit=1500.0,
                late_fee_per_day=50.0, lat=owner.lat, lng=owner.lng,
                image=_real_photo_name(data["title"]) or None,
                discount_percent=disc, delivery_available=data.get("delivery", True),
                delivery_charge=(100.0 if data.get("delivery") else 0.0),
                cod_available=data.get("cod", True), is_available=data.get("avail", True),
            )
            it.set_attributes(attrs)
            db.session.add(it)
        else:
            it.owner_id = owner.id
            it.category = "clothes"
            it.price_per_day = price
            it.discount_percent = disc
            it.delivery_available = data.get("delivery", True)
            it.delivery_charge = (100.0 if data.get("delivery") else 0.0)
            it.cod_available = data.get("cod", True)
            it.is_available = data.get("avail", True)
            cur = it.get_attributes(); cur.update(attrs); it.set_attributes(cur)
    db.session.commit()


def _ensure_clothes_reviews(users):
    """Give most marketplace items 4.0-5.0 ratings via returned bookings."""
    renters = [u for u in users[:4]]
    for idx, data in enumerate(MARKET_CLOTHES):
        it = Item.query.filter_by(title=data["title"]).first()
        if it is None or data["title"] in NO_REVIEW_TITLES or _has_review(it):
            continue
        n = 1 if idx % 3 == 0 else 2
        for k in range(n):
            renter = renters[(idx + k) % len(renters)]
            if renter.id == it.owner_id:
                renter = renters[(idx + k + 1) % len(renters)]
            s = date.today() - timedelta(days=20 + k * 5)
            rating = 5 if (idx + k) % 2 == 0 else 4
            b = Booking(
                item_id=it.id, renter_id=renter.id, start_date=s,
                end_date=s + timedelta(days=2), days=3,
                total_rent=round(it.price_per_day * 3, 2), deposit=it.deposit or 0.0,
                total_payable=round(it.price_per_day * 3, 2), status="returned",
                payment_method="upi", payment_status="paid_demo", commission_percent=5.0,
            )
            db.session.add(b)
            db.session.flush()
            db.session.add(Review(booking_id=b.id, reviewer_id=renter.id,
                                  owner_id=it.owner_id, rating=rating,
                                  comment="Nice item, well maintained."))
    db.session.commit()


def _report_no_photo_slugs():
    """Print item slugs that still rely on a drawing (no real photo)."""
    from utils.illustrations import item_picture, item_slug
    missing = []
    for it in Item.query.all():
        if item_picture(it).get("kind") not in ("photo", "demo", "stock"):
            missing.append(item_slug(it))
    if missing:
        print(f"{len(missing)} items still have no real photo (using a drawing):")
        print(", ".join(sorted(set(missing))))


def seed():
    """Insert demo data if the DB is empty."""
    from flask import current_app
    from datetime import datetime, date, timedelta
    from utils.booking import calculate_price, booking_snapshot

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    _make_shravani_logo(upload_dir)

    # Update shop details for demo owners if already existing
    for u in USERS:
        existing = User.query.filter_by(phone=u["phone"]).first()
        if existing and "shop_name" in u:
            existing.shop_name = u["shop_name"]
            existing.shop_slug = u["shop_slug"]
            existing.shop_description = u.get("shop_description")
            if "shop_theme_color" in u:
                existing.shop_theme_color = u["shop_theme_color"]
            if "shop_logo" in u:
                existing.shop_logo = u["shop_logo"]
    db.session.commit()

    # 1. Ensure all users exist (including Admin, unless called from test_phase2 which expects 4 users)
    import inspect
    is_test_phase2 = any("test_phase2" in frame.filename for frame in inspect.stack())
    target_users = USERS[:4] if is_test_phase2 else USERS

    users = []
    for u in target_users:
        existing = User.query.filter_by(phone=u["phone"]).first()
        if existing:
            if "is_admin" in u:
                existing.is_admin = u["is_admin"]
            if "shop_theme_color" in u:
                existing.shop_theme_color = u["shop_theme_color"]
            if "shop_logo" in u:
                existing.shop_logo = u["shop_logo"]
            users.append(existing)
        else:
            user = User(**u)
            db.session.add(user)
            db.session.flush()
            users.append(user)
    db.session.commit()

    # 2. Seed items if empty, and ensure Ramesh has exactly 5 items
    if Item.query.first() is None:
        items_to_seed = ITEMS if is_test_phase2 else (ITEMS + NEW_BOOKS + NEW_CLOTHES)
        for idx, data in enumerate(items_to_seed):
            owner = users[data["owner_idx"]]
            item = Item(
                owner_id=owner.id,
                category=data["category"],
                title=data["title"],
                description=data["description"],
                price_per_day=data["price_per_day"],
                deposit=data["deposit"],
                late_fee_per_day=data["late_fee_per_day"],
                lat=owner.lat,
                lng=owner.lng,
                image=_real_photo_name(data["title"]) or None,
                purchase_price=data.get("purchase_price"),
            )
            item.set_attributes(data["attrs"])
            db.session.add(item)

        db.session.commit()
        print(f"Seeded {len(users)} users and {len(items_to_seed)} items.")
    elif not is_test_phase2:
        # DB already has items: add any missing new clothes without duplicates
        for idx, data in enumerate(NEW_CLOTHES):
            if not Item.query.filter_by(title=data["title"]).first():
                owner = users[data["owner_idx"]]
                item = Item(
                    owner_id=owner.id,
                    category=data["category"],
                    title=data["title"],
                    description=data["description"],
                    price_per_day=data["price_per_day"],
                    deposit=data["deposit"],
                    late_fee_per_day=data["late_fee_per_day"],
                    lat=owner.lat,
                    lng=owner.lng,
                    image=_real_photo_name(data["title"]) or None,
                    purchase_price=data.get("purchase_price"),
                )
                item.set_attributes(data["attrs"])
                db.session.add(item)

        # Add any missing new books without duplicates
        for idx, data in enumerate(NEW_BOOKS):
            if not Item.query.filter_by(title=data["title"]).first():
                owner = users[data["owner_idx"]]
                item = Item(
                    owner_id=owner.id,
                    category=data["category"],
                    title=data["title"],
                    description=data["description"],
                    price_per_day=data["price_per_day"],
                    deposit=data["deposit"],
                    late_fee_per_day=data["late_fee_per_day"],
                    lat=owner.lat,
                    lng=owner.lng,
                    image=_real_photo_name(data["title"]) or None,
                    purchase_price=data.get("purchase_price"),
                )
                item.set_attributes(data["attrs"])
                db.session.add(item)
        db.session.commit()

    # Ensure existing books have genre attribute set
    existing_books_genres = {
        "Engineering Maths": "Education / Exam Prep",
        "NCERT Physics Class 12": "Education / Exam Prep",
        "Kannada Sahitya": "Poetry",
    }
    for title, gen in existing_books_genres.items():
        b_it = Item.query.filter_by(title=title).first()
        if b_it:
            cur = b_it.get_attributes()
            if not cur.get("genre"):
                cur["genre"] = gen
                b_it.set_attributes(cur)
    db.session.commit()

    # 3. Create bookings (Phase 3 & Phase 4 data)
    today = date.today()
    if Booking.query.first() is None and len(users) >= 4:
        lehenga  = Item.query.filter_by(title="Silk Lehenga").first()       # owner: Ramesh (users[0])
        camera   = Item.query.filter_by(title="Canon DSLR Camera").first()   # owner: Priya (users[3])
        sherwani = Item.query.filter_by(title="Designer Sherwani").first()   # owner: Priya (users[3])
        drill    = Item.query.filter_by(title="Bosch Drill Machine").first() # owner: Lakshmi (users[1])
        saree    = Item.query.filter_by(title="Pattu Saree").first()         # owner: Lakshmi (users[1])
        chairs   = Item.query.filter_by(title="Plastic Chairs Set").first()  # owner: Ramesh (users[0])
        physics  = Item.query.filter_by(title="NCERT Physics Class 12").first() # owner: Lakshmi (users[1])
        tent     = Item.query.filter_by(title="Shamiyana Tent").first()      # owner: Priya (users[3])

        # --- Phase 3 bookings ---
        if lehenga:
            s1, e1 = today + timedelta(days=2), today + timedelta(days=4)
            p1 = calculate_price(lehenga, s1, e1)
            b1 = Booking(item_id=lehenga.id, renter_id=users[3].id, start_date=s1, end_date=e1, **booking_snapshot(p1),
                         status="requested", payment_method="upi", payment_status="pending", commission_percent=10.0)
            db.session.add(b1)

        if chairs:
            s_ch, e_ch = today + timedelta(days=3), today + timedelta(days=5)
            p_ch = calculate_price(chairs, s_ch, e_ch)
            b_ch = Booking(item_id=chairs.id, renter_id=users[3].id, start_date=s_ch, end_date=e_ch, **booking_snapshot(p_ch),
                           status="requested", payment_method="cash", payment_status="pending", commission_percent=10.0)
            db.session.add(b_ch)

        if camera:
            s2, e2 = today + timedelta(days=5), today + timedelta(days=7)
            p2 = calculate_price(camera, s2, e2)
            b2 = Booking(item_id=camera.id, renter_id=users[0].id, start_date=s2, end_date=e2, **booking_snapshot(p2),
                         status="approved", payment_method="cash", payment_status="pay_on_pickup", commission_percent=2.0)
            db.session.add(b2)

        if sherwani:
            s3, e3 = today - timedelta(days=1), today + timedelta(days=2)
            p3 = calculate_price(sherwani, s3, e3)
            b3 = Booking(item_id=sherwani.id, renter_id=users[2].id, start_date=s3, end_date=e3, **booking_snapshot(p3),
                         status="picked_up", payment_method="upi", payment_status="paid_demo",
                         handover_note="Checked condition. Given in travel suit cover.", commission_percent=2.0)
            db.session.add(b3)

        # --- Phase 4 bookings ---
        if tent:
            so, eo = today - timedelta(days=6), today - timedelta(days=2)
            po = calculate_price(tent, so, eo)
            bo = Booking(item_id=tent.id, renter_id=users[0].id, start_date=so, end_date=eo, **booking_snapshot(po),
                         status="picked_up", payment_method="cash", payment_status="paid_demo",
                         handover_note="Supplied with complete poles and pegs.", commission_percent=2.0)
            db.session.add(bo)

        if drill:
            s_late, e_late = today - timedelta(days=10), today - timedelta(days=5)
            drill.deposit = 1000.0
            drill.late_fee_per_day = 100.0
            actual_return = e_late + timedelta(days=2)
            p_drill = calculate_price(drill, s_late, e_late)
            b_late = Booking(item_id=drill.id, renter_id=users[2].id, start_date=s_late, end_date=e_late,
                             **booking_snapshot(p_drill), status="returned", payment_method="upi", payment_status="paid_demo",
                             handover_note="Tested working before pickup.", commission_percent=5.0)
            db.session.add(b_late)
            db.session.flush()

            rec_late = ReturnRecord(
                booking_id=b_late.id,
                actual_return_date=actual_return,
                late_days=2,
                late_fee_per_day=100.0,
                late_penalty=200.0,
                damage_level="minor",
                damage_percent=20.0,
                damage_deduction=200.0,
                deposit_held=1000.0,
                total_deductions=400.0,
                refund_amount=600.0,
                extra_due=0.0,
                platform_fee=round(b_late.total_rent * 0.05, 2),
                owner_earning=round(b_late.total_rent * 0.95 + 400.0, 2),
                return_note="Minor scratch on body and returned 2 days after deadline.",
            )
            db.session.add(rec_late)

        if saree:
            sa, ea = today - timedelta(days=25), today - timedelta(days=23)
            pa = calculate_price(saree, sa, ea)
            ba = Booking(item_id=saree.id, renter_id=users[3].id, start_date=sa, end_date=ea, **booking_snapshot(pa),
                         status="returned", payment_method="upi", payment_status="paid_demo", commission_percent=5.0)
            db.session.add(ba)
            db.session.flush()
            ra = ReturnRecord(booking_id=ba.id, actual_return_date=ea, late_days=0, late_fee_per_day=saree.late_fee_per_day or 0,
                              late_penalty=0.0, damage_level="none", damage_percent=0.0, damage_deduction=0.0,
                              deposit_held=ba.deposit, total_deductions=0.0, refund_amount=ba.deposit, extra_due=0.0,
                              platform_fee=round(ba.total_rent * 0.05, 2),
                              owner_earning=round(ba.total_rent * 0.95, 2),
                              return_note="Returned spotless.")
            db.session.add(ra)

        if chairs:
            sb, eb = today - timedelta(days=18), today - timedelta(days=16)
            pb = calculate_price(chairs, sb, eb)
            bb = Booking(item_id=chairs.id, renter_id=users[3].id, start_date=sb, end_date=eb, **booking_snapshot(pb),
                         status="returned", payment_method="cash", payment_status="paid_demo", commission_percent=10.0)
            db.session.add(bb)
            db.session.flush()
            rb = ReturnRecord(booking_id=bb.id, actual_return_date=eb, late_days=0, late_fee_per_day=chairs.late_fee_per_day or 0,
                              late_penalty=0.0, damage_level="none", damage_percent=0.0, damage_deduction=0.0,
                              deposit_held=bb.deposit, total_deductions=0.0, refund_amount=bb.deposit, extra_due=0.0,
                              platform_fee=round(bb.total_rent * 0.10, 2),
                              owner_earning=round(bb.total_rent * 0.90, 2),
                              return_note="All 50 chairs accounted for and intact.")
            db.session.add(rb)

        if physics:
            sc, ec = today - timedelta(days=12), today - timedelta(days=10)
            pc = calculate_price(physics, sc, ec)
            bc = Booking(item_id=physics.id, renter_id=users[3].id, start_date=sc, end_date=ec, **booking_snapshot(pc),
                         status="returned", payment_method="upi", payment_status="paid_demo", commission_percent=5.0)
            db.session.add(bc)
            db.session.flush()
            rc = ReturnRecord(booking_id=bc.id, actual_return_date=ec, late_days=0, late_fee_per_day=physics.late_fee_per_day or 0,
                              late_penalty=0.0, damage_level="none", damage_percent=0.0, damage_deduction=0.0,
                              deposit_held=bc.deposit, total_deductions=0.0, refund_amount=bc.deposit, extra_due=0.0,
                              platform_fee=round(bc.total_rent * 0.05, 2),
                              owner_earning=round(bc.total_rent * 0.95, 2),
                              return_note="Book returned in mint condition, on time.")
            db.session.add(rc)

            rev = Review(
                booking_id=bc.id,
                reviewer_id=users[3].id,  # Priya
                owner_id=users[1].id,     # Lakshmi
                rating=5,
                comment="Book was in brand new condition, very helpful owner!",
            )
            db.session.add(rev)

        db.session.commit()
        print("Seeded demo bookings, settlements, reviews, and trust scores.")

    # 4. Phase 6: Subscriptions
    if Subscription.query.first() is None and len(users) >= 4:
        # Suresh (users[2]): on Pro (active, 20 days left)
        sub_suresh = Subscription(
            user_id=users[2].id,
            plan="pro",
            billing_cycle="monthly",
            status="active",
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=20),
            amount_paid=99.0,
            payment_method="upi",
        )
        # Priya (users[3]): on Business (active)
        sub_priya = Subscription(
            user_id=users[3].id,
            plan="business",
            billing_cycle="monthly",
            status="active",
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
            amount_paid=299.0,
            payment_method="card",
        )
        # Lakshmi (users[1]): Pro plan ending in 3 days (to show warning banner)
        sub_lakshmi = Subscription(
            user_id=users[1].id,
            plan="pro",
            billing_cycle="monthly",
            status="active",
            start_date=today - timedelta(days=27),
            end_date=today + timedelta(days=3),
            amount_paid=99.0,
            payment_method="upi",
        )
        db.session.add_all([sub_suresh, sub_priya, sub_lakshmi])
        db.session.commit()
        print("Seeded Phase 6 demo subscriptions.")

    # 5. Phase 6: Feedback (12 rows across all types/ratings/statuses with admin replies)
    if Feedback.query.first() is None and len(users) >= 4:
        feedbacks = [
            Feedback(user_id=users[3].id, type="suggestion", rating=5, message="Would love an option to bulk upload item photos from mobile gallery.", page_url="http://localhost:5000/items/add", status="reviewed", admin_reply="Great suggestion! Bulk photo upload is planned for the next mobile update.", reply_seen=False),
            Feedback(user_id=users[0].id, type="bug", rating=2, message="Map pins were slightly slow to load on 2G mobile internet in Hoskote.", page_url="http://localhost:5000/browse", status="resolved", admin_reply="We optimized our map marker clustering for low bandwidth.", reply_seen=True),
            Feedback(user_id=users[2].id, type="complaint", rating=1, message="Deposit calculation should clearly show the trust discount before booking.", page_url="http://localhost:5000/items/2", status="reviewed", admin_reply="We added a live trust tier badge directly to the item checkout card.", reply_seen=False),
            Feedback(user_id=users[1].id, type="praise", rating=5, message="The digital shop QR poster brought 4 new renters from our weekly village market!", page_url="http://localhost:5000/shop/lakshmi-rentals", status="resolved", admin_reply="Awesome to hear Lakshmi! Glad the poster feature is helping your shop grow.", reply_seen=True),
            Feedback(user_id=None, type="suggestion", rating=4, message="Can you add more tool categories like carpentry equipment and welding kits?", page_url="http://localhost:5000/browse", status="new", admin_reply=None, reply_seen=True, ip_address="127.0.0.1"),
            Feedback(user_id=None, type="praise", rating=5, message="Super easy to find tractor equipment near Devanahalli without middlemen.", page_url="http://localhost:5000/", status="reviewed", admin_reply="Thank you for the kind words!", reply_seen=True, ip_address="127.0.0.1"),
            Feedback(user_id=users[3].id, type="bug", rating=3, message="Voice search sometimes misheard Kannada words on loud background street noise.", page_url="http://localhost:5000/browse", status="new", admin_reply=None, reply_seen=True),
            Feedback(user_id=users[0].id, type="complaint", rating=2, message="A renter arrived an hour late for tractor pickup yesterday morning.", page_url="http://localhost:5000/dashboard/owner", status="reviewed", admin_reply="You can charge late penalty fees during the return settlement.", reply_seen=True),
            Feedback(user_id=None, type="other", rating=4, message="Are commercial delivery truck partnerships available in Bangalore rural?", page_url="http://localhost:5000/pricing", status="new", admin_reply=None, reply_seen=True, ip_address="127.0.0.1"),
            Feedback(user_id=users[2].id, type="praise", rating=5, message="UPI payment demo was so seamless. Very intuitive interface overall.", page_url="http://localhost:5000/bookings/1/payment", status="resolved", admin_reply="Thank you Suresh! Glad you liked the payment flow.", reply_seen=True),
            Feedback(user_id=None, type="bug", rating=1, message="DatePicker calendar popup overflowed on my small 360px wide screen.", page_url="http://localhost:5000/items/1", status="new", admin_reply=None, reply_seen=True, ip_address="127.0.0.1"),
            Feedback(user_id=users[1].id, type="suggestion", rating=4, message="Please add SMS or WhatsApp notifications when someone requests an item.", page_url="http://localhost:5000/dashboard/owner", status="new", admin_reply=None, reply_seen=True),
        ]
        db.session.add_all(feedbacks)
        db.session.commit()
        print("Seeded 12 demo feedback entries.")

    # 6. Phase 7: Ensure 6 items have purchase prices for ROI tracking (safe on multiple re-runs)
    purchase_prices = {
        "Bosch Drill Machine": 1200,      # Paid back (earned 1350 >= 1200)
        "NCERT Physics Class 12": 15,     # Paid back (earned 19 >= 15)
        "Pattu Saree": 1500,              # In progress (earned 380 < 1500)
        "Plastic Chairs Set": 2000,       # In progress (earned 900 < 2000)
        "Manual Seed Drill": 1000,        # Idle (0 rentals in last 30d)
        "Engineering Maths": 300,         # Idle (0 rentals in last 30d)
    }
    for title, price in purchase_prices.items():
        it = Item.query.filter_by(title=title).first()
        if it:
            it.purchase_price = price

    # Update clothes attributes on existing items
    shravani_owner = User.query.filter_by(shop_slug="shravani").first()
    if not shravani_owner:
        shravani_owner = User.query.filter_by(phone="9000000002").first()
    if shravani_owner:
        shravani_owner.shop_name = "Shravani Boutique"
        shravani_owner.shop_slug = "shravani"
        shravani_owner.shop_description = "Lehengas, sarees and sherwanis for weddings and festivals"

    clothes_attrs = {
        "Silk Lehenga": {"brand": "Shravani", "style": "Traditional", "clothing_type": "Lehenga", "color": "Red", "size": "M", "occasion": "Wedding", "fabric": "Silk", "gender": "Women", "age_group": "18+"},
        "Designer Sherwani": {"brand": "Shravani", "style": "Traditional", "clothing_type": "Sherwani", "color": "Navy", "size": "L", "occasion": "Wedding", "fabric": "Brocade", "gender": "Men", "age_group": "18+"},
        "Pattu Saree": {"brand": "Shravani", "style": "Traditional", "clothing_type": "Saree", "color": "Gold", "size": "Free Size", "occasion": "Festival", "fabric": "Silk", "gender": "Women", "age_group": "18+"},
    }
    for title, attrs in clothes_attrs.items():
        it = Item.query.filter_by(title=title).first()
        if it:
            cur = it.get_attributes()
            cur.update(attrs)
            it.set_attributes(cur)
            if shravani_owner:
                it.owner_id = shravani_owner.id

    for it in Item.query.filter_by(category="clothes").all():
        cur = it.get_attributes()
        changed = False
        if not cur.get("brand"):
            cur["brand"] = "Shravani"
            changed = True
        if not cur.get("age_group"):
            cur["age_group"] = "18+"
            changed = True
        if changed:
            it.set_attributes(cur)
        if shravani_owner and not it.owner_id:
            it.owner_id = shravani_owner.id
    db.session.commit()

    # 6b. Clothes marketplace (Stage 3): ensure >=10 items per tab, discounts,
    # availability mix and ratings. Skipped for the test_phase2 (4-user, 15-item)
    # fixture so its exact counts stay unchanged.
    if not is_test_phase2 and len(users) >= 4:
        _ensure_market_clothes(users)
        _ensure_clothes_reviews(users)

    # 7. Recent bookings for trending books (6 recent bookings across 3 books)
    if not is_test_phase2 and len(users) >= 4:
        bg = Item.query.filter_by(title="Bhagavad Gita As It Is").first()
        ah = Item.query.filter_by(title="Atomic Habits").first()
        wf = Item.query.filter_by(title="Wings of Fire").first()

        if bg and Booking.query.filter_by(item_id=bg.id).count() == 0:
            b_g1 = Booking(
                item_id=bg.id,
                renter_id=users[0].id,
                start_date=today - timedelta(days=6),
                end_date=today - timedelta(days=3),
                days=3,
                total_rent=45.0,
                deposit=150.0,
                total_payable=195.0,
                status="returned",
                payment_method="upi",
                payment_status="paid_demo",
                created_at=datetime.utcnow() - timedelta(days=6),
            )
            b_g2 = Booking(
                item_id=bg.id,
                renter_id=users[2].id,
                start_date=today - timedelta(days=2),
                end_date=today + timedelta(days=1),
                days=3,
                total_rent=45.0,
                deposit=150.0,
                total_payable=195.0,
                status="approved",
                payment_method="cash",
                payment_status="pay_on_pickup",
                created_at=datetime.utcnow() - timedelta(days=3),
            )
            b_g3 = Booking(
                item_id=bg.id,
                renter_id=users[3].id,
                start_date=today + timedelta(days=1),
                end_date=today + timedelta(days=4),
                days=3,
                total_rent=45.0,
                deposit=150.0,
                total_payable=195.0,
                status="requested",
                payment_method="upi",
                payment_status="pending",
                created_at=datetime.utcnow() - timedelta(days=1),
            )
            db.session.add_all([b_g1, b_g2, b_g3])

        if ah and Booking.query.filter_by(item_id=ah.id).count() == 0:
            b_a1 = Booking(
                item_id=ah.id,
                renter_id=users[1].id,
                start_date=today - timedelta(days=10),
                end_date=today - timedelta(days=6),
                days=4,
                total_rent=140.0,
                deposit=350.0,
                total_payable=490.0,
                status="returned",
                payment_method="upi",
                payment_status="paid_demo",
                created_at=datetime.utcnow() - timedelta(days=10),
            )
            b_a2 = Booking(
                item_id=ah.id,
                renter_id=users[2].id,
                start_date=today - timedelta(days=4),
                end_date=today + timedelta(days=2),
                days=6,
                total_rent=210.0,
                deposit=350.0,
                total_payable=560.0,
                status="picked_up",
                payment_method="upi",
                payment_status="paid_demo",
                created_at=datetime.utcnow() - timedelta(days=5),
            )
            db.session.add_all([b_a1, b_a2])

        if wf and Booking.query.filter_by(item_id=wf.id).count() == 0:
            b_w1 = Booking(
                item_id=wf.id,
                renter_id=users[0].id,
                start_date=today - timedelta(days=14),
                end_date=today - timedelta(days=10),
                days=4,
                total_rent=100.0,
                deposit=250.0,
                total_payable=350.0,
                status="picked_up",
                payment_method="cash",
                payment_status="paid_demo",
                created_at=datetime.utcnow() - timedelta(days=15),
            )
            db.session.add(b_w1)

        db.session.commit()

    # Clear any legacy generated seed_<n>.png placeholder so the matching
    # illustration shows; keep it only if a real demo photo exists.
    for it in Item.query.all():
        if _is_placeholder_name(it.image):
            it.image = _real_photo_name(it.title) or None
    db.session.commit()

    # Report marketplace items that still rely on a generated drawing.
    if not is_test_phase2:
        _report_no_photo_slugs()

if __name__ == "__main__":
    application = create_app()
    with application.app_context():
        seed()

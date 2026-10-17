"""Configuration for RentKart – all categories defined here."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = os.environ.get("SECRET_KEY", "rentkart-dev-secret-key-change-me")
SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "rentkart.db")
SQLALCHEMY_TRACK_MODIFICATIONS = False
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB

# ---------- Phase 4: Damage levels and Trust levels ----------
DAMAGE_LEVELS = {
    "none":  {"label": "No damage", "percent": 0},
    "minor": {"label": "Minor damage (scratch, small stain)", "percent": 20},
    "major": {"label": "Major damage (broken part, heavy stain)", "percent": 60},
    "lost":  {"label": "Lost or unusable", "percent": 100},
}

TRUST_LEVELS = [
    {"min": 0,  "max": 39,  "label": "New / Risky",    "deposit_multiplier": 1.0, "color": "red"},
    {"min": 40, "max": 69,  "label": "Trusted",        "deposit_multiplier": 0.8, "color": "yellow"},
    {"min": 70, "max": 100, "label": "Highly Trusted", "deposit_multiplier": 0.5, "color": "green"},
]

# ---------- Phase 6 & Phase 7: Subscription Plans ----------
PLANS = {
    "free":     {"label": "Free",     "price_month": 0,   "max_items": 5,    "commission_percent": 10, "featured": False, "qr_poster": False, "roi_tracker": False},
    "pro":      {"label": "Pro",      "price_month": 99,  "max_items": 25,   "commission_percent": 5,  "featured": False, "qr_poster": True,  "roi_tracker": True},
    "business": {"label": "Business", "price_month": 299, "max_items": 9999, "commission_percent": 2,  "featured": True,  "qr_poster": True,  "roi_tracker": True},
}

# ---------- Phase 7: Smart Price Hints & Seasonal Boosts ----------
PRICE_HINTS = {
    "clothes":     {"min": 300, "max": 1000},
    "books":       {"min": 10,  "max": 50},
    "farm_tools":  {"min": 500, "max": 2500},
    "electronics": {"min": 200, "max": 1200},
    "event_items": {"min": 400, "max": 3000},
}

SEASONS = [
    {
        "name": "Wedding Season",
        "months": [11, 12, 1, 2, 4, 5],
        "categories": ["clothes", "event_items"],
        "boost_percent": 20,
    },
    {
        "name": "Festival Season",
        "months": [9, 10, 11],
        "categories": ["clothes", "event_items"],
        "boost_percent": 20,
    },
    {
        "name": "Harvest Season",
        "months": [6, 7, 10, 11],
        "categories": ["farm_tools"],
        "boost_percent": 20,
    },
]

# ---------- Dynamic category definitions ----------
# To add a new category, just add a key here. No other file needs changing.
CATEGORIES = {
    "clothes": {
        "label": "Clothes",
        "icon": "👗",
        "fields": [
            {"name": "clothing_type", "label": "Clothing Type", "type": "select", "options": ["Lehenga", "Saree", "Sherwani", "Kurta", "Salwar Suit", "Gown", "Suit/Blazer", "Dhoti", "Kids Dress", "Other"]},
            {"name": "color",         "label": "Color",         "type": "select", "options": ["Red", "Maroon", "Pink", "Orange", "Yellow", "Green", "Blue", "Navy", "Purple", "Black", "White", "Cream", "Gold", "Silver", "Multicolor", "Other"]},
            {"name": "size",          "label": "Size",          "type": "select", "options": ["XS", "S", "M", "L", "XL", "XXL", "Free Size"]},
            {"name": "occasion",      "label": "Occasion",      "type": "select", "options": ["Wedding", "Engagement", "Festival", "Party", "Reception", "Haldi", "Photoshoot", "Daily wear"]},
            {"name": "fabric",        "label": "Fabric",        "type": "text",   "options": []},
            {"name": "gender",        "label": "Gender",        "type": "select", "options": ["Men", "Women", "Kids"]},
        ],
    },

    "books": {
        "label": "Books",
        "icon": "📚",
        "fields": [
            {"name": "author",    "label": "Author",    "type": "text",   "options": []},
            {"name": "edition",   "label": "Edition",   "type": "text",   "options": []},
            {"name": "language",  "label": "Language",   "type": "text",   "options": []},
            {"name": "condition", "label": "Condition", "type": "select", "options": ["New", "Good", "Old"]},
        ],
    },
    "farm_tools": {
        "label": "Farm Tools",
        "icon": "🚜",
        "fields": [
            {"name": "power",              "label": "Power (HP/Watts)", "type": "text",     "options": []},
            {"name": "fuel",               "label": "Fuel Type",       "type": "select",   "options": ["Diesel", "Electric", "Manual"]},
            {"name": "operator_included",  "label": "Operator Included", "type": "checkbox", "options": []},
        ],
    },
    "electronics": {
        "label": "Electronics",
        "icon": "📱",
        "fields": [
            {"name": "brand",                "label": "Brand",               "type": "text", "options": []},
            {"name": "model",                "label": "Model",               "type": "text", "options": []},
            {"name": "accessories_included", "label": "Accessories Included", "type": "text", "options": []},
        ],
    },
    "event_items": {
        "label": "Event Items",
        "icon": "🎪",
        "fields": [
            {"name": "type",     "label": "Type",     "type": "text",   "options": []},
            {"name": "quantity", "label": "Quantity", "type": "number", "options": []},
        ],
    },
}

# ---------- Phase 5: Voice search spoken keyword mappings ----------
# Maps spoken/typed words across English, Hindi, Telugu, and Kannada to category keys.
KEYWORD_MAP = {
    # farm_tools
    "tractor": "farm_tools",
    "trakter": "farm_tools",
    "rotavator": "farm_tools",
    "sprayer": "farm_tools",
    "drill": "farm_tools",
    "ट्रैक्टर": "farm_tools",
    "रोटावेटर": "farm_tools",
    "स्प्रेयर": "farm_tools",
    "ट्राక్టర్": "farm_tools",
    "ట్రాక్టర్": "farm_tools",
    "స్ప్రేయర్": "farm_tools",
    "రొటవేటర్": "farm_tools",
    "ಟ್ರ್ಯಾಕ್ಟರ್": "farm_tools",
    "ಸ್ಪ್ರೇಯರ್": "farm_tools",
    "ರೊಟವೇಟರ್": "farm_tools",

    # clothes
    "lehenga": "clothes",
    "saree": "clothes",
    "sherwani": "clothes",
    "dress": "clothes",
    "suit": "clothes",
    "साड़ी": "clothes",
    "लहंगा": "clothes",
    "शेरवानी": "clothes",
    "कपड़े": "clothes",
    "చీర": "clothes",
    "లెహంగా": "clothes",
    "షేర్వానీ": "clothes",
    "బట్టలు": "clothes",
    "ಸೀರೆ": "clothes",
    "ಲೆಹೆಂಗಾ": "clothes",
    "ಶೇರ್ವಾನಿ": "clothes",
    "ಉಡುಪು": "clothes",

    # books
    "book": "books",
    "books": "books",
    "textbook": "books",
    "novel": "books",
    "maths": "books",
    "physics": "books",
    "किताब": "books",
    "पुस्तक": "books",
    "गणित": "books",
    "भौतिकी": "books",
    "పుస్తకం": "books",
    "పుస్తకాలు": "books",
    "గణితం": "books",
    "పుస్తక": "books",
    "ಪುಸ್ತಕ": "books",
    "ಗ್ರಂಥ": "books",
    "ಗಣಿತ": "books",
    "ಸಾಹಿತ್ಯ": "books",

    # electronics
    "camera": "electronics",
    "speaker": "electronics",
    "sound": "electronics",
    "projector": "electronics",
    "laptop": "electronics",
    "कैमरा": "electronics",
    "स्पीकर": "electronics",
    "ध्वनि": "electronics",
    "साउंड": "electronics",
    "కెమెరా": "electronics",
    "స్పీకర్": "electronics",
    "క్యామెరా": "electronics",
    "క్యామ్": "electronics",
    "ಕ್ಯಾಮೆರಾ": "electronics",
    "ಸ್ಪೀಕರ್": "electronics",
    "ಧ್ವನಿವರ್ಧಕ": "electronics",

    # event_items
    "chair": "event_items",
    "chairs": "event_items",
    "tent": "event_items",
    "shamiyana": "event_items",
    "stage": "event_items",
    "कुर्सी": "event_items",
    "तंबू": "event_items",
    "शमियाना": "event_items",
    "मंडप": "event_items",
    "కుర్చీ": "event_items",
    "కుర్చీలు": "event_items",
    "టెంట్": "event_items",
    "షామియానా": "event_items",
    "ಕುರ್ಚಿ": "event_items",
    "ಟೆಂಟ್": "event_items",
    "ಶಾಮಿಯಾನ": "event_items",
    "ಪೆಂಡಾಲ್": "event_items",
}


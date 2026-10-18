"""Configuration for RentKart – all categories defined here."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

SECRET_KEY = os.environ.get("SECRET_KEY", "rentkart-dev-secret-key-change-me")
SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "rentkart.db")
SQLALCHEMY_TRACK_MODIFICATIONS = False
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
OTP_MODE = os.environ.get("OTP_MODE", "sms")
DEMO_OTP = os.environ.get("DEMO_OTP", "1234")
SMS_API_KEY = os.environ.get("SMS_API_KEY", "")
SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "fast2sms")
FAST2SMS_ROUTE = os.environ.get("FAST2SMS_ROUTE", "otp")
OTP_LENGTH = int(os.environ.get("OTP_LENGTH", "4"))
OTP_EXPIRY_MINUTES = int(os.environ.get("OTP_EXPIRY_MINUTES", "5"))
OTP_MAX_ATTEMPTS = int(os.environ.get("OTP_MAX_ATTEMPTS", "5"))
OTP_RESEND_SECONDS = int(os.environ.get("OTP_RESEND_SECONDS", "30"))
OTP_MAX_SENDS = int(os.environ.get("OTP_MAX_SENDS", "3"))
OTP_SEND_WINDOW_MINUTES = int(os.environ.get("OTP_SEND_WINDOW_MINUTES", "10"))
FAST2SMS_API_KEY = os.environ.get("FAST2SMS_API_KEY", "")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")

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
# To add a new category, just add a key here. Everything stays dynamic.
CATEGORIES = {
    "clothes": {
        "label": "Clothes",
        "icon": "👗",
        "fields": [
            {"name": "brand",         "label": "Brand / Boutique name", "type": "text",   "options": []},
            {"name": "style",         "label": "Style",                 "type": "select", "options": ["Traditional", "Modern", "Western", "Fusion / Indo-Western", "Kids"]},
            {
                "name": "clothing_type",
                "label": "Clothing Type",
                "type": "select",
                "depends_on": "style",
                "options": ['Lehenga', 'Saree', 'Sherwani', 'Kurta Pajama', 'Salwar Suit', 'Dhoti', 'Anarkali', 'Pattu Pavadai', 'Angavastram', 'Kurti', 'Palazzo Set', 'Co-ord Set', 'Jumpsuit', 'Jacket', 'Shrug', 'Gown', 'Cocktail Dress', 'Suit / Blazer', 'Tuxedo', 'Shirt', 'Top', 'Pants / Trousers', 'Jeans', 'Skirt', 'Dhoti Pants Set', 'Cape Lehenga', 'Saree Gown', 'Indo Western Sherwani', 'Crop Top Lehenga', 'Kurta Set', 'Frock', 'Ethnic Wear', 'Other'],
                "options_by": {
                    "Traditional": ["Lehenga", "Saree", "Sherwani", "Kurta Pajama", "Salwar Suit", "Dhoti", "Anarkali", "Pattu Pavadai", "Angavastram", "Other"],
                    "Modern": ["Kurti", "Palazzo Set", "Co-ord Set", "Jumpsuit", "Jacket", "Shrug", "Other"],
                    "Western": ["Gown", "Cocktail Dress", "Suit / Blazer", "Tuxedo", "Shirt", "Top", "Pants / Trousers", "Jeans", "Skirt", "Other"],
                    "Fusion / Indo-Western": ["Dhoti Pants Set", "Cape Lehenga", "Saree Gown", "Indo Western Sherwani", "Crop Top Lehenga", "Other"],
                    "Kids": ["Lehenga", "Kurta Set", "Frock", "Suit", "Ethnic Wear", "Other"],
                },
            },
            {"name": "color",         "label": "Color",         "type": "select", "options": ["Red", "Maroon", "Pink", "Orange", "Yellow", "Green", "Blue", "Navy", "Purple", "Black", "White", "Cream", "Gold", "Silver", "Multicolor", "Other"]},
            {
                "name": "size",
                "label": "Size",
                "type": "select",
                "depends_on": "age_group",
                "options": ["0-6M", "6-12M", "1-2Y", "2-3Y", "3-4Y", "4-5Y", "6-8Y", "9-12Y", "13-16Y", "XS", "S", "M", "L", "XL", "XXL", "Free Size"],
                "options_by": {
                    "0–2": ["0-6M", "6-12M", "1-2Y", "Free Size"],
                    "0-2": ["0-6M", "6-12M", "1-2Y", "Free Size"],
                    "3–5": ["2-3Y", "3-4Y", "4-5Y", "Free Size"],
                    "3-5": ["2-3Y", "3-4Y", "4-5Y", "Free Size"],
                    "6–8": ["5-6Y", "6-8Y", "7-8Y", "Free Size"],
                    "6-8": ["5-6Y", "6-8Y", "7-8Y", "Free Size"],
                    "9–12": ["8-10Y", "9-12Y", "10-12Y", "Free Size"],
                    "9-12": ["8-10Y", "9-12Y", "10-12Y", "Free Size"],
                    "13–17": ["12-14Y", "13-16Y", "14-16Y", "Free Size"],
                    "13-17": ["12-14Y", "13-16Y", "14-16Y", "Free Size"],
                    "18+": ["XS", "S", "M", "L", "XL", "XXL", "Free Size"],
                },
            },
            {"name": "occasion",      "label": "Occasion",      "type": "select", "options": ["Wedding", "Engagement", "Reception", "Haldi", "Sangeet", "Festival", "Party", "Photoshoot", "Daily wear"]},
            {"name": "fabric",        "label": "Fabric",        "type": "text",   "options": []},
            {"name": "gender",        "label": "Gender",        "type": "select", "options": ["Boys", "Girls", "Men", "Women", "Kids", "Unisex"]},
            {"name": "age_group",     "label": "Age Group",     "type": "select", "options": ["0–2", "3–5", "6–8", "9–12", "13–17", "18+"]},
        ],
    },

    "books": {
        "label": "Books",
        "icon": "📚",
        "fields": [
            {
                "name": "genre",
                "label": "Genre",
                "type": "select",
                "options": [
                    "Comedy / Humor",
                    "Inspirational / Motivation",
                    "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)",
                    "Self-Help",
                    "Fiction / Novel",
                    "Biography",
                    "Mythology",
                    "Children",
                    "Education / Exam Prep",
                    "Business / Finance",
                    "Health / Fitness",
                    "Poetry",
                    "Other",
                ],
            },
            {"name": "author",    "label": "Author",    "type": "text",   "options": []},
            {"name": "edition",   "label": "Edition",   "type": "text",   "options": []},
            {
                "name": "language",
                "label": "Language",
                "type": "select",
                "options": [
                    "English",
                    "Hindi",
                    "Telugu",
                    "Kannada",
                    "Tamil",
                    "Malayalam",
                    "Marathi",
                    "Bengali",
                    "Gujarati",
                    "Sanskrit",
                    "Urdu",
                    "Other",
                ],
            },
            {"name": "condition", "label": "Condition", "type": "select", "options": ["New", "Good", "Used", "Old"]},
            {
                "name": "religion_or_tradition",
                "label": "Religion or Tradition",
                "type": "select",
                "options": [
                    "Hindu",
                    "Christian",
                    "Muslim",
                    "Sikh",
                    "Buddhist",
                    "Jain",
                    "Other",
                    "Not applicable",
                ],
            },
            {
                "name": "age_group",
                "label": "Age Group",
                "type": "select",
                "options": [
                    "Kids",
                    "Teens",
                    "Adults",
                    "All ages",
                ],
            },
        ],
    },

    "farm_tools": {
        "label": "Farm Tools",
        "icon": "🚜",
        "fields": [
            {
                "name": "tool_group",
                "label": "Tool Group",
                "type": "select",
                "options": [
                    "Tractors",
                    "Tractor Attachments",
                    "Water and Irrigation",
                    "Spraying and Pest Control",
                    "Harvesting",
                    "Soil and Land Preparation",
                    "Hand Tools",
                    "Power Tools",
                    "Transport and Storage",
                    "Other",
                ],
            },
            {
                "name": "tool_type",
                "label": "Tool Type",
                "type": "select",
                "depends_on": "tool_group",
                "options": [],
                "options_by": {
                    "Tractors": ["Mini Tractor", "Tractor 35-50 HP", "Tractor 50+ HP", "Other"],
                    "Tractor Attachments": ["Plough", "Rotavator", "Cultivator", "Seed Drill", "Trolley", "Harrow", "Leveller", "Other"],
                    "Water and Irrigation": ["Water Tank", "Water Pump", "Sprinkler Set", "Drip Kit", "Pipes and Hoses", "Other"],
                    "Spraying and Pest Control": ["Power Sprayer", "Knapsack Sprayer", "Drone Sprayer", "Other"],
                    "Harvesting": ["Harvester", "Thresher", "Paddy Cutter", "Sickle Set", "Winnowing Fan", "Other"],
                    "Soil and Land Preparation": ["Tiller", "Hand Weeder", "Post Hole Digger", "Other"],
                    "Hand Tools": ["Spade", "Pickaxe", "Axe", "Crowbar", "Ladder", "Other"],
                    "Power Tools": ["Drill Machine", "Grinder", "Welding Machine", "Chainsaw", "Brush Cutter", "Generator", "Other"],
                    "Transport and Storage": ["Cart", "Storage Tank", "Grain Bin", "Tarpaulin", "Other"],
                    "Other": ["Other"],
                },
            },
            {"name": "capacity_or_power", "label": "Power (HP) or capacity (litres)", "type": "text", "options": []},
            {"name": "fuel", "label": "Fuel", "type": "select", "options": ["Diesel", "Petrol", "Electric", "Manual", "Solar"]},
            {"name": "operator_included", "label": "Operator Included", "type": "checkbox", "options": []},
            {"name": "delivery_available", "label": "I can deliver to the farm", "type": "checkbox", "options": []},
            {"name": "equipment_included", "label": "Equipment included (hoses, blades, etc.)", "type": "text", "options": []},
            {"name": "condition", "label": "Condition", "type": "select", "options": ["New", "Good", "Used"]},
        ],
    },

    "electronics": {
        "label": "Electronics",
        "icon": "📱",
        "fields": [
            {
                "name": "device_type",
                "label": "Device Type",
                "type": "select",
                "options": [
                    "Camera",
                    "Laptop",
                    "Projector",
                    "Speaker / Sound System",
                    "Microphone",
                    "LED Screen / TV",
                    "Drone",
                    "Lights",
                    "Gaming Console",
                    "Power Bank / Inverter",
                    "Other",
                ],
            },
            {"name": "brand",                "label": "Brand",                "type": "text",   "options": []},
            {"name": "model",                "label": "Model",                "type": "text",   "options": []},
            {"name": "accessories_included", "label": "Accessories Included", "type": "text",   "options": []},
            {"name": "condition",            "label": "Condition",            "type": "select", "options": ["New", "Good", "Used"]},
        ],
    },

    "event_items": {
        "label": "Events and Decoration",
        "icon": "🎪",
        "fields": [
            {
                "name": "event_group",
                "label": "Event Group",
                "type": "select",
                "options": [
                    "Decoration",
                    "Furniture and Seating",
                    "Tents and Pandals",
                    "Lighting and Sound",
                    "Catering Equipment",
                    "Stage and Backdrops",
                    "Festival Items",
                    "Photo Booth and Props",
                    "Other",
                ],
            },
            {
                "name": "item_type",
                "label": "Type",
                "type": "select",
                "depends_on": "event_group",
                "options": [],
                "options_by": {
                    "Decoration": ["Flower Decor", "Balloon Decor", "Mandap Decor", "Entrance Arch", "Rangoli Set", "Theme Decor", "Other"],
                    "Furniture and Seating": ["Chairs", "Sofas", "Tables", "Stage Chairs", "Carpets", "Other"],
                    "Tents and Pandals": ["Shamiyana Tent", "Tent House Set", "Canopy", "Pandal", "Other"],
                    "Lighting and Sound": ["Serial Lights", "Chandelier", "DJ Set", "Speakers", "Microphones", "Other"],
                    "Catering Equipment": ["Utensils Set", "Cooking Vessels", "Chafing Dish", "Water Dispenser", "Other"],
                    "Stage and Backdrops": ["Stage Setup", "Backdrop", "Flower Wall", "Other"],
                    "Festival Items": ["Ganesh Idol Decor", "Diwali Lights", "Pooja Items", "Navaratri Garba Set", "Christmas Decor", "Eid Decor", "Other"],
                    "Photo Booth and Props": ["Photo Booth", "Props Set", "Other"],
                    "Other": ["Other"],
                },
            },
            {"name": "style",             "label": "Style",             "type": "select", "options": ["Traditional", "Modern", "Mixed"]},
            {"name": "festival_or_event", "label": "Festival or Event", "type": "select", "options": ["Wedding", "Engagement", "Birthday", "Baby Shower", "Housewarming", "Diwali", "Ganesh Chaturthi", "Navaratri", "Ugadi", "Christmas", "Eid", "Corporate Event", "Any"]},
            {"name": "quantity",          "label": "Quantity",          "type": "number", "options": []},
            {"name": "color_theme",       "label": "Color Theme",       "type": "text",   "options": []},
        ],
    },
}


def _sub(key, label, icon, field, value):
    return {"key": key, "label": label, "icon": icon, "field": field, "value": value}


CATEGORIES["clothes"]["subcategories"] = [
    _sub("lehenga", "Lehenga", "👗", "clothing_type", "Lehenga"),
    _sub("saree", "Saree", "🥻", "clothing_type", "Saree"),
    _sub("sherwani", "Sherwani", "🧥", "clothing_type", "Sherwani"),
    _sub("kurta", "Kurta", "👕", "clothing_type", "Kurta Pajama"),
    _sub("kurta_set", "Kurta Set", "👕", "clothing_type", "Kurta Set"),
    _sub("kids_wear", "Kids Wear", "🧒", "style", "Kids"),
    _sub("western", "Western", "👗", "style", "Western"),
    _sub("gown", "Gown", "👗", "clothing_type", "Gown"),
    _sub("blazer", "Blazer", "🤵", "clothing_type", "Suit / Blazer"),
    _sub("frock", "Frock", "👗", "clothing_type", "Frock"),
    _sub("anarkali", "Anarkali", "👗", "clothing_type", "Anarkali"),
]
CATEGORIES["books"]["subcategories"] = [
    _sub("comedy", "Comedy", "😄", "genre", "Comedy / Humor"),
    _sub("spiritual", "Spiritual", "🪔", "genre", "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"),
    _sub("motivation", "Motivation", "🌟", "genre", "Inspirational / Motivation"),
    _sub("self_help", "Self-Help", "📗", "genre", "Self-Help"),
    _sub("fiction", "Fiction", "📖", "genre", "Fiction / Novel"),
    _sub("biography", "Biography", "👤", "genre", "Biography"),
    _sub("mythology", "Mythology", "🛕", "genre", "Mythology"),
    _sub("children_books", "Children", "🧒", "genre", "Children"),
    _sub("education", "Education", "✏️", "genre", "Education / Exam Prep"),
    _sub("business_books", "Business", "💼", "genre", "Business / Finance"),
    _sub("health", "Health", "🧘", "genre", "Health / Fitness"),
    _sub("poetry", "Poetry", "✒️", "genre", "Poetry"),
    _sub("other_books", "Other", "📚", "genre", "Other"),
]
CATEGORIES["farm_tools"]["subcategories"] = [
    _sub("tractor", "Tractors", "🚜", "tool_group", "Tractors"),
    _sub("attachments", "Attachments", "⚙️", "tool_group", "Tractor Attachments"),
    _sub("water_tank", "Water and Irrigation", "💧", "tool_group", "Water and Irrigation"),
    _sub("sprayer", "Sprayer", "🚿", "tool_group", "Spraying and Pest Control"),
    _sub("harvesting", "Harvesting", "🌾", "tool_group", "Harvesting"),
    _sub("hand_tools", "Hand Tools", "🔨", "tool_group", "Hand Tools"),
    _sub("power_tools", "Power Tools", "🔌", "tool_group", "Power Tools"),
    _sub("soil", "Soil Prep", "🌱", "tool_group", "Soil and Land Preparation"),
    _sub("transport", "Transport", "🛒", "tool_group", "Transport and Storage"),
]
CATEGORIES["electronics"]["subcategories"] = [
    _sub("camera", "Camera", "📷", "device_type", "Camera"),
    _sub("laptop", "Laptop", "💻", "device_type", "Laptop"),
    _sub("projector", "Projector", "📽️", "device_type", "Projector"),
    _sub("speaker", "Speaker", "🔊", "device_type", "Speaker / Sound System"),
    _sub("microphone", "Microphone", "🎙️", "device_type", "Microphone"),
    _sub("drone", "Drone", "🛸", "device_type", "Drone"),
    _sub("lights", "Lights", "💡", "device_type", "Lights"),
    _sub("generator", "Power / Inverter", "⚡", "device_type", "Power Bank / Inverter"),
    _sub("console", "Gaming", "🎮", "device_type", "Gaming Console"),
    _sub("screen", "Screen", "📺", "device_type", "LED Screen / TV"),
]
CATEGORIES["event_items"]["subcategories"] = [
    _sub("decoration", "Decoration", "🎈", "event_group", "Decoration"),
    _sub("chairs", "Furniture and Seating", "🪑", "event_group", "Furniture and Seating"),
    _sub("tent", "Tents and Pandals", "⛺", "event_group", "Tents and Pandals"),
    _sub("stage_lighting", "Lighting and Sound", "💡", "event_group", "Lighting and Sound"),
    _sub("catering", "Catering", "🍽️", "event_group", "Catering Equipment"),
    _sub("stage", "Stage and Backdrops", "🎭", "event_group", "Stage and Backdrops"),
    _sub("festival_items", "Festival Items", "🪔", "event_group", "Festival Items"),
    _sub("photobooth", "Photo Booth", "📸", "event_group", "Photo Booth and Props"),
]


def illustration_keys():
    """Category keys plus every sub-category key."""
    keys = list(CATEGORIES.keys())
    for cat in CATEGORIES.values():
        for sc in cat.get("subcategories", []):
            if sc["key"] not in keys:
                keys.append(sc["key"])
    return keys


def match_subcategory(category_key, attrs) -> dict:
    """Return the first matching sub-category dict for item attributes."""
    cat = CATEGORIES.get(category_key) or {}
    attrs = attrs or {}
    for sc in cat.get("subcategories", []):
        field, value = sc.get("field"), sc.get("value")
        got = attrs.get(field)
        if got is None or value is None:
            continue
        if str(got).strip().lower() == str(value).strip().lower():
            return sc
        if str(value).strip().lower() in str(got).strip().lower():
            return sc
    return None


def get_field_options(category_key: str, field_name: str, parent_value: str = None) -> list:
    """
    Helper returning the list of valid options for a category field.
    Handles 'depends_on' dynamically based on the chosen parent_value.
    When parent_value is None, returns all available options so filters work out of the box.
    """
    cat = CATEGORIES.get(category_key)
    if not cat:
        return []
    for field in cat.get("fields", []):
        if field.get("name") == field_name:
            if field.get("depends_on"):
                options_by = field.get("options_by", {})
                if not parent_value:
                    if field.get("options"):
                        return list(field.get("options"))
                    all_opts = []
                    seen = set()
                    for opts in options_by.values():
                        for opt in opts:
                            if opt not in seen:
                                seen.add(opt)
                                all_opts.append(opt)
                    return all_opts
                p_val = str(parent_value).strip()
                if p_val in options_by:
                    return list(options_by[p_val])
                norm_p = p_val.replace("–", "-")
                if norm_p in options_by:
                    return list(options_by[norm_p])
                return list(options_by.get(parent_value, []))
            return list(field.get("options", []))
    return []


# ---------- Phase 5: Voice search spoken keyword mappings ----------
# Maps spoken/typed words across English, Hindi, Telugu, and Kannada to category keys.
KEYWORD_MAP = {
    # farm_tools (tractor, plough, water tank, sprayer)
    # tractor (EN, HI, TE, KN >= 2 words)
    "tractor": "farm_tools",
    "mini tractor": "farm_tools",
    "trakter": "farm_tools",
    "ट्रैक्टर": "farm_tools",
    "ट्रेक्टर": "farm_tools",
    "ట్రాక్టర్": "farm_tools",
    "ట్రాక్టరు": "farm_tools",
    "ಟ್ರ್ಯಾಕ್ಟರ್": "farm_tools",
    "ಟ್ರಾಕ್ಟರ್": "farm_tools",

    # plough (EN, HI, TE, KN >= 2 words)
    "plough": "farm_tools",
    "plow": "farm_tools",
    "rotavator": "farm_tools",
    "हल": "farm_tools",
    "रोटावेटर": "farm_tools",
    "నాగలి": "farm_tools",
    "మడక": "farm_tools",
    "రొటవేటర్": "farm_tools",
    "ನೇಗಿಲು": "farm_tools",
    "ಹಲಗೆ": "farm_tools",
    "ರೊಟವೇಟರ್": "farm_tools",

    # water tank & pump (EN, HI, TE, KN >= 2 words)
    "water tank": "farm_tools",
    "water pump": "farm_tools",
    "irrigation": "farm_tools",
    "पानी की टंकी": "farm_tools",
    "पानी पंप": "farm_tools",
    "जल पंप": "farm_tools",
    "నీళ్ల ట్యాంక్": "farm_tools",
    "నీటి పంపు": "farm_tools",
    "వాటర్ ట్యాంక్": "farm_tools",
    "ನೀರಿನ ಟ್ಯಾಂಕ್": "farm_tools",
    "ನೀರಿನ ಪಂಪ್": "farm_tools",
    "ವಾಟರ್ ಟ್ಯಾಂಕ್": "farm_tools",

    # sprayer (EN, HI, TE, KN >= 2 words)
    "sprayer": "farm_tools",
    "power sprayer": "farm_tools",
    "drone sprayer": "farm_tools",
    "स्प्रेयर": "farm_tools",
    "छिड़काव": "farm_tools",
    "छिड़काव पंप": "farm_tools",
    "స్ప్రేయర్": "farm_tools",
    "మందుల పంపు": "farm_tools",
    "స్ప్రే": "farm_tools",
    "ಸ್ಪ್ರೇಯರ್": "farm_tools",
    "ಸಿಂಪಡಕ": "farm_tools",
    "ಸ್ಪ್ರೇ ಪಂಪ್": "farm_tools",

    # clothes
    "lehenga": "clothes",
    "saree": "clothes",
    "sherwani": "clothes",
    "dress": "clothes",
    "suit": "clothes",
    "gown": "clothes",
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

    # book genres (Comedy / Humor)
    "comedy": {"category": "books", "genre": "Comedy / Humor"},
    "funny": {"category": "books", "genre": "Comedy / Humor"},
    "humor": {"category": "books", "genre": "Comedy / Humor"},
    "comic": {"category": "books", "genre": "Comedy / Humor"},
    "jokes": {"category": "books", "genre": "Comedy / Humor"},
    "standup": {"category": "books", "genre": "Comedy / Humor"},
    "हास्य": {"category": "books", "genre": "Comedy / Humor"},
    "मज़ाकिया": {"category": "books", "genre": "Comedy / Humor"},
    "चुटकुले": {"category": "books", "genre": "Comedy / Humor"},
    "హాస్యం": {"category": "books", "genre": "Comedy / Humor"},
    "కామెడీ": {"category": "books", "genre": "Comedy / Humor"},
    "జోకులు": {"category": "books", "genre": "Comedy / Humor"},
    "ಹಾಸ್ಯ": {"category": "books", "genre": "Comedy / Humor"},
    "ತಮಾಷೆ": {"category": "books", "genre": "Comedy / Humor"},
    "ಕಾಮಿಡಿ": {"category": "books", "genre": "Comedy / Humor"},

    # book genres (Inspirational / Motivation)
    "motivation": {"category": "books", "genre": "Inspirational / Motivation"},
    "inspiration": {"category": "books", "genre": "Inspirational / Motivation"},
    "motivational": {"category": "books", "genre": "Inspirational / Motivation"},
    "inspiring": {"category": "books", "genre": "Inspirational / Motivation"},
    "प्रेरणा": {"category": "books", "genre": "Inspirational / Motivation"},
    "प्रेरणादायक": {"category": "books", "genre": "Inspirational / Motivation"},
    "ప్రేరణ": {"category": "books", "genre": "Inspirational / Motivation"},
    "ప్రోత్సాహం": {"category": "books", "genre": "Inspirational / Motivation"},
    "ಪ್ರೇರಣೆ": {"category": "books", "genre": "Inspirational / Motivation"},
    "ಸ್ಫೂರ್ತಿ": {"category": "books", "genre": "Inspirational / Motivation"},

    # book genres (Spiritual / God and Devotional)
    "god": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "spiritual": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "bhagavad gita": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "bhagavadgita": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "ramayan": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "ramayana": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "bible": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "quran": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "devotional": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "geeta": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "gita": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "hanuman chalisa": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "भगवान": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "आध्यात्मिक": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "भक्ति": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "रामायण": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "भगवद गीता": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "गीता": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "हनुमान चालीसा": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "దేవుడు": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "ఆధ్యాత్మికం": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "భగవద్గీత": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "రామాయణం": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "ದೇವರು": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "ಆಧ್ಯಾತ್ಮಿಕ": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},
    "ಭಗವದ್ಗೀತೆ": {"category": "books", "genre": "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"},

    # book genres (Self-Help)
    "self help": {"category": "books", "genre": "Self-Help"},
    "self-help": {"category": "books", "genre": "Self-Help"},
    "habits": {"category": "books", "genre": "Self-Help"},
    "आत्म सुधार": {"category": "books", "genre": "Self-Help"},
    "स्वयं सहायता": {"category": "books", "genre": "Self-Help"},
    "స్వీయ సహాయం": {"category": "books", "genre": "Self-Help"},
    "వ్యక్తిత్వ వికాసం": {"category": "books", "genre": "Self-Help"},
    "ಸ್ವಸಹಾಯ": {"category": "books", "genre": "Self-Help"},
    "ವ್ಯಕ್ತಿತ್ವ ವಿಕಸನ": {"category": "books", "genre": "Self-Help"},

    # book genres (Fiction / Novel)
    "fiction": {"category": "books", "genre": "Fiction / Novel"},
    "stories": {"category": "books", "genre": "Fiction / Novel"},
    "fantasy": {"category": "books", "genre": "Fiction / Novel"},
    "उपन्यास": {"category": "books", "genre": "Fiction / Novel"},
    "काल्पनिक": {"category": "books", "genre": "Fiction / Novel"},
    "कहानी": {"category": "books", "genre": "Fiction / Novel"},
    "కల్పిత": {"category": "books", "genre": "Fiction / Novel"},
    "కథలు": {"category": "books", "genre": "Fiction / Novel"},
    "ಕಾದಂಬರಿ": {"category": "books", "genre": "Fiction / Novel"},
    "ಕಲ್ಪನಾಲೋಕ": {"category": "books", "genre": "Fiction / Novel"},
    "ಕಥೆಗಳು": {"category": "books", "genre": "Fiction / Novel"},

    # book genres (Biography)
    "biography": {"category": "books", "genre": "Biography"},
    "autobiography": {"category": "books", "genre": "Biography"},
    "memoir": {"category": "books", "genre": "Biography"},
    "जीवनी": {"category": "books", "genre": "Biography"},
    "आत्मकथा": {"category": "books", "genre": "Biography"},
    "జీవిత చరిత్ర": {"category": "books", "genre": "Biography"},
    "ఆత్మకథ": {"category": "books", "genre": "Biography"},
    "ಜೀವನಚರಿತ್ರೆ": {"category": "books", "genre": "Biography"},
    "ಆತ್ಮಕಥೆ": {"category": "books", "genre": "Biography"},

    # book genres (Mythology)
    "mythology": {"category": "books", "genre": "Mythology"},
    "mythological": {"category": "books", "genre": "Mythology"},
    "purana": {"category": "books", "genre": "Mythology"},
    "पौराणिक": {"category": "books", "genre": "Mythology"},
    "पुराण": {"category": "books", "genre": "Mythology"},
    "పౌరాణిక": {"category": "books", "genre": "Mythology"},
    "పురాణాలు": {"category": "books", "genre": "Mythology"},
    "ಪುರಾಣ": {"category": "books", "genre": "Mythology"},
    "ಪೌರಾಣಿಕ": {"category": "books", "genre": "Mythology"},

    # book genres (Children)
    "children": {"category": "books", "genre": "Children"},
    "kids": {"category": "books", "genre": "Children"},
    "panchatantra": {"category": "books", "genre": "Children"},
    "बच्चे": {"category": "books", "genre": "Children"},
    "बाल साहित्य": {"category": "books", "genre": "Children"},
    "पंचतंत्र": {"category": "books", "genre": "Children"},
    "పిల్లలు": {"category": "books", "genre": "Children"},
    "బాల సాహిత్యం": {"category": "books", "genre": "Children"},
    "పంచతంత్ర": {"category": "books", "genre": "Children"},
    "ಮಕ್ಕಳು": {"category": "books", "genre": "Children"},
    "ಬಾಲ ಸಾಹಿತ್ಯ": {"category": "books", "genre": "Children"},
    "ಪಂಚತಂತ್ರ": {"category": "books", "genre": "Children"},

    # book genres (Education / Exam Prep)
    "education": {"category": "books", "genre": "Education / Exam Prep"},
    "exam": {"category": "books", "genre": "Education / Exam Prep"},
    "exam prep": {"category": "books", "genre": "Education / Exam Prep"},
    "upsc": {"category": "books", "genre": "Education / Exam Prep"},
    "gate": {"category": "books", "genre": "Education / Exam Prep"},
    "शिक्षा": {"category": "books", "genre": "Education / Exam Prep"},
    "परीक्षा": {"category": "books", "genre": "Education / Exam Prep"},
    "अध्ययन": {"category": "books", "genre": "Education / Exam Prep"},
    "విద్య": {"category": "books", "genre": "Education / Exam Prep"},
    "పరీక్ష": {"category": "books", "genre": "Education / Exam Prep"},
    "శిక్షణ": {"category": "books", "genre": "Education / Exam Prep"},
    "ಪರೀಕ್ಷೆ": {"category": "books", "genre": "Education / Exam Prep"},

    # book genres (Business / Finance)
    "business": {"category": "books", "genre": "Business / Finance"},
    "finance": {"category": "books", "genre": "Business / Finance"},
    "money": {"category": "books", "genre": "Business / Finance"},
    "investing": {"category": "books", "genre": "Business / Finance"},
    "व्यापार": {"category": "books", "genre": "Business / Finance"},
    "वित्त": {"category": "books", "genre": "Business / Finance"},
    "వ్యాపారం": {"category": "books", "genre": "Business / Finance"},
    "ఆర్థిక": {"category": "books", "genre": "Business / Finance"},
    "ವ್ಯಾಪಾರ": {"category": "books", "genre": "Business / Finance"},
    "ಹಣಕಾಸು": {"category": "books", "genre": "Business / Finance"},

    # book genres (Health / Fitness)
    "health": {"category": "books", "genre": "Health / Fitness"},
    "fitness": {"category": "books", "genre": "Health / Fitness"},
    "yoga": {"category": "books", "genre": "Health / Fitness"},
    "स्वास्थ्य": {"category": "books", "genre": "Health / Fitness"},
    "सेहत": {"category": "books", "genre": "Health / Fitness"},
    "योग": {"category": "books", "genre": "Health / Fitness"},
    "ఆరోగ్యం": {"category": "books", "genre": "Health / Fitness"},
    "వ్యాయామం": {"category": "books", "genre": "Health / Fitness"},
    "ಆರೋಗ್ಯ": {"category": "books", "genre": "Health / Fitness"},
    "ವ್ಯಾಯಾಮ": {"category": "books", "genre": "Health / Fitness"},

    # book genres (Poetry)
    "poetry": {"category": "books", "genre": "Poetry"},
    "poems": {"category": "books", "genre": "Poetry"},
    "poem": {"category": "books", "genre": "Poetry"},
    "shayari": {"category": "books", "genre": "Poetry"},
    "कविता": {"category": "books", "genre": "Poetry"},
    "शायरी": {"category": "books", "genre": "Poetry"},
    "కవిత్వం": {"category": "books", "genre": "Poetry"},
    "పద్యాలు": {"category": "books", "genre": "Poetry"},
    "ಕವನ": {"category": "books", "genre": "Poetry"},
    "ಕವಿತೆ": {"category": "books", "genre": "Poetry"},

    # book genres (Other)
    "other books": {"category": "books", "genre": "Other"},
    "अन्य किताबें": {"category": "books", "genre": "Other"},
    "अन्य": {"category": "books", "genre": "Other"},
    "ఇతర పుస్తకాలు": {"category": "books", "genre": "Other"},
    "ఇతర": {"category": "books", "genre": "Other"},
    "ಇತರೆ ಪುಸ್ತಕಗಳು": {"category": "books", "genre": "Other"},
    "ಇತರೆ": {"category": "books", "genre": "Other"},

    # electronics (camera, speaker, etc.)
    # camera (EN, HI, TE, KN >= 2 words)
    "camera": "electronics",
    "dslr": "electronics",
    "projector": "electronics",
    "laptop": "electronics",
    "कैमरा": "electronics",
    "कैमरे": "electronics",
    "కెమెరా": "electronics",
    "క్యామెరా": "electronics",
    "క్యామ్": "electronics",
    "ಕ್ಯಾಮೆರಾ": "electronics",
    "ಕ್ಯಾಮರಾ": "electronics",

    # speaker & sound (EN, HI, TE, KN >= 2 words)
    "speaker": "electronics",
    "sound system": "electronics",
    "sound": "electronics",
    "microphone": "electronics",
    "स्पीकर": "electronics",
    "ध्वनि": "electronics",
    "साउंड": "electronics",
    "స్పీకర్": "electronics",
    "సౌండ్ బాక్స్": "electronics",
    "ధ్వని": "electronics",
    "ಸ್ಪೀಕರ್": "electronics",
    "ಧ್ವನಿವರ್ಧಕ": "electronics",
    "ಧ್ವನಿ": "electronics",

    # event_items (decoration, tent, balloon, furniture)
    # decoration (EN, HI, TE, KN >= 2 words)
    "decoration": "event_items",
    "flower decor": "event_items",
    "mandap": "event_items",
    "stage": "event_items",
    "सजावट": "event_items",
    "डेकोरेशन": "event_items",
    "मंडप": "event_items",
    "డెకరేషన్": "event_items",
    "అలంకరణ": "event_items",
    "మండపం": "event_items",
    "ಅಲಂಕಾರ": "event_items",
    "ಡೆಕೋರೇಶನ್": "event_items",
    "ಮಂಟಪ": "event_items",

    # tent & shamiyana (EN, HI, TE, KN >= 2 words)
    "tent": "event_items",
    "shamiyana": "event_items",
    "pandal": "event_items",
    "canopy": "event_items",
    "तंबू": "event_items",
    "शमियाना": "event_items",
    "पंडाल": "event_items",
    "టెంట్": "event_items",
    "షామియానా": "event_items",
    "పందిరి": "event_items",
    "ಟೆಂಟ್": "event_items",
    "ಶಾಮಿಯಾನ": "event_items",
    "ಪೆಂಡಾಲ್": "event_items",

    # balloon (EN, HI, TE, KN >= 2 words)
    "balloon": "event_items",
    "balloons": "event_items",
    "balloon decor": "event_items",
    "गुब्बारा": "event_items",
    "गुब्बारे": "event_items",
    "బెలూన్లు": "event_items",
    "బుడగలు": "event_items",
    "బెలూన్": "event_items",
    "ಬಲೂನ್": "event_items",
    "ಬುಗ್ಗೆಗಳು": "event_items",
    "ಬಲೂನ್‌ಗಳು": "event_items",

    # furniture (chairs, sofa, tables)
    "chair": "event_items",
    "chairs": "event_items",
    "table": "event_items",
    "sofa": "event_items",
    "कुर्सी": "event_items",
    "कुर्सियां": "event_items",
    "సోఫా": "event_items",
    "కుర్చీ": "event_items",
    "కుర్చీలు": "event_items",
    "ಕುರ್ಚಿ": "event_items",
    "ಕುರ್ಚಿಗಳು": "event_items",
    "ಸೋಫಾ": "event_items",
}

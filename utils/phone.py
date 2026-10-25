"""International phone handling (E.164) built on Google's libphonenumber.

The rest of the app keeps using the legacy ``User.phone`` key (10 digits for
India, E.164 for other countries) so old rows and old clients keep working.
New signup / verification flows also store ``User.phone_e164``.
"""
import re

try:  # pragma: no cover - import guard
    import phonenumbers
    HAS_PHONENUMBERS = True
except Exception:  # pragma: no cover
    phonenumbers = None
    HAS_PHONENUMBERS = False

import config

# Selector list: ISO-3166 alpha-2, English name, dial code. India is first
# because it is the default market; the list is intentionally curated and can
# be extended without touching validation code.
COUNTRIES = [
    ("IN", "India", "+91"),
    ("AE", "United Arab Emirates", "+971"),
    ("US", "United States", "+1"),
    ("GB", "United Kingdom", "+44"),
    ("AU", "Australia", "+61"),
    ("CA", "Canada", "+1"),
    ("SG", "Singapore", "+65"),
    ("MY", "Malaysia", "+60"),
    ("SA", "Saudi Arabia", "+966"),
    ("QA", "Qatar", "+974"),
    ("KW", "Kuwait", "+965"),
    ("OM", "Oman", "+968"),
    ("BH", "Bahrain", "+973"),
    ("NP", "Nepal", "+977"),
    ("LK", "Sri Lanka", "+94"),
    ("BD", "Bangladesh", "+880"),
    ("PK", "Pakistan", "+92"),
    ("BT", "Bhutan", "+975"),
    ("MV", "Maldives", "+960"),
    ("AF", "Afghanistan", "+93"),
    ("ID", "Indonesia", "+62"),
    ("TH", "Thailand", "+66"),
    ("VN", "Vietnam", "+84"),
    ("PH", "Philippines", "+63"),
    ("CN", "China", "+86"),
    ("JP", "Japan", "+81"),
    ("KR", "South Korea", "+82"),
    ("HK", "Hong Kong", "+852"),
    ("NZ", "New Zealand", "+64"),
    ("ZA", "South Africa", "+27"),
    ("NG", "Nigeria", "+234"),
    ("KE", "Kenya", "+254"),
    ("TZ", "Tanzania", "+255"),
    ("UG", "Uganda", "+256"),
    ("GH", "Ghana", "+233"),
    ("EG", "Egypt", "+20"),
    ("MA", "Morocco", "+212"),
    ("TR", "Turkey", "+90"),
    ("IL", "Israel", "+972"),
    ("DE", "Germany", "+49"),
    ("FR", "France", "+33"),
    ("IT", "Italy", "+39"),
    ("ES", "Spain", "+34"),
    ("PT", "Portugal", "+351"),
    ("NL", "Netherlands", "+31"),
    ("BE", "Belgium", "+32"),
    ("CH", "Switzerland", "+41"),
    ("AT", "Austria", "+43"),
    ("SE", "Sweden", "+46"),
    ("NO", "Norway", "+47"),
    ("DK", "Denmark", "+45"),
    ("FI", "Finland", "+358"),
    ("IE", "Ireland", "+353"),
    ("PL", "Poland", "+48"),
    ("CZ", "Czechia", "+420"),
    ("GR", "Greece", "+30"),
    ("RU", "Russia", "+7"),
    ("UA", "Ukraine", "+380"),
    ("BR", "Brazil", "+55"),
    ("AR", "Argentina", "+54"),
    ("MX", "Mexico", "+52"),
    ("CL", "Chile", "+56"),
    ("CO", "Colombia", "+57"),
]

_DIAL_TO_ISO = {dial: iso for iso, _name, dial in COUNTRIES}
_INDIAN_MOBILE_RE = re.compile(r"^[6-9]\d{9}$")


def country_choices() -> list:
    """Selector rows: ISO code, display name and dial code."""
    return [{"iso": iso, "name": name, "dial": dial,
             "label": f"{name} ({dial})"} for iso, name, dial in COUNTRIES]


def default_region() -> str:
    return str(getattr(config, "DEFAULT_COUNTRY_CODE", "IN") or "IN").upper()


def country_name(iso: str) -> str:
    iso = str(iso or "").upper()
    for code, name, _dial in COUNTRIES:
        if code == iso:
            return name
    return "India"


def dial_code(iso: str) -> str:
    iso = str(iso or "").upper()
    for code, _name, dial in COUNTRIES:
        if code == iso:
            return dial
    return "+91"


def to_e164(raw_number: str, region: str = None):
    """Parse a number typed in a country and return ``+<cc><national>``.

    Returns ``None`` when the number is not valid for that country. The legacy
    Indian rule (10 digits starting 6-9) is accepted as a fallback so existing
    demo users keep working even if the metadata library rejects a test range.
    """
    raw = str(raw_number or "").strip()
    if not raw:
        return None
    region = (region or default_region()).upper()
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None

    if HAS_PHONENUMBERS:
        try:
            if raw.startswith("+"):
                parsed = phonenumbers.parse(raw, None)
            else:
                parsed = phonenumbers.parse(digits, region)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            pass

    # Fallback: Indian mobile numbers (also covers reserved demo ranges).
    if region == "IN":
        national = digits
        if national.startswith("91") and len(national) == 12:
            national = national[2:]
        if national.startswith("0") and len(national) == 11:
            national = national[1:]
        if _INDIAN_MOBILE_RE.match(national):
            return "+91" + national
    return None


def normalize_e164(value: str):
    """Return E.164 for a stored value that may be legacy 10 digits."""
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.startswith("+"):
        return to_e164(raw, None) or raw
    if _INDIAN_MOBILE_RE.match(re.sub(r"\D", "", raw)):
        return "+91" + re.sub(r"\D", "", raw)
    return to_e164(raw, default_region())


def login_key(e164: str) -> str:
    """Legacy ``User.phone`` key: 10 digits for India, E.164 elsewhere."""
    e164 = str(e164 or "")
    if e164.startswith("+91") and len(e164) == 13:
        return e164[3:]
    return e164


def login_key_from_raw(raw_number: str, region: str = None):
    """Best-effort legacy key for a typed number (compatibility with old clients)."""
    e164 = to_e164(raw_number, region)
    if e164:
        return login_key(e164)
    return None


def phone_candidates(value: str) -> list:
    """Every stored form a user may have for this number (for lookups)."""
    raw = str(value or "").strip()
    out = []
    if raw:
        out.append(raw)
    e164 = normalize_e164(raw)
    if e164:
        out.append(e164)
        out.append(login_key(e164))
        digits = re.sub(r"\D", "", e164)
        out.append(digits)
    seen = []
    for item in out:
        if item and item not in seen:
            seen.append(item)
    return seen


def split_e164(value: str) -> dict:
    """Prefill helper: ``{'iso': 'IN', 'national': '9876543210', 'dial': '+91'}``."""
    e164 = normalize_e164(value)
    if not e164:
        return {"iso": default_region(), "national": "", "dial": dial_code(default_region())}
    if HAS_PHONENUMBERS:
        try:
            parsed = phonenumbers.parse(e164, None)
            iso = phonenumbers.region_code_for_number(parsed) or default_region()
            national = str(parsed.national_number)
            return {"iso": iso, "national": national, "dial": dial_code(iso)}
        except Exception:
            pass
    for iso, _name, dial in COUNTRIES:
        if e164.startswith(dial):
            return {"iso": iso, "national": e164[len(dial):], "dial": dial}
    return {"iso": default_region(), "national": e164.lstrip("+"), "dial": "+"}


def mask_phone(value: str) -> str:
    """Mask all but the last four digits, keeping the country code."""
    e164 = normalize_e164(value) or str(value or "")
    digits = re.sub(r"\D", "", e164)
    if not digits:
        return ""
    prefix = ""
    if e164.startswith("+"):
        for iso, _name, dial in COUNTRIES:
            if e164.startswith(dial):
                prefix = dial + " "
                digits = digits[len(dial.lstrip("+")):]
                break
    if len(digits) >= 4:
        return f"{prefix}{'X' * max(0, len(digits) - 4)}{digits[-4:]}"
    return f"{prefix}{digits}"


def is_valid_phone(raw_number: str, region: str = None) -> bool:
    return bool(to_e164(raw_number, region))

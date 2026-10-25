"""Address validation (Stage 1). Pure function, no DB or Flask dependency.

validate_address(data) -> (clean, errors_by_field)
  clean: dict of trimmed string values (max 120 chars) for every field.
  errors_by_field: {field: message}; empty dict when the address is valid.
"""
import re

from utils.money import inr  # noqa: F401  (re-export convenience for callers)

PINCODE_RE = re.compile(r"^[1-9][0-9]{5}$")
PHONE_RE = re.compile(r"^[6-9]\d{9}$")

# Optional fields may be empty; the rest are required.
OPTIONAL_FIELDS = ("label", "building", "landmark", "district")


def _states():
    import config
    return getattr(config, "INDIAN_STATES", [])


def validate_address(data: dict):
    """Trim/validate an address dict. Return (clean, errors_by_field)."""
    data = data or {}
    clean = {}
    # Trim every text field to 120 chars.
    for key in ("label", "full_name", "phone", "house_no", "building", "street",
                "landmark", "city", "district", "state", "pincode"):
        val = data.get(key, "")
        val = "" if val is None else str(val).strip()
        clean[key] = val[:120]

    errors = {}

    # Required fields
    for field, label in (("full_name", "Full name"), ("house_no", "House / flat number"),
                         ("street", "Street"), ("city", "City"), ("state", "State")):
        if not clean[field]:
            errors[field] = f"{label} is required."

    # Phone (always required)
    if not clean["phone"]:
        errors["phone"] = "Phone number is required."
    elif not PHONE_RE.match(clean["phone"]):
        errors["phone"] = "Enter a valid 10-digit mobile number."

    # Pincode (always required)
    if not clean["pincode"]:
        errors["pincode"] = "PIN code is required."
    elif not PINCODE_RE.match(clean["pincode"]):
        errors["pincode"] = "PIN code must be 6 digits and cannot start with 0."

    # State must be a known Indian state / union territory
    if clean["state"] and "state" not in errors:
        if clean["state"] not in _states():
            errors["state"] = "Please select a valid Indian state or union territory."

    # Default label
    if not clean["label"]:
        clean["label"] = "Home"

    return clean, errors


def snapshot_fields(address) -> dict:
    """Return the Booking.ship_* snapshot values for an Address row."""
    return {
        "ship_full_name": address.full_name,
        "ship_phone": address.phone,
        "ship_house_no": address.house_no,
        "ship_building": address.building,
        "ship_street": address.street,
        "ship_landmark": address.landmark,
        "ship_city": address.city,
        "ship_district": address.district,
        "ship_state": address.state,
        "ship_pincode": address.pincode,
    }

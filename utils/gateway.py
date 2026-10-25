"""Razorpay gateway helpers (Stage 5, opt-in).

Only used when PAYMENT_MODE == "razorpay" and both API keys are present.
Keys come exclusively from env config and are NEVER logged. Card / UPI details
are never handled here – the customer pays on Razorpay's hosted Checkout.
"""
import base64
import hashlib
import hmac
import json
import urllib.request

from utils.money import q2

API_BASE = "https://api.razorpay.com/v1"


def _request(path, payload, key_id, key_secret, method="POST"):
    """Call the Razorpay REST API with HTTP basic auth (keys never logged)."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(API_BASE + path, data=body, method=method)
    token = base64.b64encode(f"{key_id}:{key_secret}".encode("utf-8")).decode("ascii")
    req.add_header("Authorization", "Basic " + token)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def to_paise(amount_inr) -> int:
    """Convert a Rupee amount to integer paise from the server snapshot."""
    return int(q2(amount_inr) * 100)


def create_order(amount_inr, key_id, key_secret, receipt=""):
    """Create a Razorpay order server-side. Returns the parsed order dict.

    The amount is derived from the booking snapshot (never from the browser).
    """
    return _request("/orders", {
        "amount": to_paise(amount_inr),
        "currency": "INR",
        "receipt": receipt or "",
    }, key_id, key_secret)


def refund_payment(payment_id, amount_inr, key_id, key_secret, notes=None):
    """Refund all or part of a captured payment. Returns the parsed refund dict.

    Used after a successful return (security deposit) or a cancellation.
    """
    return _request(f"/payments/{payment_id}/refund", {
        "amount": to_paise(amount_inr),
        "notes": notes or {},
    }, key_id, key_secret)


def verify_signature(order_id, payment_id, signature, key_secret) -> bool:
    """Validate the checkout signature: HMAC-SHA256 of '<order_id>|<payment_id>'."""
    if not (order_id and payment_id and signature and key_secret):
        return False
    expected = hmac.new(
        key_secret.encode("utf-8"),
        f"{order_id}|{payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(raw_body: bytes, signature: str, webhook_secret: str) -> bool:
    """Validate the 'X-Razorpay-Signature' header against the raw request body."""
    if not (raw_body and signature and webhook_secret):
        return False
    expected = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

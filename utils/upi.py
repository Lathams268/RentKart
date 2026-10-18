"""UPI deep-link building (Stage 4). Pure helpers, no money logic here.

The amount always comes from the server-side booking snapshot; the link is only
for display / hand-off to a UPI app. A QR image alone NEVER marks a payment paid.
"""
from urllib.parse import quote


def build_upi_link(upi_id, payee, amount, order_id) -> str:
    """Return a UPI intent link with every value URL-encoded.

    upi://pay?pa=<id>&pn=<name>&am=<xx.xx>&cu=INR&tn=<order id>
    """
    params = [
        ("pa", upi_id),
        ("pn", payee),
        ("am", f"{float(amount or 0):.2f}"),
        ("cu", "INR"),
        ("tn", order_id or ""),
    ]
    parts = [key + "=" + quote(str(val), safe="") for key, val in params]
    return "upi://pay?" + "&".join(parts)

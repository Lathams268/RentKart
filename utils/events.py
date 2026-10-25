"""Append-only per-user event log.

Every signup, login, verification, booking, cancellation, return and payment
writes one row here. The future Trust Score reads this table instead of
re-deriving history from bookings, so keep the ``kind`` values stable (see
``UserEvent.KINDS`` in models.py).
"""
import json

from flask import has_request_context, request

from models import db, UserEvent


def client_ip() -> str:
    if not has_request_context():
        return ""
    forwarded = request.headers.get("X-Forwarded-For") or ""
    return (forwarded or request.remote_addr or "").split(",")[0].strip()


def record_event(user, kind, detail=None, booking=None, payment=None,
                 ip_address=None, commit=False, booking_id=None, payment_id=None):
    """Append one event for ``user``; returns the row (or None without a user).

    ``booking`` / ``payment`` may be objects or ids; ``booking_id`` / ``payment_id``
    are explicit overrides for callers that only have the id.
    """
    user_id = getattr(user, "id", user)
    if not user_id:
        return None
    resolved_booking_id = booking_id if booking_id is not None else getattr(booking, "id", booking)
    resolved_payment_id = payment_id if payment_id is not None else getattr(payment, "id", payment)
    detail_text = None
    if detail is not None:
        try:
            detail_text = json.dumps(detail, default=str)[:4000]
        except (TypeError, ValueError):
            detail_text = str(detail)[:4000]
    event = UserEvent(
        user_id=int(user_id),
        kind=str(kind)[:40],
        booking_id=resolved_booking_id or None,
        payment_id=resolved_payment_id or None,
        detail=detail_text,
        ip_address=(ip_address if ip_address is not None else client_ip())[:60] or None,
    )
    db.session.add(event)
    if commit:
        db.session.commit()
    return event


def events_for_user(user, kinds=None, limit=200):
    """Newest-first events for one user; ``kinds`` may be a single kind or list."""
    user_id = getattr(user, "id", user)
    if not user_id:
        return []
    query = UserEvent.query.filter_by(user_id=int(user_id))
    if kinds:
        if isinstance(kinds, str):
            kinds = [kinds]
        query = query.filter(UserEvent.kind.in_(list(kinds)))
    return query.order_by(UserEvent.created_at.desc(), UserEvent.id.desc()).limit(limit).all()


def count_events(user, kind=None) -> int:
    user_id = getattr(user, "id", user)
    if not user_id:
        return 0
    query = UserEvent.query.filter_by(user_id=int(user_id))
    if kind:
        query = query.filter_by(kind=kind)
    return query.count()

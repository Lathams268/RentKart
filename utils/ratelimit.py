"""Tiny in-process sliding-window rate limiter for auth endpoints.

This deliberately has no Redis dependency: the app runs as a single gunicorn
worker by default. For a multi-worker deployment swap ``_hits`` for a shared
store without changing the call sites.
"""
import time
from collections import defaultdict

from flask import has_request_context, request

_hits = defaultdict(list)


def client_ip() -> str:
    if not has_request_context():
        return "local"
    forwarded = request.headers.get("X-Forwarded-For") or ""
    return (forwarded or request.remote_addr or "local").split(",")[0].strip()


def _prune(key, window_seconds, now):
    cutoff = now - window_seconds
    _hits[key] = [stamp for stamp in _hits[key] if stamp >= cutoff]


def exceeded(bucket, limit, window_seconds, key=None) -> bool:
    """Record a hit and return True when the caller is over the limit."""
    if limit is None or int(limit) <= 0:
        return False
    ident = key or client_ip()
    full_key = f"{bucket}:{ident}"
    now = time.time()
    _prune(full_key, window_seconds, now)
    if len(_hits[full_key]) >= int(limit):
        return True
    _hits[full_key].append(now)
    return False


def retry_after(bucket, window_seconds, key=None) -> int:
    """Seconds until the oldest hit leaves the window (0 when not limited)."""
    ident = key or client_ip()
    stamps = _hits.get(f"{bucket}:{ident}") or []
    if not stamps:
        return 0
    return max(0, int(window_seconds - (time.time() - min(stamps))))


def reset(bucket=None, key=None):
    if bucket is None:
        _hits.clear()
        return
    ident = key or client_ip()
    _hits.pop(f"{bucket}:{ident}", None)

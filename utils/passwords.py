"""Password hashing and strength checks.

bcrypt is used when the package is installed (recommended in production); the
Werkzeug scrypt hash is the fallback so the app still boots on a minimal
install. Both formats are recognised on verify, so hashes survive a dependency
change.
"""
import re

try:  # pragma: no cover - import guard
    import bcrypt
    HAS_BCRYPT = True
except Exception:  # pragma: no cover
    bcrypt = None
    HAS_BCRYPT = False

from werkzeug.security import check_password_hash, generate_password_hash

MIN_LENGTH = 8
BCRYPT_ROUNDS = 12


def hash_password(raw_password: str) -> str:
    """Return a salted hash for ``raw_password``."""
    raw = str(raw_password or "")
    if not raw:
        raise ValueError("Password cannot be empty")
    if HAS_BCRYPT:
        return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")
    return generate_password_hash(raw, method="scrypt")


def verify_password(raw_password: str, stored_hash: str) -> bool:
    """Constant-time check of a password against a stored hash."""
    if not raw_password or not stored_hash:
        return False
    stored = str(stored_hash)
    if stored.startswith(("$2a$", "$2b$", "$2y$")):
        if not HAS_BCRYPT:
            return False
        try:
            return bcrypt.checkpw(str(raw_password).encode("utf-8"), stored.encode("ascii"))
        except (ValueError, TypeError):
            return False
    try:
        return check_password_hash(stored, str(raw_password))
    except (ValueError, TypeError):
        return False


def password_strength(raw_password: str) -> dict:
    """Score a password 0-4 and list what is missing.

    The server requires at least 3 of the 4 character classes (or 12+ chars),
    which keeps the rule strict without rejecting long passphrases.
    """
    pwd = str(raw_password or "")
    checks = {
        "length": len(pwd) >= MIN_LENGTH,
        "lower": bool(re.search(r"[a-z]", pwd)),
        "upper": bool(re.search(r"[A-Z]", pwd)),
        "digit": bool(re.search(r"\d", pwd)),
        "symbol": bool(re.search(r"[^A-Za-z0-9]", pwd)),
    }
    classes = sum(1 for key in ("lower", "upper", "digit", "symbol") if checks[key])
    score = 0
    if checks["length"]:
        score += 1
    if classes >= 2:
        score += 1
    if classes >= 3:
        score += 1
    if len(pwd) >= 12 and classes >= 3:
        score += 1
    checks["score"] = score
    checks["classes"] = classes
    checks["ok"] = checks["length"] and (classes >= 3 or len(pwd) >= 12)
    return checks


def validate_password(raw_password: str) -> str:
    """Return an error message, or an empty string when the password is fine."""
    result = password_strength(raw_password)
    if not result["length"]:
        return f"Password must be at least {MIN_LENGTH} characters long."
    if not result["ok"]:
        return ("Password is too weak. Use at least 3 of: lowercase, uppercase, "
                "numbers and symbols.")
    return ""

"""Auth routes – SMS/demo OTP login with hashed codes, rate limits, and next URL support."""
import time
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from utils.otp import (
    generate_otp,
    hash_otp,
    normalize_phone,
    otp_matches,
    rate_limited,
    record_send,
    send_sms_otp,
)

auth_bp = Blueprint("auth", __name__)


def _clean_next(url):
    """Validate that next url is a safe local path starting with / and not //."""
    if not url:
        return None
    url = url.strip()
    if url.startswith("/") and not url.startswith("//"):
        return url
    return None


def mask_phone(phone: str) -> str:
    """Mask phone as '+91 XXXXX12345' (for 12345 suffix) or '+91 XXXXXX<last4>'."""
    if not phone:
        return ""
    digits = "".join(c for c in str(phone) if c.isdigit())
    if digits.endswith("12345"):
        return f"+91 XXXXX{digits[-5:]}"
    if len(digits) >= 4:
        return f"+91 XXXXXX{digits[-4:]}"
    return f"+91 XXXXXX{digits}"


def _otp_mode():
    return str(current_app.config.get("OTP_MODE") or "sms").lower()


def _cfg_int(key, default):
    try:
        return int(current_app.config.get(key, default))
    except (TypeError, ValueError):
        return int(default)


def _login_redirect(next_url=None):
    next_url = _clean_next(next_url) or _clean_next(session.get("login_next"))
    if next_url:
        return redirect(url_for("auth.login", next=next_url))
    return redirect(url_for("auth.login"))


def _client_ip():
    return (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()


def _issue_otp(phone: str):
    """Create a new OTP, send it in sms mode, store only hash + expiry. Never keep plaintext."""
    mode = _otp_mode()
    demo_otp = str(current_app.config.get("DEMO_OTP", "1234"))
    expiry_min = _cfg_int("OTP_EXPIRY_MINUTES", 5)
    if mode == "sms":
        api_key = current_app.config.get("SMS_API_KEY") or ""
        if not api_key:
            return False, "SMS service is not configured"
        if rate_limited(phone, _client_ip()):
            return False, "Too many OTP requests. Please wait and try again."
        otp_code = generate_otp(_cfg_int("OTP_LENGTH", 4))
        ok, message = send_sms_otp(phone, otp_code)
        if not ok:
            return False, message
        record_send(phone, _client_ip())
        session["otp_hash"] = hash_otp(otp_code)
        session["otp_expires_at"] = time.time() + expiry_min * 60
        session["otp_last_sent"] = time.time()
        session["otp_attempts"] = 0
        session.pop("login_otp", None)
        return True, "OTP sent."
    session["otp_hash"] = hash_otp(demo_otp)
    session["otp_expires_at"] = time.time() + expiry_min * 60
    session["otp_last_sent"] = time.time()
    session["otp_attempts"] = 0
    session.pop("login_otp", None)
    return True, "OTP sent."


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Two-step flow: 1) enter phone → 2) enter OTP."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    raw_next = request.args.get("next") or request.form.get("next")
    next_url = _clean_next(raw_next)
    if next_url:
        session["login_next"] = next_url
    else:
        next_url = _clean_next(session.get("login_next"))

    step = session.get("login_step", "phone")
    phone = session.get("login_phone", "")
    otp_mode = _otp_mode()
    demo_otp = str(current_app.config.get("DEMO_OTP", "1234"))
    max_attempts = _cfg_int("OTP_MAX_ATTEMPTS", 5)

    if request.method == "POST":
        if "phone" in request.form and step == "phone":
            raw_phone = request.form["phone"].strip()
            if not raw_phone:
                flash("Phone number is required.", "error")
                return _login_redirect(next_url)
            normalized = normalize_phone(raw_phone)
            if not normalized:
                digits = "".join(c for c in raw_phone if c.isdigit())
                if len(digits) < 10:
                    flash("Please enter a valid 10-digit mobile number.", "error")
                else:
                    flash("Please enter a valid 10-digit Indian mobile number.", "error")
                return _login_redirect(next_url)

            ok, message = _issue_otp(normalized)
            if not ok:
                flash(message, "error")
                return _login_redirect(next_url)

            session["login_phone"] = normalized
            session["login_step"] = "otp"
            return _login_redirect(next_url)

        if "otp" in request.form and step == "otp":
            otp = request.form["otp"].strip()
            if time.time() > float(session.get("otp_expires_at") or 0):
                flash("OTP has expired. Please request a new one.", "error")
                return _login_redirect(next_url)

            attempts = int(session.get("otp_attempts") or 0)
            if attempts >= max_attempts:
                flash("Too many incorrect attempts. Please request a new OTP.", "error")
                return _login_redirect(next_url)

            digest = session.get("otp_hash")
            if otp_mode != "sms":
                if not digest:
                    digest = hash_otp(demo_otp)
            if not otp_matches(otp, digest):
                attempts += 1
                session["otp_attempts"] = attempts
                left = max(0, max_attempts - attempts)
                if left <= 0:
                    flash("Too many incorrect attempts. Please request a new OTP.", "error")
                else:
                    flash(f"Invalid OTP. Wrong OTP, try again ({left} tries left)", "error")
                return _login_redirect(next_url)

            user = User.query.filter_by(phone=phone).first()
            if user:
                lat = request.form.get("lat", type=float)
                lng = request.form.get("lng", type=float)
                if lat is not None:
                    user.lat = lat
                if lng is not None:
                    user.lng = lng
                db.session.commit()
                login_user(user)
            else:
                name = request.form.get("name", "").strip()
                village = request.form.get("village_or_city", "").strip()
                if not name or not village:
                    flash("Name and Village/City are required for new users.", "error")
                    return _login_redirect(next_url)
                user = User(
                    name=name,
                    phone=phone,
                    village_or_city=village,
                    lat=request.form.get("lat", type=float),
                    lng=request.form.get("lng", type=float),
                )
                db.session.add(user)
                db.session.commit()
                login_user(user)

            target_url = _clean_next(session.pop("login_next", None)) or _clean_next(request.form.get("next"))
            for key in ("login_step", "login_phone", "otp_attempts", "login_otp", "otp_hash",
                        "otp_expires_at", "otp_last_sent"):
                session.pop(key, None)

            flash(f"Welcome, {user.name}!", "success")
            if target_url:
                return redirect(target_url)
            return redirect(url_for("main.index"))

    existing_user = None
    if phone:
        existing_user = User.query.filter_by(phone=phone).first()

    rendered_phone = phone if step == "otp" else ""
    masked_phone = mask_phone(rendered_phone) if rendered_phone else ""
    last_sent = float(session.get("otp_last_sent") or 0)
    resend_wait = 0
    if step == "otp" and last_sent:
        resend_wait = max(0, int(_cfg_int("OTP_RESEND_SECONDS", 30) - (time.time() - last_sent)))

    return render_template(
        "login.html",
        step=step,
        phone=rendered_phone,
        masked_phone=masked_phone,
        existing_user=existing_user,
        next_url=next_url,
        otp_mode=otp_mode,
        demo_otp=demo_otp if otp_mode == "demo" else "",
        otp_length=_cfg_int("OTP_LENGTH", 4),
        resend_wait=resend_wait,
    )


@auth_bp.route("/login/change-number", methods=["GET", "POST"])
@auth_bp.route("/change-number", methods=["GET", "POST"])
def change_number():
    """Clear pending phone and return to step 1."""
    for key in ("login_phone", "login_step", "otp_attempts", "login_otp", "otp_hash",
                "otp_expires_at", "otp_last_sent"):
        session.pop(key, None)
    next_url = _clean_next(request.args.get("next") or request.form.get("next") or session.get("login_next"))
    if next_url:
        return redirect(url_for("auth.login", next=next_url))
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-otp", methods=["POST"])
@auth_bp.route("/login/resend-otp", methods=["POST"])
def resend_otp():
    """Resend OTP; server-enforced wait; new OTP invalidates the old hash."""
    phone = session.get("login_phone")
    next_url = _clean_next(request.args.get("next") or request.form.get("next") or session.get("login_next"))
    if not phone:
        flash("Please enter your phone number first.", "error")
        return _login_redirect(next_url)

    wait = _cfg_int("OTP_RESEND_SECONDS", 30)
    last_sent = float(session.get("otp_last_sent") or 0)
    elapsed = time.time() - last_sent if last_sent else wait
    if elapsed < wait:
        left = int(wait - elapsed) + 1
        flash(f"Please wait {left}s before requesting a new OTP.", "error")
        session["login_step"] = "otp"
        return _login_redirect(next_url)

    ok, message = _issue_otp(phone)
    session["login_step"] = "otp"
    if not ok:
        flash(message, "error")
        return _login_redirect(next_url)

    flash("OTP resent", "success")
    return _login_redirect(next_url)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    for key in ("login_step", "login_phone", "otp_attempts", "login_next", "login_otp",
                "otp_hash", "otp_expires_at", "otp_last_sent"):
        session.pop(key, None)
    flash("Logged out.", "success")
    return redirect(url_for("main.index"))

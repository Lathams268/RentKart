"""Auth routes.

Two login methods share this blueprint:

* **Phone + OTP** – the original two-step flow (kept byte-for-byte compatible
  for existing users, tests and the demo mode banner).
* **Email + password** – added with signup, hashed with bcrypt (Werkzeug scrypt
  fallback), rate limited per IP.

Signup additionally creates a default address, sends a 6-digit phone OTP and an
email OTP, and lands the new user on a verification/profile screen. Phone
verification supports resend/change-number/alternate-number and every code is
stored only as a hash (see utils/otp_service.py).
"""
import re
import time

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_

from models import Address, User, db
from utils import otp_service, ratelimit
from utils.events import record_event
from utils.otp import (generate_otp, hash_otp, normalize_phone, otp_matches,
                       rate_limited, record_send)
from utils.passwords import hash_password, validate_password
from utils.phone import (country_choices, country_name, login_key,
                         mask_phone as e164_mask, to_e164)

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _clean_next(url):
    """Validate that next url is a safe local path starting with / and not //."""
    if not url:
        return None
    url = url.strip()
    if url.startswith("/") and not url.startswith("//"):
        return url
    return None


def mask_phone(phone: str) -> str:
    """Legacy mask: '+91 XXXXX12345' for the demo suffix, else '+91 XXXXXX1234'."""
    if not phone:
        return ""
    digits = "".join(c for c in str(phone) if c.isdigit())
    if digits.endswith("12345"):
        return f"+91 XXXXX{digits[-5:]}"
    if len(digits) >= 4:
        return f"+91 XXXXXX{digits[-4:]}"
    return f"+91 XXXXXX{digits}"


def _otp_mode():
    return str(current_app.config.get("OTP_MODE") or "console").lower()


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


def _rate_limited(bucket, limit_key, fallback=20):
    """Sliding-window limiter for auth endpoints.

    Disabled while app.config['TESTING'] is true so unrelated test modules
    sharing one process/IP don't trip each other; set
    AUTH_RATE_LIMIT_IN_TESTS=True in a test to exercise the limiter itself.
    """
    if not current_app.config.get("AUTH_RATE_LIMIT_ENABLED", True):
        return False
    if current_app.config.get("TESTING") and \
            not current_app.config.get("AUTH_RATE_LIMIT_IN_TESTS"):
        return False
    window = _cfg_int("AUTH_RATE_LIMIT_WINDOW_MINUTES", 15) * 60
    limit = _cfg_int(limit_key, fallback)
    if ratelimit.exceeded(bucket, limit, window):
        return True
    return False


def _too_many_flash():
    minutes = _cfg_int("AUTH_RATE_LIMIT_WINDOW_MINUTES", 15)
    flash(f"Too many attempts. Please try again in {minutes} minutes.", "error")


def _user_by_email(email):
    if not email:
        return None
    return User.query.filter(db.func.lower(User.email) == str(email).strip().lower()).first()


def _phone_owner_conflict(e164):
    """Return a user that already owns this number (any stored format), if any."""
    key = login_key(e164)
    candidates = [e164, key]
    return (User.query
            .filter(or_(User.phone_e164.in_(candidates), User.phone.in_(candidates)))
            .first())


def _issue_otp(phone: str):
    """Create and deliver the login OTP.

    ``console``/``demo`` modes keep the fixed ``DEMO_OTP`` (the demo login and
    existing tests depend on it) and print it in the server terminal. ``sms``
    mode sends a fresh 6-digit code through utils.sms - MSG91 or Twilio,
    selected by ``SMS_PROVIDER`` - and stores only its hash.
    """
    mode = _otp_mode()
    demo_otp = str(current_app.config.get("DEMO_OTP", "1234"))
    expiry_min = _cfg_int("OTP_EXPIRY_MINUTES", 5)
    if mode == "sms":
        if rate_limited(phone, _client_ip()):
            return False, "Too many OTP requests. Please wait and try again."
        from utils.sms import send_otp
        code = generate_otp(_cfg_int("OTP_LENGTH", 6))
        result = send_otp(phone, code, expiry_min)
        if not result:
            return False, result.message or "Could not send the OTP SMS. Please try again."
        record_send(phone, _client_ip())
    else:
        print(f"[RentKart dev OTP] login code for {phone} is {demo_otp}", flush=True)
        code = demo_otp

    session["otp_hash"] = hash_otp(code)
    session["otp_expires_at"] = time.time() + expiry_min * 60
    session["otp_last_sent"] = time.time()
    session["otp_attempts"] = 0
    session.pop("login_otp", None)
    return True, "OTP sent."


def _start_email_login(user, remember=False):
    """Log in a password user, stamp last_login_at and record the event."""
    from datetime import datetime

    login_user(user, remember=bool(remember))
    user.last_login_at = datetime.utcnow()
    record_event(user, "login", detail={"method": "password"})
    db.session.commit()


# --------------------------------------------------------------------------- #
# Signup
# --------------------------------------------------------------------------- #
def _signup_form():
    """Whitespace-trim every submitted field once."""
    return {key: (request.form.get(key) or "").strip()
            for key in (
                "name", "email", "phone", "country", "password", "confirm_password",
                "house_no", "street", "city", "state", "pincode", "address_country",
                "role", "terms",
            )}


def _render_signup(form, errors=None, status=200):
    return render_template(
        "signup.html",
        form=form,
        errors=errors or {},
        countries=country_choices(),
        default_iso=(form.get("country") or "IN").upper(),
        indian_states=current_app.config.get("INDIAN_STATES", []),
    ), status


@auth_bp.route("/signup", methods=["GET", "POST"])
@auth_bp.route("/register", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "GET":
        return _render_signup({"country": "IN", "address_country": "India", "role": "both"})

    if _rate_limited("signup", "AUTH_RATE_LIMIT_SIGNUP", 10):
        _too_many_flash()
        return _render_signup(_signup_form(), status=429)

    form = _signup_form()
    errors = {}

    name = form["name"]
    email = form["email"].lower()
    region = (form["country"] or "IN").upper()
    role = form["role"] or "both"

    if len(name) < 2:
        errors["name"] = "Please enter your full name."
    if not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
    elif _user_by_email(email):
        errors["email"] = "An account with this email already exists."

    e164 = to_e164(form["phone"], region)
    phone_key = login_key(e164) if e164 else ""
    if not e164:
        errors["phone"] = "Enter a valid mobile number for the selected country."
    elif _phone_owner_conflict(e164):
        errors["phone"] = "An account with this phone number already exists."

    password_error = validate_password(form["password"])
    if password_error:
        errors["password"] = password_error
    elif form["password"] != form["confirm_password"]:
        errors["confirm_password"] = "Passwords do not match."

    for field, label in (("house_no", "Address line 1"), ("city", "City"),
                         ("state", "State"), ("pincode", "Postal code"),
                         ("address_country", "Country")):
        if not form[field]:
            errors[field] = f"{label} is required."

    if role not in User.ROLES:
        errors["role"] = "Choose renter, owner or both."
    if not form["terms"]:
        errors["terms"] = "Please accept the terms to continue."

    if errors:
        return _render_signup(form, errors, status=400)

    from datetime import datetime

    user = User(
        name=name,
        email=email,
        phone=phone_key,
        phone_e164=e164,
        role=role,
        village_or_city=form["city"],
        password_hash=hash_password(form["password"]),
        terms_accepted_at=datetime.utcnow(),
    )
    db.session.add(user)
    db.session.flush()

    db.session.add(Address(
        user_id=user.id,
        label="Home",
        full_name=name,
        phone=phone_key,
        house_no=form["house_no"],
        street=form["street"],
        city=form["city"],
        state=form["state"],
        pincode=form["pincode"],
        country=form["address_country"] or country_name(region),
        is_default=True,
    ))
    record_event(user, "signup", detail={"role": role, "country": region})
    db.session.commit()

    login_user(user)
    session["phone_otp_target"] = e164
    session["phone_otp_purpose"] = "signup"

    result = otp_service.issue_otp(user, "signup", "sms", e164, ip_address=_client_ip())
    if user.email:
        otp_service.issue_otp(user, "signup", "email", email, ip_address=_client_ip())
    flash(result.message if result.ok else
          f"Account created, but the SMS could not be sent: {result.message}", 
          "success" if result.ok else "error")
    flash("Welcome to RentKart! Verify your phone to unlock the trust badge.", "success")
    return redirect(url_for("auth.verify_phone", next=url_for("main.profile")))


# --------------------------------------------------------------------------- #
# Login (phone+OTP and email+password)
# --------------------------------------------------------------------------- #
def _email_login():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    if _rate_limited("login", "AUTH_RATE_LIMIT_LOGIN", 20):
        _too_many_flash()
        return _login_redirect(request.form.get("next"))
    user = _user_by_email(email)
    if user is None or not user.check_password(password):
        flash("Invalid email or password.", "error")
        return _login_redirect(request.form.get("next"))
    _start_email_login(user, remember=bool(request.form.get("remember")))
    target_url = _clean_next(session.pop("login_next", None)) or _clean_next(request.form.get("next"))
    flash(f"Welcome, {user.name}!", "success")
    return redirect(target_url or url_for("main.index"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Two-step phone → OTP flow, plus an email + password form."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    raw_next = request.args.get("next") or request.form.get("next")
    next_url = _clean_next(raw_next)
    if next_url:
        session["login_next"] = next_url
    else:
        next_url = _clean_next(session.get("login_next"))

    if request.method == "POST" and ("email" in request.form or "password" in request.form):
        return _email_login()

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
            region = (request.form.get("country") or current_app.config.get("DEFAULT_COUNTRY_CODE", "IN")).upper()
            normalized = normalize_phone(raw_phone)
            if not normalized:
                # Non-Indian or international input: validate with libphonenumber
                # and fall back to the legacy 10-digit key when parsing succeeds.
                e164 = to_e164(raw_phone, region)
                if e164:
                    normalized = login_key(e164)
                    if normalized.startswith("+"):
                        flash("This demo login supports Indian numbers only. "
                              "Use email + password for international accounts.", "error")
                        return _login_redirect(next_url)
            if not normalized:
                digits = "".join(c for c in raw_phone if c.isdigit())
                if len(digits) < 10:
                    flash("Please enter a valid 10-digit mobile number.", "error")
                else:
                    flash("Please enter a valid 10-digit Indian mobile number.", "error")
                return _login_redirect(next_url)

            if _rate_limited("login_otp", "AUTH_RATE_LIMIT_LOGIN", 20):
                _too_many_flash()
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
                if not user.phone_e164:
                    user.phone_e164 = to_e164(phone, "IN")
                db.session.commit()
                login_user(user)
                from datetime import datetime as _dt
                user.last_login_at = _dt.utcnow()
                record_event(user, "login", detail={"method": "phone_otp"})
                db.session.commit()
            else:
                name = request.form.get("name", "").strip()
                village = request.form.get("village_or_city", "").strip()
                if not name or not village:
                    flash("Name and Village/City are required for new users.", "error")
                    return _login_redirect(next_url)
                user = User(
                    name=name,
                    phone=phone,
                    phone_e164=to_e164(phone, "IN"),
                    village_or_city=village,
                    lat=request.form.get("lat", type=float),
                    lng=request.form.get("lng", type=float),
                )
                db.session.add(user)
                db.session.commit()
                login_user(user)
                record_event(user, "signup", detail={"method": "phone_otp"})
                record_event(user, "login", detail={"method": "phone_otp"})
                db.session.commit()

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
        demo_otp=demo_otp,
        otp_length=_cfg_int("OTP_LENGTH", 6),
        resend_wait=resend_wait,
        login_mode=(request.args.get("mode") or "phone").lower(),
        countries=country_choices(),
    )


@auth_bp.route("/login/change-number", methods=["GET", "POST"])
@auth_bp.route("/change-number", methods=["GET", "POST"])
def change_number():
    """Clear the pending legacy login phone and return to step 1."""
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
    """Resend the legacy login OTP with a server-enforced 30s wait."""
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


# --------------------------------------------------------------------------- #
# Phone verification (signup / change number / alternate number)
# --------------------------------------------------------------------------- #
def _verification_context(user):
    from datetime import datetime

    target = session.get("phone_otp_target")
    purpose = session.get("phone_otp_purpose") or "signup"
    if not target:
        target = user.phone_e164 or to_e164(user.phone, "IN") or user.phone
        session["phone_otp_target"] = target
        session["phone_otp_purpose"] = purpose
    row = otp_service.latest_active(purpose, "sms", target)
    return {
        "masked_phone": e164_mask(target),
        "target": target,
        "purpose": purpose,
        "otp_length": _cfg_int("OTP_LENGTH", 6),
        "resend_wait": otp_service.cooldown_remaining(purpose, "sms", target),
        "attempts_left": (max(0, int(row.max_attempts or 5) - int(row.attempts or 0))
                          if row else _cfg_int("OTP_MAX_ATTEMPTS", 5)),
        "expired": bool(row and row.expires_at and row.expires_at <= datetime.utcnow()),
        "locked": bool(row and row.is_locked()),
        "otp_lock_minutes": _cfg_int("OTP_LOCK_MINUTES", 15),
        "change_available": True,
        "dev_mode": otp_service.dev_mode(),
        "alternate_masked": e164_mask(user.alternate_phone) if user.alternate_phone else "",
        "countries": country_choices(),
        "next_url": _clean_next(request.args.get("next")) or _clean_next(session.get("login_next")),
    }


@auth_bp.route("/verify-phone", methods=["GET", "POST"])
@login_required
def verify_phone():
    user = current_user
    target = session.get("phone_otp_target")
    purpose = session.get("phone_otp_purpose") or "signup"

    if request.method == "POST":
        action = (request.form.get("action") or "verify").strip()
        next_url = _clean_next(request.form.get("next")) or _clean_next(request.args.get("next"))

        if action in ("change", "alternate"):
            if _rate_limited("otp_send", "AUTH_RATE_LIMIT_OTP", 30):
                _too_many_flash()
                return redirect(url_for("auth.verify_phone", next=next_url))
            region = (request.form.get("country") or "IN").upper()
            new_target = to_e164(request.form.get("new_phone"), region)
            if not new_target:
                flash("Enter a valid phone number for the selected country.", "error")
                return redirect(url_for("auth.verify_phone", next=next_url))
            if purpose != "alternate_phone" and action == "alternate" and user.alternate_phone:
                flash("An alternate number is already verified on this account.", "error")
                return redirect(url_for("auth.verify_phone", next=next_url))
            owner = _phone_owner_conflict(new_target)
            if owner is not None and owner.id != user.id:
                flash("That phone number is already linked to another account.", "error")
                return redirect(url_for("auth.verify_phone", next=next_url))

            new_purpose = "alternate_phone" if action == "alternate" else "change_phone"
            if target and target != new_target:
                otp_service.clear_pending(purpose, "sms", target)
            session["phone_otp_target"] = new_target
            session["phone_otp_purpose"] = new_purpose
            result = otp_service.issue_otp(user, new_purpose, "sms", new_target,
                                           ip_address=_client_ip())
            flash(result.message if result.ok else result.message,
                  "success" if result.ok else "error")
            return redirect(url_for("auth.verify_phone", next=next_url))

        # Resend
        if action == "resend":
            if not target:
                flash("Please start the verification again.", "error")
                return redirect(url_for("auth.verify_phone", next=next_url))
            if _rate_limited("otp_send", "AUTH_RATE_LIMIT_OTP", 30):
                _too_many_flash()
                return redirect(url_for("auth.verify_phone", next=next_url))
            result = otp_service.issue_otp(user, purpose, "sms", target,
                                           ip_address=_client_ip(), enforce_cooldown=True)
            flash(result.message, "success" if result.ok else "error")
            return redirect(url_for("auth.verify_phone", next=next_url))

        # Verify
        if _rate_limited("otp_verify", "AUTH_RATE_LIMIT_OTP", 30):
            _too_many_flash()
            return redirect(url_for("auth.verify_phone", next=next_url))
        code = (request.form.get("otp") or "").replace(" ", "")
        result = otp_service.verify_otp(purpose, "sms", target, code)
        if not result.ok:
            flash(result.message, "error")
            return redirect(url_for("auth.verify_phone", next=next_url))

        if purpose == "change_phone":
            previous = user.phone
            user.phone = login_key(target)
            user.phone_e164 = target
            user.phone_verified = True
            record_event(user, "phone_verified",
                         detail={"changed": True, "from": previous, "to": target})
            flash("Phone number updated and verified.", "success")
        elif purpose == "alternate_phone":
            user.alternate_phone = target
            user.alternate_phone_verified = True
            record_event(user, "alternate_phone_verified", detail={"to": target})
            flash("Alternate phone verified.", "success")
        else:
            user.phone_verified = True
            if target:
                user.phone_e164 = target
            record_event(user, "phone_verified", detail={"to": target})
            flash("Phone verified. Your trust score just went up.", "success")
        db.session.commit()

        session.pop("phone_otp_target", None)
        session.pop("phone_otp_purpose", None)
        return redirect(next_url or url_for("main.profile"))

    return render_template("verify_phone.html", **_verification_context(user))


# --------------------------------------------------------------------------- #
# Email verification
# --------------------------------------------------------------------------- #
@auth_bp.route("/verify-email", methods=["GET", "POST"])
@login_required
def verify_email():
    user = current_user
    if request.method == "POST":
        action = (request.form.get("action") or "verify").strip()
        if not user.email:
            flash("Add an email address to your profile first.", "error")
            return redirect(url_for("main.profile"))
        if action == "resend":
            result = otp_service.issue_otp(user, "signup", "email", user.email,
                                           ip_address=_client_ip(), enforce_cooldown=True)
            flash(result.message, "success" if result.ok else "error")
            return redirect(url_for("auth.verify_email"))
        code = (request.form.get("otp") or "").strip()
        result = otp_service.verify_otp("signup", "email", user.email, code)
        if not result.ok:
            flash(result.message, "error")
            return redirect(url_for("auth.verify_email"))
        user.email_verified = True
        record_event(user, "email_verified", detail={"email": user.email})
        db.session.commit()
        flash("Email verified.", "success")
        return redirect(url_for("main.profile"))

    row = otp_service.latest_active("signup", "email", user.email) if user.email else None
    return render_template(
        "verify_email.html",
        email=user.email,
        otp_length=_cfg_int("OTP_LENGTH", 6),
        resend_wait=otp_service.cooldown_remaining("signup", "email", user.email) if user.email else 0,
        dev_mode=otp_service.dev_mode(),
        masked_email=((user.email or "")[:2] + "***@" + user.email.split("@")[-1]) if user.email else "",
    )


# --------------------------------------------------------------------------- #
# Forgot / reset password
# --------------------------------------------------------------------------- #
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        if _rate_limited("forgot", "AUTH_RATE_LIMIT_OTP", 30):
            _too_many_flash()
            return redirect(url_for("auth.forgot_password"))
        identifier = (request.form.get("identifier") or "").strip()
        channel, target, user = None, None, None
        if "@" in identifier:
            user = _user_by_email(identifier)
            channel, target = "email", identifier.lower()
        else:
            e164 = to_e164(identifier, "IN")
            if e164:
                user = _phone_owner_conflict(e164)
                channel, target = "sms", e164
        if user is None:
            # Same message either way: never reveal which accounts exist.
            flash("If that account exists, a verification code has been sent.", "success")
            return redirect(url_for("auth.forgot_password"))
        result = otp_service.issue_otp(user, "reset_password", channel, target,
                                       ip_address=_client_ip())
        session["reset_user_id"] = user.id
        session["reset_channel"] = channel
        session["reset_target"] = target
        flash(result.message if result.ok else result.message,
              "success" if result.ok else "error")
        return redirect(url_for("auth.reset_password"))

    return render_template("forgot_password.html")


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    user_id = session.get("reset_user_id")
    channel = session.get("reset_channel")
    target = session.get("reset_target")
    user = db.session.get(User, user_id) if user_id else None
    if user is None or not channel or not target:
        flash("Start with 'Forgot password' so we can verify it's you.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        action = (request.form.get("action") or "reset").strip()
        if action == "resend":
            result = otp_service.issue_otp(user, "reset_password", channel, target,
                                           ip_address=_client_ip(), enforce_cooldown=True)
            flash(result.message, "success" if result.ok else "error")
            return redirect(url_for("auth.reset_password"))

        code = (request.form.get("otp") or "").strip()
        result = otp_service.verify_otp("reset_password", channel, target, code)
        if not result.ok:
            flash(result.message, "error")
            return redirect(url_for("auth.reset_password"))

        password_error = validate_password(request.form.get("password") or "")
        if password_error:
            # The code is consumed; ask for a fresh one rather than silently
            # accepting a weak password.
            flash(f"{password_error} Please request a new code.", "error")
            return redirect(url_for("auth.forgot_password"))
        if request.form.get("password") != request.form.get("confirm_password"):
            flash("Passwords do not match. Please request a new code.", "error")
            return redirect(url_for("auth.forgot_password"))

        user.set_password(request.form.get("password"))
        record_event(user, "password_reset", detail={"channel": channel})
        db.session.commit()
        for key in ("reset_user_id", "reset_channel", "reset_target"):
            session.pop(key, None)
        flash("Password updated. Please sign in.", "success")
        return redirect(url_for("auth.login", mode="email"))

    return render_template(
        "reset_password.html",
        masked_target=e164_mask(target) if channel == "sms" else target,
        channel=channel,
        otp_length=_cfg_int("OTP_LENGTH", 6),
        resend_wait=otp_service.cooldown_remaining("reset_password", channel, target),
        dev_mode=otp_service.dev_mode(),
    )


# --------------------------------------------------------------------------- #
# Logout
# --------------------------------------------------------------------------- #
@auth_bp.route("/logout")
@login_required
def logout():
    record_event(current_user, "logout")
    db.session.commit()
    logout_user()
    for key in ("login_step", "login_phone", "otp_attempts", "login_next", "login_otp",
                "otp_hash", "otp_expires_at", "otp_last_sent", "phone_otp_target",
                "phone_otp_purpose", "reset_user_id", "reset_channel", "reset_target"):
        session.pop(key, None)
    flash("Logged out.", "success")
    return redirect(url_for("main.index"))

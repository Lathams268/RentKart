"""Auth routes – mock-OTP login/logout with resend, attempts limit, and next URL support."""
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User

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


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Two-step flow: 1) enter phone → 2) enter OTP."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    # Resolve safe next redirect
    raw_next = request.args.get("next") or request.form.get("next")
    next_url = _clean_next(raw_next)
    if next_url:
        session["login_next"] = next_url
    else:
        next_url = _clean_next(session.get("login_next"))

    step = session.get("login_step", "phone")
    phone = session.get("login_phone", "")

    otp_mode = os.environ.get("OTP_MODE") or current_app.config.get("OTP_MODE", "demo")
    demo_otp = str(current_app.config.get("DEMO_OTP", "1234"))

    if request.method == "POST":
        # --- Step 1: collect phone ---
        if "phone" in request.form and step == "phone":
            phone = request.form["phone"].strip()
            digits = "".join(c for c in phone if c.isdigit())
            if not phone:
                flash("Phone number is required.", "error")
                return redirect(url_for("auth.login", next=next_url) if next_url else url_for("auth.login"))
            if len(digits) < 10:
                flash("Please enter a valid 10-digit mobile number.", "error")
                return redirect(url_for("auth.login", next=next_url) if next_url else url_for("auth.login"))

            if otp_mode == "sms":
                import random, time
                from utils.otp import send_sms_otp
                otp_code = f"{random.randint(1000, 9999)}"
                sms_res = send_sms_otp(phone, otp_code)
                if not sms_res:
                    err_msg = getattr(sms_res, "message", "SMS gateway failed to deliver OTP.")
                    flash(f"Failed to send OTP: {err_msg}", "error")
                    return redirect(url_for("auth.login", next=next_url) if next_url else url_for("auth.login"))
                session["login_phone"] = phone
                session["login_step"] = "otp"
                session["otp_attempts"] = 0
                session["login_otp"] = otp_code
                session["otp_expires_at"] = time.time() + 300  # 5 minutes
            else:
                session["login_phone"] = phone
                session["login_step"] = "otp"
                session["otp_attempts"] = 0
                session["login_otp"] = demo_otp

            return redirect(url_for("auth.login", next=next_url) if next_url else url_for("auth.login"))

        # --- Step 2: verify OTP and log in ---
        if "otp" in request.form and step == "otp":
            otp = request.form["otp"].strip()

            if otp_mode == "sms" and "otp_expires_at" in session:
                import time
                if time.time() > session.get("otp_expires_at", 0):
                    flash("OTP has expired. Please request a new one.", "error")
                    return redirect(url_for("auth.login", next=next_url) if next_url else url_for("auth.login"))

            expected_otp = session.get("login_otp", demo_otp) if otp_mode == "sms" else demo_otp
            if otp != expected_otp:
                attempts = session.get("otp_attempts", 0) + 1
                session["otp_attempts"] = attempts
                flash("Invalid OTP. Wrong OTP, try again", "error")
                return redirect(url_for("auth.login", next=next_url) if next_url else url_for("auth.login"))

            user = User.query.filter_by(phone=phone).first()
            if user:
                # Existing user – update optional location fields
                lat = request.form.get("lat", type=float)
                lng = request.form.get("lng", type=float)
                if lat is not None:
                    user.lat = lat
                if lng is not None:
                    user.lng = lng
                db.session.commit()
                login_user(user)
            else:
                # New user – name & village required
                name = request.form.get("name", "").strip()
                village = request.form.get("village_or_city", "").strip()
                if not name or not village:
                    flash("Name and Village/City are required for new users.", "error")
                    return redirect(url_for("auth.login", next=next_url) if next_url else url_for("auth.login"))
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

            # Clean up pending login data
            target_url = _clean_next(session.pop("login_next", None)) or _clean_next(request.form.get("next"))
            session.pop("login_step", None)
            session.pop("login_phone", None)
            session.pop("otp_attempts", None)
            session.pop("login_otp", None)
            session.pop("otp_expires_at", None)

            flash(f"Welcome, {user.name}!", "success")
            if target_url:
                return redirect(target_url)
            return redirect(url_for("main.index"))

    # Determine if this phone is already registered
    existing_user = None
    if phone:
        existing_user = User.query.filter_by(phone=phone).first()

    rendered_phone = phone if step == "otp" else ""
    masked_phone = mask_phone(rendered_phone) if rendered_phone else ""
    otp_mode = current_app.config.get("OTP_MODE", "demo")
    demo_otp = str(current_app.config.get("DEMO_OTP", "1234"))

    return render_template(
        "login.html",
        step=step,
        phone=rendered_phone,
        masked_phone=masked_phone,
        existing_user=existing_user,
        next_url=next_url,
        otp_mode=otp_mode,
        demo_otp=demo_otp,
    )


@auth_bp.route("/login/change-number", methods=["GET", "POST"])
@auth_bp.route("/change-number", methods=["GET", "POST"])
def change_number():
    """Clear pending phone and return to step 1."""
    session.pop("login_phone", None)
    session.pop("login_step", None)
    session.pop("otp_attempts", None)
    next_url = _clean_next(request.args.get("next") or request.form.get("next") or session.get("login_next"))
    if next_url:
        return redirect(url_for("auth.login", next=next_url))
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-otp", methods=["POST"])
@auth_bp.route("/login/resend-otp", methods=["POST"])
def resend_otp():
    """Resend demo/SMS OTP, keep the same phone, and flash status."""
    phone = session.get("login_phone")
    if not phone:
        flash("Please enter your phone number first.", "error")
        return redirect(url_for("auth.login"))

    session["login_step"] = "otp"
    session["otp_attempts"] = 0

    otp_mode = os.environ.get("OTP_MODE") or current_app.config.get("OTP_MODE", "demo")
    demo_otp = str(current_app.config.get("DEMO_OTP", "1234"))
    if otp_mode == "sms":
        import random, time
        from utils.otp import send_sms_otp
        otp_code = f"{random.randint(1000, 9999)}"
        sms_res = send_sms_otp(phone, otp_code)
        if not sms_res:
            err_msg = getattr(sms_res, "message", "SMS gateway failed to deliver OTP.")
            flash(f"Failed to resend OTP: {err_msg}", "error")
            next_url = _clean_next(request.args.get("next") or request.form.get("next") or session.get("login_next"))
            if next_url:
                return redirect(url_for("auth.login", next=next_url))
            return redirect(url_for("auth.login"))
        session["login_otp"] = otp_code
        session["otp_expires_at"] = time.time() + 300
    else:
        session["login_otp"] = demo_otp

    flash("OTP resent", "success")

    next_url = _clean_next(request.args.get("next") or request.form.get("next") or session.get("login_next"))
    if next_url:
        return redirect(url_for("auth.login", next=next_url))
    return redirect(url_for("auth.login"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("login_step", None)
    session.pop("login_phone", None)
    session.pop("otp_attempts", None)
    session.pop("login_next", None)
    flash("Logged out.", "success")
    return redirect(url_for("main.index"))

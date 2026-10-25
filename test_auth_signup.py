"""Signup, email login, profile editing and password reset (sections A + E).

Every test runs against a throwaway SQLite file with ``OTP_MODE=console`` so
no SMS or email is ever sent and the dev code appears in the flash message.
"""
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from models import db, Address, OtpCode, User, UserEvent
from utils import ratelimit
from utils.passwords import password_strength

BASE_SIGNUP = {
    "name": "Asha Verma",
    "email": "asha@example.com",
    "phone": "9812345678",
    "country": "IN",
    "password": "Str0ngPass!23",
    "confirm_password": "Str0ngPass!23",
    "house_no": "12, Rose Villa",
    "street": "MG Road",
    "city": "Pune",
    "state": "Maharashtra",
    "pincode": "411001",
    "address_country": "India",
    "role": "renter",
    "terms": "on",
}


class SignupFlow(unittest.TestCase):

    def setUp(self):
        ratelimit.reset()
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "OTP_MODE": "console",
            "EMAIL_PROVIDER": "console",
            "PAYMENT_MODE": "mock",
            "SECRET_KEY": "signup-tests",
            "SQLALCHEMY_DATABASE_URI":
                "sqlite:///" + os.path.join(self.tmp, "auth.db").replace("\\", "/"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        ratelimit.reset()
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers ---------------------------------------------------------
    def _form(self, **overrides):
        data = dict(BASE_SIGNUP)
        data.update(overrides)
        return data

    def _signup(self, **overrides):
        return self.client.post("/signup", data=self._form(**overrides),
                                follow_redirects=True)

    def _user(self, email="asha@example.com"):
        db.session.expire_all()
        return User.query.filter(db.func.lower(User.email) == email).first()

    def _dev_code(self, response):
        match = re.search(rb"your code is (\d{6})", response.data)
        self.assertIsNotNone(match, "dev-mode OTP was not shown in the flash message")
        return match.group(1).decode()

    def _logout(self):
        self.client.get("/logout")

    # -- 1. the form renders every required field -------------------------
    def test_01_signup_page_renders_all_fields(self):
        resp = self.client.get("/signup")
        self.assertEqual(resp.status_code, 200)
        for field in (b'name="name"', b'name="email"', b'name="phone"',
                      b'name="country"', b'name="password"',
                      b'name="confirm_password"', b'name="house_no"',
                      b'name="street"', b'name="city"', b'name="state"',
                      b'name="pincode"', b'name="address_country"',
                      b'name="role"', b'name="terms"'):
            self.assertIn(field, resp.data, field)
        self.assertIn(b"India (+91)", resp.data)   # country-code selector

    # -- 2. a valid signup creates everything and asks for verification ---
    def test_02_valid_signup_creates_user_address_and_otp(self):
        resp = self._signup()
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Verify your phone", resp.data)

        user = self._user()
        self.assertIsNotNone(user)
        self.assertEqual(user.name, "Asha Verma")
        self.assertEqual(user.phone_e164, "+919812345678")
        self.assertEqual(user.phone, "9812345678")
        self.assertEqual(user.role, "renter")
        self.assertTrue(user.has_password)
        self.assertNotIn("Str0ngPass!23", user.password_hash)
        self.assertFalse(user.phone_verified)
        self.assertIsNotNone(user.terms_accepted_at)

        address = Address.query.filter_by(user_id=user.id, is_default=True).first()
        self.assertIsNotNone(address)
        self.assertEqual(address.city, "Pune")
        self.assertEqual(address.pincode, "411001")
        self.assertEqual(address.country, "India")

        self.assertEqual(
            UserEvent.query.filter_by(user_id=user.id, kind="signup").count(), 1)
        otp = OtpCode.query.filter_by(purpose="signup", channel="sms",
                                      target="+919812345678").first()
        self.assertIsNotNone(otp)
        self.assertEqual(len(otp.code_hash), 64)      # HMAC hexdigest, not the code
        self.assertGreater(otp.expires_at, otp.created_at)

    # -- 3. server-side validation ---------------------------------------
    def test_03_duplicate_email_rejected_case_insensitively(self):
        self._signup()
        self._logout()
        resp = self._signup(email="ASHA@Example.com", phone="9876543210")
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"already exists", resp.data)
        self.assertEqual(
            User.query.filter(db.func.lower(User.email) == "asha@example.com").count(), 1)

    def test_04_duplicate_phone_rejected(self):
        self._signup()
        self._logout()
        resp = self._signup(email="other@example.com")
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"phone number already exists", resp.data)

    def test_05_weak_password_and_mismatch_rejected(self):
        resp = self._signup(password="short", confirm_password="short")
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"at least 8 characters", resp.data)
        resp = self._signup(password="Str0ngPass!23",
                            confirm_password="Different!23")
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"Passwords do not match", resp.data)
        self.assertTrue(password_strength("Str0ngPass!23")["ok"])
        self.assertFalse(password_strength("lowercase1")["ok"])  # 9 chars, 2 classes

    def test_06_invalid_email_and_phone_rejected(self):
        resp = self._signup(email="not-an-email")
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"valid email", resp.data)
        resp = self._signup(phone="12345")
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"valid mobile number", resp.data)

    def test_07_terms_are_required(self):
        form = self._form()
        form.pop("terms")
        resp = self.client.post("/signup", data=form)
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"accept the terms", resp.data)

    # -- 4. international numbers get E.164 storage ----------------------
    def test_08_international_signup_stores_e164(self):
        resp = self._signup(country="US", phone="6502530000",
                            address_country="United States")
        self.assertEqual(resp.status_code, 200)
        user = self._user()
        self.assertIsNotNone(user)
        self.assertEqual(user.phone_e164, "+16502530000")
        self.assertEqual(user.phone, "+16502530000")   # legacy key for non-India

    # -- 5. email + password login ---------------------------------------
    def test_09_email_login_and_wrong_password(self):
        self._signup()
        self._logout()
        bad = self.client.post("/login", data={"email": "asha@example.com",
                                               "password": "WrongPass1!"},
                               follow_redirects=True)
        self.assertIn(b"Invalid email or password", bad.data)
        good = self.client.post("/login", data={"email": "asha@example.com",
                                                "password": "Str0ngPass!23"},
                                follow_redirects=True)
        self.assertEqual(good.status_code, 200)
        self.assertIn(b"Welcome, Asha Verma", good.data)
        with self.client.session_transaction() as sess:
            self.assertIn("_user_id", sess)
        login_events = UserEvent.query.filter_by(kind="login").count()
        self.assertGreaterEqual(login_events, 1)

    # -- 6. profile edit + verification status ---------------------------
    def test_10_profile_edit_updates_address_and_verification(self):
        self._signup()
        resp = self.client.post("/profile", data={
            "action": "profile",
            "name": "Asha V.",
            "email": "asha@example.com",
            "house_no": "99 Lake Road",
            "street": "Kalyani Nagar",
            "city": "Pune",
            "state": "Maharashtra",
            "pincode": "411006",
            "country": "India",
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Verification status", resp.data)
        user = self._user()
        self.assertEqual(user.name, "Asha V.")
        self.assertTrue(user.address_verified)
        address = Address.query.filter_by(user_id=user.id, is_default=True).first()
        self.assertEqual(address.house_no, "99 Lake Road")
        self.assertEqual(address.pincode, "411006")
        self.assertGreaterEqual(
            UserEvent.query.filter_by(kind="profile_updated").count(), 1)

    # -- 7. forgot password via the email OTP ----------------------------
    def test_11_forgot_password_email_otp_then_login(self):
        self._signup()
        self._logout()
        resp = self.client.post("/forgot-password",
                                data={"identifier": "asha@example.com"},
                                follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Set a new password", resp.data)
        code = self._dev_code(resp)

        done = self.client.post("/reset-password", data={
            "otp": code, "password": "NewPass!456",
            "confirm_password": "NewPass!456",
        }, follow_redirects=True)
        self.assertEqual(done.status_code, 200)
        self.assertIn(b"Password updated", done.data)

        self._logout()
        relogin = self.client.post("/login", data={"email": "asha@example.com",
                                                   "password": "NewPass!456"},
                                   follow_redirects=True)
        self.assertIn(b"Welcome, Asha Verma", relogin.data)
        self.assertGreaterEqual(
            UserEvent.query.filter_by(kind="password_reset").count(), 1)


if __name__ == "__main__":
    unittest.main()

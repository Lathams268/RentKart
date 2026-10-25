"""OTP lifecycle rules (section B + E).

Covers expiry, wrong-attempt lock, resend cooldown, "a resend supersedes the
old code", the 5-sends-per-hour cap, and the HTTP change-number /
alternate-number flows (including "the account number changes only after the
new number is verified").
"""
import os
import re
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from models import db, OtpCode, User, UserEvent
from utils import otp_service, ratelimit
from utils.otp import hash_otp


class OtpRules(unittest.TestCase):
    TARGET = "+919812345678"

    def setUp(self):
        ratelimit.reset()
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "OTP_MODE": "console",
            "EMAIL_PROVIDER": "console",
            "SECRET_KEY": "otp-tests",
            "SQLALCHEMY_DATABASE_URI":
                "sqlite:///" + os.path.join(self.tmp, "otp.db").replace("\\", "/"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.user = User(name="Otp Tester", email="otp@example.com",
                         phone="9812345678", phone_e164=self.TARGET,
                         village_or_city="Pune", role="both")
        self.user.set_password("Str0ngPass!23")
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        ratelimit.reset()
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers ---------------------------------------------------------
    def _issue(self, target=None, purpose="signup", channel="sms", **kwargs):
        return otp_service.issue_otp(
            self.user, purpose, channel, target or self.TARGET, **kwargs)

    def _row(self, target=None, purpose="signup", channel="sms"):
        return (OtpCode.query
                .filter_by(purpose=purpose, channel=channel,
                           target=target or self.TARGET)
                .order_by(OtpCode.id.desc()).first())

    def _login(self):
        return self.client.post("/login", data={
            "email": "otp@example.com", "password": "Str0ngPass!23",
        }, follow_redirects=True)

    def _dev_code(self, response):
        match = re.search(rb"your code is (\d{6})", response.data)
        self.assertIsNotNone(match, "dev-mode OTP not shown in the flash message")
        return match.group(1).decode()

    # -- 1. code is hashed, verifies once --------------------------------
    def test_01_issue_stores_hash_and_consumes_once(self):
        result = self._issue(code="246810")
        self.assertTrue(result.ok)
        row = self._row()
        self.assertIsNotNone(row)
        self.assertEqual(row.code_hash, hash_otp("246810"))
        self.assertNotEqual(row.code_hash, "246810")
        self.assertEqual(len(row.code_hash), 64)
        self.assertGreater(row.expires_at, datetime.utcnow())

        first = otp_service.verify_otp("signup", "sms", self.TARGET, "246810")
        self.assertTrue(first.ok)
        self.assertEqual(first.status, otp_service.STATUS_OK)
        self.assertIsNotNone(self._row().consumed_at)

        replay = otp_service.verify_otp("signup", "sms", self.TARGET, "246810")
        self.assertFalse(replay.ok)
        self.assertEqual(replay.status, otp_service.STATUS_MISSING)
        self.assertIn("already used", replay.message)

    # -- 2. 5 minute expiry ----------------------------------------------
    def test_02_expired_code_is_rejected(self):
        self._issue(code="111111")
        row = self._row()
        row.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
        result = otp_service.verify_otp("signup", "sms", self.TARGET, "111111")
        self.assertEqual(result.status, otp_service.STATUS_EXPIRED)
        self.assertIn("expired", result.message)

    # -- 3. five wrong attempts then a 15 minute lock ---------------------
    def test_03_wrong_attempts_lock_for_fifteen_minutes(self):
        self._issue(code="555555")
        for attempt in range(1, 5):
            result = otp_service.verify_otp("signup", "sms", self.TARGET, "000000")
            self.assertEqual(result.status, otp_service.STATUS_INVALID)
            self.assertEqual(result.remaining, 5 - attempt)
        fifth = otp_service.verify_otp("signup", "sms", self.TARGET, "000000")
        self.assertEqual(fifth.status, otp_service.STATUS_LOCKED)
        self.assertGreaterEqual(fifth.locked_seconds, 14 * 60)

        locked_row = self._row()
        self.assertIsNotNone(locked_row.locked_until)
        self.assertTrue(locked_row.is_locked())

        # Even the right code cannot get through while the lock is active.
        blocked = otp_service.verify_otp("signup", "sms", self.TARGET, "555555")
        self.assertEqual(blocked.status, otp_service.STATUS_LOCKED)

    # -- 4. 30 second resend cooldown -------------------------------------
    def test_04_resend_cooldown_is_enforced(self):
        first = self._issue(code="135790")
        self.assertTrue(first.ok)
        second = self._issue(code="246801", enforce_cooldown=True)
        self.assertFalse(second.ok)
        self.assertIn("Please wait", second.message)
        self.assertGreater(second.retry_after, 0)
        self.assertLessEqual(second.retry_after, 30)

    # -- 5. a resend invalidates the previous code ------------------------
    def test_05_resend_supersedes_previous_code(self):
        old = self._issue(code="111222")
        new = self._issue(code="333444")
        self.assertTrue(old.ok and new.ok)

        stale = otp_service.verify_otp("signup", "sms", self.TARGET, "111222")
        # The active row is the new code, so the old digits are just a wrong code.
        self.assertFalse(stale.ok)
        self.assertEqual(stale.status, otp_service.STATUS_INVALID)
        old_row = (OtpCode.query
                   .filter_by(purpose="signup", channel="sms", target=self.TARGET)
                   .order_by(OtpCode.id.asc()).first())
        self.assertIsNotNone(old_row.superseded_at)
        self.assertEqual(otp_service.latest_active("signup", "sms", self.TARGET).id,
                         self._row().id)
        fresh = otp_service.verify_otp("signup", "sms", self.TARGET, "333444")
        self.assertTrue(fresh.ok)

    # -- 6. at most five sends per hour -----------------------------------
    def test_06_max_five_sends_per_hour(self):
        target = "+919800000001"
        for index in range(5):
            result = self._issue(target=target, code=f"10000{index}")
            self.assertTrue(result.ok, f"send {index + 1} should succeed")
        sixth = self._issue(target=target, code="100009")
        self.assertFalse(sixth.ok)
        self.assertIn("Too many codes", sixth.message)
        self.assertEqual(sixth.retry_after, 60 * 60)

    # -- 7. change number: verify first, only then update the account -----
    def test_07_change_number_updates_only_after_verification(self):
        self._login()
        start = self.client.post("/verify-phone", data={
            "action": "change", "country": "IN", "new_phone": "9123456780",
        }, follow_redirects=True)
        self.assertEqual(start.status_code, 200)
        self.assertIn(b"Confirm your new number", start.data)
        new_target = "+919123456780"
        self.assertIsNotNone(self._row(target=new_target, purpose="change_phone"))
        db.session.expire_all()
        self.assertEqual(User.query.get(self.user.id).phone, "9812345678")

        wrong = self.client.post("/verify-phone", data={
            "action": "verify", "otp": "000000",
        }, follow_redirects=True)
        self.assertIn(b"Wrong code", wrong.data)
        db.session.expire_all()
        self.assertEqual(User.query.get(self.user.id).phone, "9812345678")

        code = self._dev_code(start)
        done = self.client.post("/verify-phone", data={
            "action": "verify", "otp": code,
        }, follow_redirects=True)
        self.assertEqual(done.status_code, 200)
        user = User.query.get(self.user.id)
        self.assertEqual(user.phone, "9123456780")
        self.assertEqual(user.phone_e164, new_target)
        self.assertTrue(user.phone_verified)
        event = UserEvent.query.filter_by(user_id=user.id, kind="phone_verified").first()
        self.assertIsNotNone(event)
        self.assertTrue(event.get_detail().get("changed"))

    # -- 8. alternate (secondary) phone -----------------------------------
    def test_08_alternate_phone_verification(self):
        self._login()
        start = self.client.post("/verify-phone", data={
            "action": "alternate", "country": "IN", "new_phone": "9988776655",
        }, follow_redirects=True)
        self.assertEqual(start.status_code, 200)
        code = self._dev_code(start)
        done = self.client.post("/verify-phone", data={
            "action": "verify", "otp": code,
        }, follow_redirects=True)
        self.assertEqual(done.status_code, 200)
        user = User.query.get(self.user.id)
        self.assertEqual(user.alternate_phone, "+919988776655")
        self.assertTrue(user.alternate_phone_verified)
        self.assertEqual(
            UserEvent.query.filter_by(user_id=user.id,
                                      kind="alternate_phone_verified").count(), 1)

    # -- 9. cannot take a number another account already owns -------------
    def test_09_change_number_rejects_number_owned_by_someone_else(self):
        other = User(name="Someone Else", phone="9000000001",
                     phone_e164="+919000000001", village_or_city="Mumbai")
        db.session.add(other)
        db.session.commit()
        self._login()
        resp = self.client.post("/verify-phone", data={
            "action": "change", "country": "IN", "new_phone": "9000000001",
        }, follow_redirects=True)
        self.assertIn(b"already linked to another account", resp.data)
        self.assertIsNone(
            self._row(target="+919000000001", purpose="change_phone"))


if __name__ == "__main__":
    unittest.main()

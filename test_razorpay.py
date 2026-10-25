"""Stage 5 tests – Razorpay test-mode gateway (HTTP + order creation mocked).

Signature verification uses the real HMAC algorithm so both the accept and
reject paths are exercised without any network or browser.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil, hmac, hashlib
from unittest import mock
from datetime import date, timedelta
from app import create_app
from models import db, User, Item, Booking, Payment
from utils.booking import calculate_price, booking_snapshot, generate_order_id
from utils.gateway import to_paise, verify_signature

SECRET = "rzp_test_secret_123"


class Razorpay(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True, "OTP_MODE": "demo", "PAYMENT_MODE": "razorpay",
            "RAZORPAY_KEY_ID": "rzp_test_key_abc", "RAZORPAY_KEY_SECRET": SECRET,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove(); self.ctx.pop(); shutil.rmtree(self.tmp, ignore_errors=True)

    def _login(self, phone, name="U"):
        self.client.get("/logout")
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        return self.client.post("/login", data={"otp": "1234", "name": name,
                                "village_or_city": "City"}, follow_redirects=True)

    def _mk(self, phone, name="U"):
        u = User.query.filter_by(phone=phone).first()
        if not u:
            u = User(name=name, phone=phone, village_or_city="City", lat=12.9, lng=77.5)
            db.session.add(u); db.session.commit()
        return u

    def _pending(self, renter, owner):
        item = Item(owner_id=owner.id, category="electronics", title="Cam",
                    price_per_day=100.0, deposit=500.0, late_fee_per_day=50.0,
                    delivery_available=False, cod_available=True)
        db.session.add(item); db.session.commit()
        s = date.today() + timedelta(days=2); e = s + timedelta(days=2)
        p = calculate_price(item, s, e, user=renter, delivery_method="pickup")
        b = Booking(item_id=item.id, renter_id=renter.id, start_date=s, end_date=e,
                    order_id=generate_order_id(), payment_status="pending",
                    **booking_snapshot(p), status="pending_payment")
        db.session.add(b); db.session.commit()
        return b

    def _sign(self, order_id, payment_id):
        return hmac.new(SECRET.encode(), f"{order_id}|{payment_id}".encode(),
                        hashlib.sha256).hexdigest()

    def test_01_to_paise_and_signature(self):
        self.assertEqual(to_paise(1250.50), 125050)
        sig = self._sign("order_1", "pay_1")
        self.assertTrue(verify_signature("order_1", "pay_1", sig, SECRET))
        self.assertFalse(verify_signature("order_1", "pay_1", "bad", SECRET))
        self.assertFalse(verify_signature("order_1", "pay_1", sig, ""))

    def test_02_get_creates_server_order(self):
        owner = self._mk("9000004001", "O"); renter = self._mk("9000004002", "R")
        b = self._pending(renter, owner)
        self._login(renter.phone)
        with mock.patch("utils.gateway.create_order", return_value={"id": "order_TEST"}) as m:
            resp = self.client.get(f"/bookings/{b.id}/pay")
        self.assertEqual(resp.status_code, 200)
        m.assert_called_once()
        db.session.refresh(b)
        self.assertEqual(b.razorpay_order_id, "order_TEST")
        self.assertIn(b"order_TEST", resp.data)

    def test_03_valid_signature_marks_paid(self):
        owner = self._mk("9000004011", "O"); renter = self._mk("9000004012", "R")
        b = self._pending(renter, owner)
        self._login(renter.phone)
        with mock.patch("utils.gateway.create_order", return_value={"id": "order_TEST"}):
            self.client.get(f"/bookings/{b.id}/pay")
        sig = self._sign("order_TEST", "pay_OK")
        resp = self.client.post(f"/bookings/{b.id}/pay", data={
            "method": "upi", "razorpay_order_id": "order_TEST",
            "razorpay_payment_id": "pay_OK", "razorpay_signature": sig,
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        db.session.refresh(b)
        self.assertEqual(b.status, "requested")
        self.assertEqual(b.payment_status, "paid")
        p = Payment.query.filter_by(booking_id=b.id, status="paid").first()
        self.assertIsNotNone(p)
        self.assertEqual(p.provider, "razorpay")
        self.assertEqual(p.provider_payment_id, "pay_OK")

    def test_04_invalid_signature_fails_and_keeps_pending(self):
        owner = self._mk("9000004021", "O"); renter = self._mk("9000004022", "R")
        b = self._pending(renter, owner)
        self._login(renter.phone)
        with mock.patch("utils.gateway.create_order", return_value={"id": "order_TEST"}):
            self.client.get(f"/bookings/{b.id}/pay")
        resp = self.client.post(f"/bookings/{b.id}/pay", data={
            "method": "upi", "razorpay_order_id": "order_TEST",
            "razorpay_payment_id": "pay_X", "razorpay_signature": "tampered",
        }, follow_redirects=True)
        self.assertIn(b"signature check failed", resp.data)
        db.session.refresh(b)
        self.assertEqual(b.status, "pending_payment")
        self.assertEqual(Payment.query.filter_by(booking_id=b.id, status="paid").count(), 0)
        self.assertEqual(Payment.query.filter_by(booking_id=b.id, status="failed").count(), 1)

    def test_05_missing_keys_falls_back_to_mock(self):
        app2 = create_app({
            "TESTING": True, "OTP_MODE": "demo", "PAYMENT_MODE": "razorpay",
            "RAZORPAY_KEY_ID": "", "RAZORPAY_KEY_SECRET": "",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test2.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads2"),
        })
        ctx = app2.app_context(); ctx.push(); db.create_all()
        owner = User(name="O", phone="9000004091", village_or_city="C", lat=1.0, lng=1.0)
        renter = User(name="R", phone="9000004092", village_or_city="C", lat=1.0, lng=1.0)
        db.session.add_all([owner, renter]); db.session.commit()
        item = Item(owner_id=owner.id, category="electronics", title="Cam",
                    price_per_day=100.0, deposit=500.0, late_fee_per_day=50.0, cod_available=True)
        db.session.add(item); db.session.commit()
        s = date.today() + timedelta(days=2); e = s + timedelta(days=2)
        p = calculate_price(item, s, e, user=renter, delivery_method="pickup")
        b = Booking(item_id=item.id, renter_id=renter.id, start_date=s, end_date=e,
                    order_id=generate_order_id(), payment_status="pending",
                    **booking_snapshot(p), status="pending_payment")
        db.session.add(b); db.session.commit()
        c2 = app2.test_client()
        c2.get("/logout")
        c2.post("/login", data={"phone": renter.phone}, follow_redirects=True)
        c2.post("/login", data={"otp": "1234", "name": "R", "village_or_city": "C"}, follow_redirects=True)
        # No create_order call needed: mock banner is shown because it fell back.
        resp = c2.get(f"/bookings/{b.id}/pay")
        self.assertIn(b"Demo mode", resp.data)
        ctx.pop()


if __name__ == "__main__":
    unittest.main(verbosity=2)

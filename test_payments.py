"""Stage 3 tests – mock gateway payment page with retry, idempotency and safety."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from datetime import date, datetime, timedelta
from app import create_app
from models import db, User, Item, Booking, Payment
from utils.booking import calculate_price, booking_snapshot, generate_order_id


class Payments(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True, "OTP_MODE": "demo", "PAYMENT_MODE": "mock",
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

    def _item(self, owner, cod=True):
        it = Item(owner_id=owner.id, category="electronics", title="Cam",
                  price_per_day=100.0, deposit=500.0, late_fee_per_day=50.0,
                  delivery_available=False, cod_available=cod)
        db.session.add(it); db.session.commit()
        return it

    def _pending(self, renter, item, expires_min=15, delivery="pickup"):
        s = date.today() + timedelta(days=2); e = s + timedelta(days=2)
        p = calculate_price(item, s, e, user=renter, delivery_method=delivery)
        b = Booking(item_id=item.id, renter_id=renter.id, start_date=s, end_date=e,
                    order_id=generate_order_id(),
                    payment_expires_at=datetime.utcnow() + timedelta(minutes=expires_min),
                    payment_status="pending", **booking_snapshot(p), status="pending_payment")
        db.session.add(b); db.session.commit()
        return b

    def test_01_success_moves_to_requested_and_one_paid_payment(self):
        owner = self._mk("9000002001", "O"); renter = self._mk("9000002002", "R")
        item = self._item(owner); b = self._pending(renter, item)
        self._login(renter.phone)
        resp = self.client.post(f"/bookings/{b.id}/pay",
                                data={"method": "upi", "outcome": "success"},
                                follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        db.session.refresh(b)
        self.assertEqual(b.status, "requested")
        self.assertEqual(b.payment_status, "paid")
        self.assertIsNone(b.payment_expires_at)
        self.assertEqual(Payment.query.filter_by(booking_id=b.id, status="paid").count(), 1)

    def test_02_failure_keeps_pending_and_allows_retry(self):
        owner = self._mk("9000002011", "O"); renter = self._mk("9000002012", "R")
        item = self._item(owner); b = self._pending(renter, item)
        self._login(renter.phone)
        resp = self.client.post(f"/bookings/{b.id}/pay",
                                data={"method": "upi", "outcome": "declined"},
                                follow_redirects=True)
        self.assertIn(b"bank declined", resp.data)
        db.session.refresh(b)
        self.assertEqual(b.status, "pending_payment")
        self.assertEqual(Payment.query.filter_by(booking_id=b.id, status="failed").count(), 1)
        self.assertEqual(Payment.query.filter_by(booking_id=b.id, status="paid").count(), 0)

    def test_03_success_after_failed_attempt(self):
        owner = self._mk("9000002021", "O"); renter = self._mk("9000002022", "R")
        item = self._item(owner); b = self._pending(renter, item)
        self._login(renter.phone)
        self.client.post(f"/bookings/{b.id}/pay", data={"method": "upi", "outcome": "timeout"})
        self.client.post(f"/bookings/{b.id}/pay", data={"method": "upi", "outcome": "success"},
                         follow_redirects=True)
        db.session.refresh(b)
        self.assertEqual(b.status, "requested")
        self.assertEqual(Payment.query.filter_by(booking_id=b.id, status="paid").count(), 1)
        self.assertEqual(Payment.query.filter_by(booking_id=b.id, status="failed").count(), 1)

    def test_04_double_submit_is_idempotent(self):
        owner = self._mk("9000002031", "O"); renter = self._mk("9000002032", "R")
        item = self._item(owner); b = self._pending(renter, item)
        self._login(renter.phone)
        self.client.post(f"/bookings/{b.id}/pay", data={"method": "upi", "outcome": "success"})
        self.client.post(f"/bookings/{b.id}/pay", data={"method": "upi", "outcome": "success"},
                         follow_redirects=True)
        self.assertEqual(Payment.query.filter_by(booking_id=b.id, status="paid").count(), 1)

    def test_05_cash_refused_when_item_does_not_accept(self):
        owner = self._mk("9000002041", "O"); renter = self._mk("9000002042", "R")
        item = self._item(owner, cod=False); b = self._pending(renter, item)
        self._login(renter.phone)
        resp = self.client.post(f"/bookings/{b.id}/pay", data={"method": "cash", "outcome": "success"},
                                follow_redirects=True)
        db.session.refresh(b)
        self.assertEqual(b.status, "pending_payment")
        self.assertEqual(Payment.query.filter_by(booking_id=b.id, status="paid").count(), 0)

    def test_06_different_user_gets_403(self):
        owner = self._mk("9000002051", "O"); renter = self._mk("9000002052", "R")
        other = self._mk("9000002053", "X")
        item = self._item(owner); b = self._pending(renter, item)
        self._login(other.phone)
        resp = self.client.get(f"/bookings/{b.id}/pay")
        self.assertEqual(resp.status_code, 403)

    def test_07_expired_booking_is_cancelled(self):
        owner = self._mk("9000002061", "O"); renter = self._mk("9000002062", "R")
        item = self._item(owner); b = self._pending(renter, item, expires_min=-1)
        self._login(renter.phone)
        resp = self.client.get(f"/bookings/{b.id}/pay", follow_redirects=True)
        self.assertIn(b"Payment time expired", resp.data)
        db.session.refresh(b)
        self.assertEqual(b.status, "cancelled")

    def test_08_no_card_data_in_db(self):
        owner = self._mk("9000002071", "O"); renter = self._mk("9000002072", "R")
        item = self._item(owner); b = self._pending(renter, item)
        self._login(renter.phone)
        card = "4111111111111111"; cvv = "123"
        self.client.post(f"/bookings/{b.id}/pay",
                         data={"method": "debit_card", "outcome": "success",
                               "card_number": card, "cvv": cvv, "upi_id": "r@upi"},
                         follow_redirects=True)
        # Dump every row and confirm the card number / cvv never appear.
        blob = ""
        for p in Payment.query.all():
            blob += str({c.name: getattr(p, c.name) for c in p.__table__.columns})
        for bo in Booking.query.all():
            blob += str({c.name: getattr(bo, c.name) for c in bo.__table__.columns})
        self.assertNotIn(card, blob)
        self.assertNotIn(cvv, blob)


if __name__ == "__main__":
    unittest.main(verbosity=2)

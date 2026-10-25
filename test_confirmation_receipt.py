"""Stage 4 tests – confirmation, receipt, refunds on reject/cancel."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from datetime import date, datetime, timedelta
from app import create_app
from models import db, User, Item, Booking, Payment
from utils.booking import calculate_price, booking_snapshot, generate_order_id
from utils.money import inr


class ConfirmationReceipt(unittest.TestCase):

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

    def _item(self, owner):
        it = Item(owner_id=owner.id, category="electronics", title="Cam",
                  price_per_day=100.0, deposit=500.0, late_fee_per_day=50.0,
                  delivery_available=False, cod_available=True)
        db.session.add(it); db.session.commit()
        return it

    def _paid(self, renter, item, method="upi"):
        """Create a requested booking that has already been paid (Payment row)."""
        s = date.today() + timedelta(days=2); e = s + timedelta(days=2)
        p = calculate_price(item, s, e, user=renter, delivery_method="pickup")
        b = Booking(item_id=item.id, renter_id=renter.id, start_date=s, end_date=e,
                    order_id=generate_order_id(), payment_method=method,
                    payment_status="paid", **booking_snapshot(p), status="requested")
        db.session.add(b); db.session.commit()
        pay = Payment(booking_id=b.id, order_id=b.order_id, attempt_no=1, method=method,
                      amount=p["total_payable"], status="paid", provider="mock",
                      paid_at=datetime.utcnow())
        db.session.add(pay); db.session.commit()
        return b

    def test_01_confirmation_shows_order_id_and_dates(self):
        owner = self._mk("9000003001", "O"); renter = self._mk("9000003002", "R")
        item = self._item(owner); b = self._paid(renter, item)
        self._login(renter.phone)
        resp = self.client.get(f"/bookings/{b.id}/confirmation")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8")
        self.assertIn(b.order_id, body)
        self.assertIn(str(b.start_date), body)
        self.assertIn(str(b.end_date), body)
        self.assertIn("Waiting for owner approval", body)

    def test_02_receipt_shows_snapshot_amounts(self):
        owner = self._mk("9000003011", "O"); renter = self._mk("9000003012", "R")
        item = self._item(owner); b = self._paid(renter, item)
        self._login(renter.phone)
        resp = self.client.get(f"/bookings/{b.id}/receipt")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8")
        # Every price line comes from the booking snapshot.
        for value in [b.total_rent, b.deposit, b.delivery_charge or 0,
                      b.platform_fee or 0, b.total_payable]:
            self.assertIn(inr(value), body)
        self.assertIn(b.order_id, body)

    def test_03_third_user_gets_403_on_both(self):
        owner = self._mk("9000003021", "O"); renter = self._mk("9000003022", "R")
        other = self._mk("9000003023", "X")
        item = self._item(owner); b = self._paid(renter, item)
        self._login(other.phone)
        self.assertEqual(self.client.get(f"/bookings/{b.id}/confirmation").status_code, 403)
        self.assertEqual(self.client.get(f"/bookings/{b.id}/receipt").status_code, 403)

    def test_04_owner_rejection_creates_full_refund(self):
        owner = self._mk("9000003031", "O"); renter = self._mk("9000003032", "R")
        item = self._item(owner); b = self._paid(renter, item)
        amount = b.total_payable
        self._login(owner.phone, "Owner")
        resp = self.client.post(f"/bookings/{b.id}/reject", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        db.session.refresh(b)
        paid = Payment.query.filter_by(booking_id=b.id, status="paid").count()
        refunded = Payment.query.filter_by(booking_id=b.id, status="refunded").first()
        self.assertEqual(paid, 0)
        self.assertIsNotNone(refunded)
        self.assertEqual(refunded.amount, amount)
        self.assertEqual(b.payment_status, "refunded")
        self.assertEqual(b.status, "rejected")

    def test_05_renter_cancellation_before_approval_refunds(self):
        owner = self._mk("9000003041", "O"); renter = self._mk("9000003042", "R")
        item = self._item(owner); b = self._paid(renter, item)
        self._login(renter.phone)
        resp = self.client.post(f"/bookings/{b.id}/cancel", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        db.session.refresh(b)
        self.assertEqual(b.status, "cancelled")
        self.assertEqual(b.payment_status, "refunded")
        self.assertEqual(Payment.query.filter_by(booking_id=b.id, status="refunded").count(), 1)

    def test_06_cash_cancel_has_nothing_to_refund(self):
        owner = self._mk("9000003051", "O"); renter = self._mk("9000003052", "R")
        item = self._item(owner); b = self._paid(renter, item, method="cash")
        b.payment_status = "pay_on_pickup"; db.session.commit()
        # Flip the Payment row to cash too.
        p = Payment.query.filter_by(booking_id=b.id).first(); p.method = "cash"; p.status = "paid"
        db.session.commit()
        self._login(renter.phone)
        self.client.post(f"/bookings/{b.id}/cancel", follow_redirects=True)
        db.session.refresh(b)
        self.assertEqual(b.status, "cancelled")
        # Cash on pickup: nothing was charged, so nothing refunded.
        self.assertEqual(b.payment_status, "pay_on_pickup")
        self.assertEqual(Payment.query.filter_by(booking_id=b.id, status="refunded").count(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

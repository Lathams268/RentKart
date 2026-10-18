"""Stage 2/3 tests – address required at checkout, snapshot, rounding, payment page."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from datetime import date, datetime, timedelta
from app import create_app
from models import db, User, Item, Booking, Address, Payment
from utils.booking import calculate_price, booking_snapshot, generate_order_id


class PaymentDetails(unittest.TestCase):

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

    def _item(self, owner, delivery=False, charge=0.0, price=100.0, deposit=500.0, late=50.0):
        it = Item(owner_id=owner.id, category="electronics", title="Drill",
                  price_per_day=price, deposit=deposit, late_fee_per_day=late,
                  delivery_available=delivery, delivery_charge=charge, cod_available=True)
        db.session.add(it); db.session.commit()
        return it

    def _addr(self, user, city="Bengaluru", **kw):
        a = Address(user_id=user.id, label="Home", full_name=user.name, phone=user.phone,
                    house_no=kw.get("house_no", "1"), street=kw.get("street", "Street"),
                    city=city, state="Karnataka", pincode="560001", is_default=True)
        db.session.add(a); db.session.commit()
        return a

    def _dates(self):
        s = date.today() + timedelta(days=2)
        return s, s + timedelta(days=4)

    # ---- TEST 2: address required ----
    def test_01_checkout_refuses_no_address(self):
        owner = self._mk("9000004001", "O"); renter = self._mk("9000004002", "R")
        item = self._item(owner); self._login(renter.phone)
        s, e = self._dates()
        self.client.post(f"/items/{item.id}/checkout", data={
            "start_date": s.isoformat(), "end_date": e.isoformat(),
            "delivery": "pickup", "agree": "1"}, follow_redirects=True)
        self.assertEqual(Booking.query.filter_by(status="pending_payment").count(), 0)

    def test_02_checkout_refuses_others_address(self):
        owner = self._mk("9000004011", "O"); renter = self._mk("9000004012", "R")
        stranger = self._mk("9000004013", "S")
        item = self._item(owner); self._login(renter.phone)
        foreign = self._addr(stranger)
        s, e = self._dates()
        self.client.post(f"/items/{item.id}/checkout", data={
            "start_date": s.isoformat(), "end_date": e.isoformat(),
            "delivery": "pickup", "agree": "1", "address_id": foreign.id},
            follow_redirects=True)
        self.assertEqual(Booking.query.filter_by(status="pending_payment").count(), 0)

    def test_03_snapshot_keeps_old_address_after_edit(self):
        owner = self._mk("9000004021", "O"); renter = self._mk("9000004022", "R")
        item = self._item(owner); self._login(renter.phone)
        a = self._addr(renter, city="Bengaluru")
        s, e = self._dates()
        self.client.post(f"/items/{item.id}/checkout", data={
            "start_date": s.isoformat(), "end_date": e.isoformat(),
            "delivery": "pickup", "agree": "1", "address_id": a.id},
            follow_redirects=True)
        b = Booking.query.filter_by(renter_id=renter.id, status="pending_payment").first()
        self.assertIsNotNone(b)
        self.assertEqual(b.ship_city, "Bengaluru")
        self.assertEqual(b.address_id, a.id)
        # Editing the saved address must NOT change the booking snapshot.
        a.city = "Mysuru"; db.session.commit()
        db.session.refresh(b)
        self.assertEqual(b.ship_city, "Bengaluru")

    # ---- TEST 3: delivery + rounding ----
    def test_04_delivery_refused_without_flag(self):
        owner = self._mk("9000004031", "O"); renter = self._mk("9000004032", "R")
        item = self._item(owner, delivery=False, charge=60.0)
        self._login(renter.phone); a = self._addr(renter)
        s, e = self._dates()
        self.client.post(f"/items/{item.id}/checkout", data={
            "start_date": s.isoformat(), "end_date": e.isoformat(),
            "delivery": "delivery", "agree": "1", "address_id": a.id},
            follow_redirects=True)
        b = Booking.query.filter_by(renter_id=renter.id, status="pending_payment").first()
        self.assertEqual(b.delivery_method, "pickup")
        self.assertEqual(b.delivery_charge, 0.0)

    def test_05_delivery_charge_rounded_whole(self):
        owner = self._mk("9000004041", "O"); renter = self._mk("9000004042", "R")
        item = self._item(owner, delivery=True, charge=45.5)
        self._login(renter.phone); a = self._addr(renter)
        s, e = self._dates()
        self.client.post(f"/items/{item.id}/checkout", data={
            "start_date": s.isoformat(), "end_date": e.isoformat(),
            "delivery": "delivery", "agree": "1", "address_id": a.id},
            follow_redirects=True)
        b = Booking.query.filter_by(renter_id=renter.id, status="pending_payment").first()
        self.assertEqual(b.delivery_charge, 46.0)      # 45.5 -> 46, whole rupees
        self.assertEqual(b.delivery_charge % 1, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

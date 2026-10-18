"""Stage 2 tests – order summary checkout page and pending_payment booking."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from datetime import date, timedelta
from app import create_app
from models import db, User, Item, Booking
from utils.booking import calculate_price


class CheckoutPage(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "OTP_MODE": "demo",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _login(self, phone, name="U"):
        self.client.get("/logout")
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        return self.client.post("/login", data={"otp": "1234", "name": name,
                                "village_or_city": "City"}, follow_redirects=True)

    def _mk(self, phone, name):
        u = User.query.filter_by(phone=phone).first()
        if not u:
            u = User(name=name, phone=phone, village_or_city="City", lat=12.9, lng=77.5)
            db.session.add(u); db.session.commit()
        return u

    def _item(self, owner, delivery=False, charge=0.0, price=100.0, deposit=500.0):
        it = Item(owner_id=owner.id, category="electronics", title="Drill",
                  price_per_day=price, deposit=deposit, late_fee_per_day=50.0,
                  delivery_available=delivery, delivery_charge=charge, cod_available=True)
        db.session.add(it); db.session.commit()
        return it

    def _dates(self):
        s = date.today() + timedelta(days=2)
        return s, s + timedelta(days=4)

    def test_01_summary_shows_all_lines_and_total(self):
        owner = self._mk("9000001001", "Owner")
        renter = self._mk("9000001002", "Renter")
        item = self._item(owner, delivery=True, charge=60.0)
        self._login(renter.phone)
        s, e = self._dates()
        resp = self.client.get(f"/items/{item.id}/checkout?start={s}&end={e}&delivery=delivery")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8")
        for token in ["Rent", "Security deposit", "Delivery charge", "Platform fee", "TOTAL PAYABLE",
                      "What is refundable", "Possible charges later", "No hidden charges",
                      "I agree to the rental terms"]:
            self.assertIn(token, body)
        p = calculate_price(item, s, e, user=renter, delivery_method="delivery")
        self.assertIn(f"{p['total_payable']:,.2f}".rstrip("0").rstrip("."), body.replace("₹", ""))

    def test_02_invalid_date_refused(self):
        owner = self._mk("9000001011", "Owner")
        renter = self._mk("9000001012", "Renter")
        item = self._item(owner)
        self._login(renter.phone)
        past = date.today() - timedelta(days=3)
        resp = self.client.get(f"/items/{item.id}/checkout?start={past}&end={past}", follow_redirects=True)
        self.assertIn(b"past", resp.data)
        self.assertEqual(Booking.query.count(), 0)

    def test_03_owner_cannot_open_checkout(self):
        owner = self._mk("9000001021", "Owner")
        item = self._item(owner)
        self._login(owner.phone, "Owner")
        s, e = self._dates()
        resp = self.client.get(f"/items/{item.id}/checkout?start={s}&end={e}", follow_redirects=True)
        self.assertIn(b"cannot book your own item", resp.data)

    def test_04_tampered_total_is_ignored(self):
        owner = self._mk("9000001031", "Owner")
        renter = self._mk("9000001032", "Renter")
        item = self._item(owner, price=150.0, deposit=300.0)
        self._login(renter.phone)
        s, e = self._dates()
        p = calculate_price(item, s, e, user=renter, delivery_method="pickup")
        resp = self.client.post(f"/items/{item.id}/checkout", data={
            "start_date": s.isoformat(), "end_date": e.isoformat(),
            "delivery": "pickup", "agree": "1",
            "total_payable": "1", "deposit": "1", "platform_fee": "0",
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        b = Booking.query.filter_by(renter_id=renter.id, status="pending_payment").first()
        self.assertIsNotNone(b)
        self.assertEqual(b.total_payable, p["total_payable"])
        self.assertNotEqual(b.total_payable, 1.0)

    def test_05_duplicate_submit_reuses_pending_booking(self):
        owner = self._mk("9000001041", "Owner")
        renter = self._mk("9000001042", "Renter")
        item = self._item(owner)
        self._login(renter.phone)
        s, e = self._dates()
        data = {"start_date": s.isoformat(), "end_date": e.isoformat(),
                "delivery": "pickup", "agree": "1"}
        self.client.post(f"/items/{item.id}/checkout", data=data, follow_redirects=True)
        self.client.post(f"/items/{item.id}/checkout", data=data, follow_redirects=True)
        pending = Booking.query.filter_by(renter_id=renter.id, item_id=item.id,
                                          status="pending_payment").all()
        self.assertEqual(len(pending), 1)
        self.assertTrue(pending[0].order_id.startswith("RK-"))

    def test_06_api_checkout_price_is_server_side(self):
        owner = self._mk("9000001051", "Owner")
        renter = self._mk("9000001052", "Renter")
        item = self._item(owner, delivery=True, charge=60.0)
        self._login(renter.phone)
        s, e = self._dates()
        resp = self.client.get(f"/api/checkout-price?item_id={item.id}&start={s}&end={e}&delivery=delivery")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        p = calculate_price(item, s, e, user=renter, delivery_method="delivery")
        self.assertEqual(data["total_payable"], p["total_payable"])
        self.assertEqual(data["delivery_charge"], 60.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

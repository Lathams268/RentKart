"""Stage 1 (clothes redesign) – discount_percent, effective price, CLOTH_TABS.

Covers: 10% off Rs 500 shows Rs 450 in the card, the checkout total and the
receipt; old items without a discount keep their price; every clothes tab
returns the right genders; Unisex / missing gender appear in Men AND Women.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from datetime import date, timedelta

from app import create_app
from models import db, User, Item, Booking, Address, Payment
from utils.booking import calculate_price, effective_price, booking_snapshot, generate_order_id
from utils.filters import cloth_tab_filter, rating_summary
from utils.money import inr
from datetime import datetime


class ClothesDataTest(unittest.TestCase):

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

    # --- helpers ---
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

    def _item(self, owner, price=500.0, discount=None, gender="Women", title="Silk Saree"):
        it = Item(owner_id=owner.id, category="clothes", title=title,
                  price_per_day=price, deposit=1000.0, late_fee_per_day=0.0,
                  delivery_available=False, cod_available=True,
                  discount_percent=discount)
        it.set_attributes({"gender": gender, "clothing_type": "Saree"})
        db.session.add(it); db.session.commit()
        return it

    def _addr(self, user):
        a = Address(user_id=user.id, label="Home", full_name=user.name, phone=user.phone,
                    house_no="1", street="Street", city="City", state="Karnataka",
                    pincode="560001", is_default=True)
        db.session.add(a); db.session.commit()
        return a

    def _dates(self):
        s = date.today() + timedelta(days=2)
        return s, s + timedelta(days=2)  # 3 days

    # --- effective price ---
    def test_01_effective_price_10_percent_on_500(self):
        owner = self._mk("9100000001", "Owner")
        it = self._item(owner, price=500.0, discount=10)
        self.assertEqual(effective_price(it), 450.0)

    def test_02_no_discount_keeps_original_price(self):
        owner = self._mk("9100000002", "Owner")
        it = self._item(owner, price=500.0, discount=None)
        self.assertEqual(effective_price(it), 500.0)
        # whole-rupee rounding with a discount
        it2 = self._item(owner, price=499.0, discount=20, title="Kurti")
        self.assertEqual(effective_price(it2), 399.0)  # 499*0.8 = 399.2 -> 399

    def test_03_checkout_total_uses_effective_price(self):
        owner = self._mk("9100000003", "Owner")
        renter = self._mk("9100000004", "Renter")
        it = self._item(owner, price=500.0, discount=10)
        s, e = self._dates()  # 3 days
        p = calculate_price(it, s, e, user=None, delivery_method="pickup")
        self.assertEqual(p["price_per_day"], 450.0)      # effective
        self.assertEqual(p["price_original"], 500.0)     # snapshot of original
        self.assertEqual(p["rent"], 1350.0)             # 450 * 3

    def test_04_card_shows_effective_price(self):
        owner = self._mk("9100000005", "Owner")
        self._item(owner, price=500.0, discount=10, title="Discount Saree")
        resp = self.client.get("/browse?category=clothes")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("₹450", html)

    def test_05_checkout_page_shows_effective_price(self):
        owner = self._mk("9100000006", "Owner")
        renter = self._mk("9100000007", "Renter")
        it = self._item(owner, price=500.0, discount=10)
        self._login(renter.phone)
        s, e = self._dates()
        resp = self.client.get(f"/items/{it.id}/checkout?start={s}&end={e}&delivery=pickup")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8")
        self.assertIn("₹450", body)

    def test_06_receipt_snapshot_and_amounts(self):
        owner = self._mk("9100000008", "Owner")
        renter = self._mk("9100000009", "Renter")
        it = self._item(owner, price=500.0, discount=10)
        s, e = self._dates()
        p = calculate_price(it, s, e, user=renter, delivery_method="pickup")
        b = Booking(item_id=it.id, renter_id=renter.id, start_date=s, end_date=e,
                    order_id=generate_order_id(), payment_method="upi",
                    payment_status="paid", **booking_snapshot(p), status="requested")
        db.session.add(b); db.session.commit()
        # Snapshots store both the effective per-day price and the original.
        self.assertEqual(b.price_per_day, 450.0)
        self.assertEqual(b.price_original, 500.0)
        self.assertEqual(b.total_rent, 1350.0)
        pay = Payment(booking_id=b.id, order_id=b.order_id, attempt_no=1, method="upi",
                      amount=p["total_payable"], status="paid", provider="mock",
                      paid_at=datetime.utcnow())
        db.session.add(pay); db.session.commit()
        self._login(renter.phone)
        resp = self.client.get(f"/bookings/{b.id}/receipt")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8")
        self.assertIn(inr(b.total_rent), body)  # 1350 from effective price

    # --- tabs ---
    def _gendered(self, owner, gender):
        return self._item(owner, gender=gender, title=f"{gender} Item")

    def test_07_tab_men_returns_men(self):
        owner = self._mk("9100000010", "Owner")
        items = [self._gendered(owner, g) for g in ["Men", "Women", "Boys", "Girls", "Kids", "Unisex"]]
        men = cloth_tab_filter(items, "men")
        genders = {i.get_attributes()["gender"] for i in men}
        self.assertEqual(genders, {"Men", "Unisex"})

    def test_08_tab_women_returns_women(self):
        owner = self._mk("9100000011", "Owner")
        items = [self._gendered(owner, g) for g in ["Men", "Women", "Boys", "Girls", "Kids", "Unisex"]]
        women = cloth_tab_filter(items, "women")
        genders = {i.get_attributes()["gender"] for i in women}
        self.assertEqual(genders, {"Women", "Unisex"})

    def test_09_tab_children_returns_boys_girls_kids(self):
        owner = self._mk("9100000012", "Owner")
        items = [self._gendered(owner, g) for g in ["Men", "Women", "Boys", "Girls", "Kids", "Unisex"]]
        kids = cloth_tab_filter(items, "children")
        genders = {i.get_attributes()["gender"] for i in kids}
        self.assertEqual(genders, {"Boys", "Girls", "Kids"})

    def test_10_unisex_appears_in_men_and_women_not_children(self):
        owner = self._mk("9100000013", "Owner")
        unisex = self._gendered(owner, "Unisex")
        items = [unisex]
        self.assertIn(unisex, cloth_tab_filter(items, "men"))
        self.assertIn(unisex, cloth_tab_filter(items, "women"))
        self.assertNotIn(unisex, cloth_tab_filter(items, "children"))

    def test_11_missing_gender_in_men_and_women(self):
        owner = self._mk("9100000014", "Owner")
        it = Item(owner_id=owner.id, category="clothes", title="No gender",
                  price_per_day=200.0, deposit=500.0)
        it.set_attributes({})
        db.session.add(it); db.session.commit()
        items = [it]
        self.assertIn(it, cloth_tab_filter(items, "men"))
        self.assertIn(it, cloth_tab_filter(items, "women"))
        self.assertNotIn(it, cloth_tab_filter(items, "children"))

    def test_12_rating_summary_none_when_no_reviews(self):
        owner = self._mk("9100000015", "Owner")
        it = self._gendered(owner, "Women")
        self.assertIsNone(rating_summary(it))


if __name__ == "__main__":
    unittest.main(verbosity=2)

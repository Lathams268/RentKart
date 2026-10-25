"""Stage 1 tests – single server-side pricing function and Rupee formatting."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from datetime import date, timedelta
from decimal import Decimal
from app import create_app
from models import db, User, Item
from utils.booking import calculate_price
from utils.money import inr


class CheckoutPricing(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
            "OTP_MODE": "demo",
        })
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _user(self, phone="9000000101"):
        u = User(name="R", phone=phone, village_or_city="C", lat=12.9, lng=77.5)
        db.session.add(u); db.session.commit()
        return u

    def _item(self, owner, price=100.0, deposit=500.0, delivery_available=False,
              delivery_charge=0.0, late_fee=50.0):
        it = Item(owner_id=owner.id, category="electronics", title="T",
                  price_per_day=price, deposit=deposit, late_fee_per_day=late_fee,
                  delivery_available=delivery_available, delivery_charge=delivery_charge)
        db.session.add(it); db.session.commit()
        return it

    def test_01_exact_total_3_days_delivery_fee(self):
        # fee percent 2 for this test
        self.app.config["RENTER_FEE_PERCENT"] = 2
        owner = self._user("9000000111")
        renter = self._user("9000000112")  # new user -> trust score 50 -> Trusted (0.8)
        item = self._item(owner, price=100.0, deposit=500.0,
                          delivery_available=True, delivery_charge=60.0)
        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=2)  # 3 days
        p = calculate_price(item, start, end, user=renter, delivery_method="delivery")

        self.assertEqual(p["days"], 3)
        self.assertEqual(p["rent"], 300.0)
        self.assertEqual(p["deposit_original"], 500.0)
        self.assertEqual(p["deposit"], 400.0)          # 20% trust discount
        self.assertEqual(p["trust_discount"], 100.0)
        self.assertEqual(p["delivery_charge"], 60.0)
        self.assertEqual(p["platform_fee"], 6.0)        # 2% of 300
        self.assertEqual(p["total_payable"], 766.0)     # 300 + 400 + 60 + 6

    def test_02_pickup_never_charges_delivery(self):
        owner = self._user("9000000121")
        item = self._item(owner, delivery_available=True, delivery_charge=60.0)
        start = date.today() + timedelta(days=1); end = start
        p = calculate_price(item, start, end, user=None, delivery_method="pickup")
        self.assertEqual(p["delivery_method"], "pickup")
        self.assertEqual(p["delivery_charge"], 0.0)

    def test_03_item_without_delivery_rejects_delivery(self):
        owner = self._user("9000000131")
        item = self._item(owner, delivery_available=False, delivery_charge=60.0)
        start = date.today() + timedelta(days=1); end = start
        p = calculate_price(item, start, end, user=None, delivery_method="delivery")
        self.assertEqual(p["delivery_method"], "pickup")   # forced back to pickup
        self.assertEqual(p["delivery_charge"], 0.0)

    def test_04_fee_respects_min_and_max(self):
        owner = self._user("9000000141")
        item = self._item(owner, price=100.0, deposit=0.0)
        start = date.today() + timedelta(days=1); end = start + timedelta(days=9)  # 10 days rent 1000
        # Max clamp: 20% of 1000 = 200, but RENTER_FEE_MAX default 50
        self.app.config.update({"RENTER_FEE_PERCENT": 20, "RENTER_FEE_MIN": 0, "RENTER_FEE_MAX": 50})
        p = calculate_price(item, start, end, user=None, delivery_method="pickup")
        self.assertEqual(p["platform_fee"], 50.0)
        # Min clamp: 0.1% of 1000 = 1, but RENTER_FEE_MIN 10
        self.app.config.update({"RENTER_FEE_PERCENT": 0.1, "RENTER_FEE_MIN": 10, "RENTER_FEE_MAX": 50})
        p2 = calculate_price(item, start, end, user=None, delivery_method="pickup")
        self.assertEqual(p2["platform_fee"], 10.0)

    def test_05_total_equals_sum_of_displayed_lines(self):
        self.app.config["RENTER_FEE_PERCENT"] = 3
        owner = self._user("9000000151")
        renter = self._user("9000000152")
        item = self._item(owner, price=137.0, deposit=499.0, delivery_available=True, delivery_charge=45.5)
        start = date.today() + timedelta(days=1); end = start + timedelta(days=4)
        p = calculate_price(item, start, end, user=renter, delivery_method="delivery")
        displayed = Decimal(str(p["rent"])) + Decimal(str(p["deposit"])) + \
            Decimal(str(p["delivery_charge"])) + Decimal(str(p["platform_fee"]))
        self.assertEqual(Decimal(str(p["total_payable"])), displayed.quantize(Decimal("0.01")))

    def test_06_possible_later_charges_present_but_not_in_total(self):
        owner = self._user("9000000161")
        item = self._item(owner, price=100.0, deposit=500.0, late_fee=50.0)
        start = date.today() + timedelta(days=1); end = start
        p = calculate_price(item, start, end, user=None, delivery_method="pickup")
        types = {c["type"] for c in p["possible_later_charges"]}
        self.assertIn("late_fee", types)
        self.assertIn("damage", types)
        # not added to total
        self.assertEqual(p["total_payable"], p["rent"] + p["deposit"])

    def test_07_inr_format(self):
        self.assertEqual(inr(1250), "₹1,250")
        self.assertEqual(inr(1250.5), "₹1,250.50")
        self.assertEqual(inr(1250000), "₹1,250,000")
        self.assertEqual(inr(0), "₹0")


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Phase-7 tests: ROI tracker, smart price suggestion, language toggle, and final polish."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from datetime import date, timedelta
from unittest.mock import patch
from app import create_app
from models import db, User, Item, Booking, ReturnRecord, Subscription
from utils.roi import item_earnings, roi_progress, payback_days, utilization_30d, ROIProgress
from utils.pricing import suggest_price
from translations import t, TRANSLATIONS


class RentKartPhase7(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
            "WTF_CSRF_ENABLED": False,
            "SERVER_NAME": "localhost",
            "OTP_MODE": "demo",
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _login(self, phone="9876543210", name="Demo Owner", village="Bengaluru"):
        self.client.get("/logout")
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        return self.client.post("/login", data={
            "otp": "1234",
            "name": name,
            "village_or_city": village,
        }, follow_redirects=True)

    def _create_user(self, name, phone, village="Bengaluru", lat=12.9716, lng=77.5946):
        user = User(name=name, phone=phone, village_or_city=village, lat=lat, lng=lng)
        db.session.add(user)
        db.session.commit()
        return user

    def _create_item(self, owner, title="Item", category="clothes", price=500.0, purchase_price=None):
        item = Item(
            owner_id=owner.id,
            category=category,
            title=title,
            description="Test Description",
            price_per_day=price,
            deposit=1000.0,
            late_fee_per_day=50.0,
            purchase_price=purchase_price,
            is_available=True,
        )
        db.session.add(item)
        db.session.commit()
        return item

    # -------------------------------------------------------------------------
    # TEST 1: roi_progress and payback_days return correct values for sample item
    # -------------------------------------------------------------------------
    def test_roi_progress_and_payback_days(self):
        owner = self._create_user("Owner", "9111111111")
        renter = self._create_user("Renter", "9222222222")
        item = self._create_item(owner, title="Drill", purchase_price=1000)

        # Before any bookings
        prog = roi_progress(item)
        self.assertEqual(prog.percent, 0.0)
        self.assertEqual(prog.to_recover, 1000.0)
        self.assertIsNone(payback_days(item))

        # First booking: starts 2026-01-01, returns 2026-01-05, owner_earning=600
        d1_start = date(2026, 1, 1)
        d1_end = date(2026, 1, 5)
        b1 = Booking(
            item_id=item.id,
            renter_id=renter.id,
            start_date=d1_start,
            end_date=d1_end,
            days=4,
            total_rent=600.0,
            deposit=200.0,
            total_payable=800.0,
            status="returned",
        )
        db.session.add(b1)
        db.session.flush()

        r1 = ReturnRecord(
            booking_id=b1.id,
            actual_return_date=d1_end,
            owner_earning=600.0,
            refund_amount=200.0,
        )
        db.session.add(r1)
        db.session.commit()

        # After booking 1: earned 600 of 1000 -> 60%, 400 to recover, no payback yet
        prog1 = roi_progress(item)
        self.assertEqual(prog1.percent, 60.0)
        self.assertEqual(prog1.to_recover, 400.0)
        self.assertIsNone(payback_days(item))

        # Second booking: starts 2026-01-10, returns 2026-01-15, owner_earning=500
        d2_start = date(2026, 1, 10)
        d2_end = date(2026, 1, 15)
        b2 = Booking(
            item_id=item.id,
            renter_id=renter.id,
            start_date=d2_start,
            end_date=d2_end,
            days=5,
            total_rent=500.0,
            deposit=200.0,
            total_payable=700.0,
            status="returned",
        )
        db.session.add(b2)
        db.session.flush()

        r2 = ReturnRecord(
            booking_id=b2.id,
            actual_return_date=d2_end,
            owner_earning=500.0,
            refund_amount=200.0,
        )
        db.session.add(r2)
        db.session.commit()

        # Cumulative earned: 1100 >= 1000 -> capped at 100%, 0 to recover
        prog2 = roi_progress(item)
        self.assertEqual(prog2.percent, 100.0)
        self.assertEqual(prog2.to_recover, 0.0)

        # Payback days: from first booking start (2026-01-01) to b2 return (2026-01-15) = 14 days
        pdays = payback_days(item)
        self.assertEqual(pdays, 14)

    # -------------------------------------------------------------------------
    # TEST 2: Free owner sees locked ROI card, Pro owner sees insights
    # -------------------------------------------------------------------------
    def test_free_vs_pro_owner_roi_card(self):
        # 1. Free owner
        free_owner = self._create_user("Free Owner", "9333333333")
        self._create_item(free_owner, "Free Item", purchase_price=500)
        self._login(phone="9333333333")

        res_free = self.client.get("/dashboard/owner")
        self.assertEqual(res_free.status_code, 200)
        html_free = res_free.get_data(as_text=True)
        self.assertIn("Upgrade to Pro to unlock ROI tracking", html_free)
        self.assertIn("/pricing", html_free)
        self.assertNotIn("PRO UNLOCKED", html_free)

        # 2. Pro owner
        pro_owner = self._create_user("Pro Owner", "9444444444")
        self._create_item(pro_owner, "Pro Item", purchase_price=2000)
        today = date.today()
        sub = Subscription(
            user_id=pro_owner.id,
            plan="pro",
            status="active",
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
            amount_paid=99.0,
        )
        db.session.add(sub)
        db.session.commit()

        self._login(phone="9444444444")
        res_pro = self.client.get("/dashboard/owner")
        self.assertEqual(res_pro.status_code, 200)
        html_pro = res_pro.get_data(as_text=True)
        self.assertIn("My earnings insights", html_pro)
        self.assertIn("PRO UNLOCKED", html_pro)
        self.assertNotIn("Upgrade to Pro to unlock ROI tracking", html_pro)

    # -------------------------------------------------------------------------
    # TEST 3: Idle item appears in idle list
    # -------------------------------------------------------------------------
    def test_idle_item_in_idle_list(self):
        owner = self._create_user("Active Pro Owner", "9555555555")
        renter = self._create_user("Renter", "9666666666")
        today = date.today()

        # Pro subscription
        sub = Subscription(
            user_id=owner.id,
            plan="pro",
            status="active",
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
            amount_paid=99.0,
        )
        db.session.add(sub)

        # Active rented item
        active_item = self._create_item(owner, "Rented Camera", purchase_price=3000)
        b_act = Booking(
            item_id=active_item.id,
            renter_id=renter.id,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=2),
            days=7,
            total_rent=700.0,
            deposit=500.0,
            total_payable=1200.0,
            status="picked_up",
        )
        db.session.add(b_act)

        # Idle item with no bookings in last 30 days
        idle_item = self._create_item(owner, "Idle Lawn Mower", purchase_price=5000)
        db.session.commit()

        self.assertEqual(utilization_30d(idle_item), 0.0)
        self.assertGreater(utilization_30d(active_item), 0.0)

        self._login(phone="9555555555")
        res = self.client.get("/dashboard/owner")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Idle Lawn Mower", html)
        self.assertIn("Try lowering the price or sharing your shop QR", html)

    # -------------------------------------------------------------------------
    # TEST 4: /api/price-hint returns range, and boosted range in season (patch date)
    # -------------------------------------------------------------------------
    def test_price_hint_api_and_seasonal_boost(self):
        # 1. Base range check
        res = self.client.get("/api/price-hint?category=clothes")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["min"], 300)
        self.assertEqual(data["max"], 1000)

        # 2. In season check (Wedding season: November, month 11)
        with patch("utils.pricing.date") as mock_date:
            mock_date.today.return_value = date(2026, 11, 15)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            res_boosted = self.client.get("/api/price-hint?category=clothes")
            data_boosted = res_boosted.get_json()

            self.assertIsNotNone(data_boosted["season_name"])
            self.assertEqual(data_boosted["boost_percent"], 20)
            self.assertEqual(data_boosted["boosted_min"], 360)
            self.assertEqual(data_boosted["boosted_max"], 1200)

        # 3. Out of season check (August, month 8 for clothes)
        with patch("utils.pricing.date") as mock_date:
            mock_date.today.return_value = date(2026, 8, 15)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            res_off = self.client.get("/api/price-hint?category=clothes")
            data_off = res_off.get_json()

            self.assertIsNone(data_off["season_name"])
            self.assertIsNone(data_off["boosted_min"])
            self.assertIsNone(data_off["boosted_max"])

    # -------------------------------------------------------------------------
    # TEST 5: /set-language/hi changes page text, invalid code ignored, fallback
    # -------------------------------------------------------------------------
    def test_language_toggle_and_fallbacks(self):
        # Set to Hindi
        res = self.client.get("/set-language/hi", follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify page content is in Hindi
        res_home = self.client.get("/")
        html_home = res_home.get_data(as_text=True)
        self.assertIn("सामान देखें", html_home)
        self.assertIn("अपना रेंटल व्यवसाय शुरू करें", html_home)

        # Invalid code is ignored
        self.client.get("/set-language/invalid_xyz", follow_redirects=True)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("lang"), "hi")

        # Missing key in translations falls back to English
        with self.app.test_request_context():
            # A key only defined in en
            TRANSLATIONS["en"]["_test_fallback_key"] = "English Fallback Value"
            val = t("_test_fallback_key", lang="hi")
            self.assertEqual(val, "English Fallback Value")

            # A totally unknown key returns itself
            self.assertEqual(t("UnknownKeyXYZ", lang="hi"), "UnknownKeyXYZ")

    # -------------------------------------------------------------------------
    # TEST 6: 404 URL returns custom page
    # -------------------------------------------------------------------------
    def test_custom_404_page(self):
        res = self.client.get("/nonexistent-page-url-404")
        self.assertEqual(res.status_code, 404)
        html = res.get_data(as_text=True)
        self.assertIn("404", html)
        self.assertIn("Page Not Found", html)
        self.assertIn("Go Home", html)

    # -------------------------------------------------------------------------
    # TEST 7: Add Item form accepts optional purchase_price
    # -------------------------------------------------------------------------
    def test_add_item_form_optional_purchase_price(self):
        self._login(phone="9777777777", name="Seller User")

        # 1. With purchase_price
        res = self.client.post("/items/add", data={
            "category": "farm_tools",
            "title": "Seed Drill 2-Row",
            "description": "High precision seed drill",
            "price_per_day": "350",
            "deposit": "500",
            "late_fee_per_day": "50",
            "purchase_price": "8500",
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        item = Item.query.filter_by(title="Seed Drill 2-Row").first()
        self.assertIsNotNone(item)
        self.assertEqual(item.purchase_price, 8500)

        # 2. Without purchase_price (omitted/blank)
        res2 = self.client.post("/items/add", data={
            "category": "clothes",
            "title": "Party Blazer",
            "description": "Blue party blazer",
            "price_per_day": "250",
            "deposit": "400",
            "late_fee_per_day": "30",
            "purchase_price": "",
        }, follow_redirects=True)
        self.assertEqual(res2.status_code, 200)

        item2 = Item.query.filter_by(title="Party Blazer").first()
        self.assertIsNotNone(item2)
        self.assertIsNone(item2.purchase_price)


if __name__ == "__main__":
    unittest.main()

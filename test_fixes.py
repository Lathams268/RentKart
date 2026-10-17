"""Tests for Fixes 1, 2, and 3: Login improvements, clothes options, and pricing/subscription flow."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from datetime import date, timedelta
from urllib.parse import urlparse
from app import create_app
from models import db, User, Item, Subscription
import config


class RentKartFixesTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
            "WTF_CSRF_ENABLED": False,
            "SERVER_NAME": "localhost",
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _create_user(self, name="Test Owner", phone="9876543210", village="Bengaluru"):
        user = User(name=name, phone=phone, village_or_city=village)
        db.session.add(user)
        db.session.commit()
        return user

    def _login(self, phone="9876543210", name="Test Owner", village="Bengaluru"):
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        return self.client.post("/login", data={
            "otp": "1234",
            "name": name,
            "village_or_city": village,
        }, follow_redirects=True)

    # -------------------------------------------------------------------------
    # TEST 1: /login always renders an empty phone field
    # -------------------------------------------------------------------------
    def test_01_login_renders_empty_phone_field(self):
        # 1. Fresh GET /login
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn('name="phone"', html)
        self.assertIn('autocomplete="off"', html)
        self.assertIn('value=""', html)

        # 2. Even with leftover session, rendering step 1 always has empty input
        with self.client.session_transaction() as sess:
            sess["login_step"] = "phone"
            sess["login_phone"] = "9999999999"

        res2 = self.client.get("/login")
        html2 = res2.get_data(as_text=True)
        self.assertIn('value=""', html2)
        self.assertNotIn('value="9999999999"', html2)

    # -------------------------------------------------------------------------
    # TEST 2: "change number" clears pending phone, and resend keeps the phone
    # -------------------------------------------------------------------------
    def test_02_change_number_clears_phone_and_resend_keeps_phone(self):
        phone_num = "9876512345"
        # Enter phone number to get to step 2
        res = self.client.post("/login", data={"phone": phone_num}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("login_phone"), phone_num)
            self.assertEqual(sess.get("login_step"), "otp")

        # Step 2 HTML check
        html_step2 = res.get_data(as_text=True)
        self.assertIn("OTP sent to +91 XXXXX12345", html_step2)
        self.assertIn("Change number", html_step2)

        # 1. Change number
        res_change = self.client.get("/login/change-number", follow_redirects=True)
        self.assertEqual(res_change.status_code, 200)

        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("login_phone"))
            self.assertNotEqual(sess.get("login_step"), "otp")

        # 2. Resend keeps the phone
        self.client.post("/login", data={"phone": phone_num}, follow_redirects=True)
        res_resend = self.client.post("/resend-otp", follow_redirects=True)
        self.assertEqual(res_resend.status_code, 200)
        self.assertIn("OTP resent", res_resend.get_data(as_text=True))

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("login_phone"), phone_num)
            self.assertEqual(sess.get("login_step"), "otp")

    # -------------------------------------------------------------------------
    # TEST 3: An external next URL like //evil.com is ignored
    # -------------------------------------------------------------------------
    def test_03_external_next_url_is_ignored(self):
        # 1. Provide malicious next URL
        res = self.client.get("/login?next=//evil.com")
        self.assertEqual(res.status_code, 200)

        # Submit phone
        self.client.post("/login", data={"phone": "9888888888", "next": "//evil.com"}, follow_redirects=False)

        # Submit OTP and verify login redirect does NOT go to //evil.com
        res_login = self.client.post("/login", data={
            "otp": "1234",
            "name": "Safety User",
            "village_or_city": "SafeCity",
            "next": "//evil.com",
        }, follow_redirects=False)

        self.assertEqual(res_login.status_code, 302)
        target = res_login.headers.get("Location")
        self.assertFalse(target.startswith("//evil.com"))
        parsed = urlparse(target)
        self.assertEqual(parsed.path, "/")

    # -------------------------------------------------------------------------
    # TEST 4: Visiting /subscribe/pro?cycle=yearly while logged out redirects
    #         to /login?next=... and after login lands on checkout page
    # -------------------------------------------------------------------------
    def test_04_subscribe_logged_out_redirects_and_lands_on_checkout(self):
        target_sub = "/subscribe/pro?cycle=yearly"
        # 1. Logged out visit
        res = self.client.get(target_sub, follow_redirects=False)
        self.assertEqual(res.status_code, 302)

        loc = res.headers.get("Location")
        self.assertIn("/login", loc)
        self.assertIn("next=", loc)
        from urllib.parse import unquote
        self.assertIn("cycle=yearly", unquote(loc))


        # Verify flash message
        res_follow = self.client.get(target_sub, follow_redirects=True)
        self.assertIn("Please log in to continue", res_follow.get_data(as_text=True))

        # 2. Complete login with that next URL
        self.client.post("/login", data={"phone": "9777777777"}, follow_redirects=True)
        res_after_login = self.client.post("/login", data={
            "otp": "1234",
            "name": "Subscriber",
            "village_or_city": "Indiranagar",
        }, follow_redirects=True)

        self.assertEqual(res_after_login.status_code, 200)
        html_checkout = res_after_login.get_data(as_text=True)
        self.assertIn("Pro Plan Subscription", html_checkout)
        self.assertIn("Yearly", html_checkout)
        self.assertIn("990", html_checkout)
        self.assertIn("Demo Mode Notice", html_checkout)

    # -------------------------------------------------------------------------
    # TEST 5: Completing checkout creates an active Pro subscription
    # -------------------------------------------------------------------------
    def test_05_checkout_creates_active_pro_subscription(self):
        user = self._create_user(name="Pro Buyer", phone="9666666666")
        self._login(phone="9666666666")

        # Checkout POST
        res = self.client.post("/subscribe/pro", data={
            "billing_cycle": "monthly",
            "payment_method": "upi",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn("Successfully subscribed to Pro Plan", res.get_data(as_text=True))

        # Check DB
        sub = Subscription.query.filter_by(user_id=user.id, plan="pro").first()
        self.assertIsNotNone(sub)
        self.assertEqual(sub.status, "active")
        self.assertEqual(sub.amount_paid, 99.0)
        self.assertEqual(user.current_plan(), "pro")

        # Visiting checkout again while plan is active redirects with notice
        res_again = self.client.get("/subscribe/pro", follow_redirects=True)
        self.assertEqual(res_again.status_code, 200)
        self.assertIn("already have an active Pro plan", res_again.get_data(as_text=True))

    # -------------------------------------------------------------------------
    # TEST 6: Clothes config has clothing_type and color, and an item saved
    #         with them shows them on the detail page
    # -------------------------------------------------------------------------
    def test_06_clothes_config_and_detail_page(self):
        clothes_fields = {f["name"]: f for f in config.CATEGORIES["clothes"]["fields"]}
        self.assertIn("clothing_type", clothes_fields)
        self.assertIn("color", clothes_fields)
        self.assertEqual(clothes_fields["clothing_type"]["type"], "select")
        self.assertIn("Lehenga", clothes_fields["clothing_type"]["options"])
        self.assertEqual(clothes_fields["color"]["type"], "select")
        self.assertIn("Red", clothes_fields["color"]["options"])

        owner = self._create_user(name="Fashion Owner", phone="9555555555")
        item = Item(
            owner_id=owner.id,
            category="clothes",
            title="Bridal Red Lehenga",
            description="Exquisite designer wedding lehenga",
            price_per_day=1200.0,
            deposit=4000.0,
            late_fee_per_day=150.0,
            is_available=True,
        )
        item.set_attributes({
            "clothing_type": "Lehenga",
            "color": "Red",
            "size": "M",
            "occasion": "Wedding",
            "fabric": "Silk",
            "gender": "Women",
        })
        db.session.add(item)
        db.session.commit()

        res = self.client.get(f"/items/{item.id}")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Clothing Type", html)
        self.assertIn("Lehenga", html)
        self.assertIn("Color", html)
        self.assertIn("Red", html)

    # -------------------------------------------------------------------------
    # TEST 7: An old clothes item without the new fields still loads
    # -------------------------------------------------------------------------
    def test_07_old_clothes_item_loads_without_errors(self):
        owner = self._create_user(name="Vintage Owner", phone="9444444444")
        old_item = Item(
            owner_id=owner.id,
            category="clothes",
            title="Vintage Kurta",
            description="Classic vintage cotton kurta",
            price_per_day=200.0,
            deposit=500.0,
            late_fee_per_day=20.0,
            is_available=True,
        )
        # Old item attrs without clothing_type or color
        old_item.set_attributes({
            "size": "L",
            "occasion": "Festival",
            "fabric": "Cotton",
            "gender": "Men",
        })
        db.session.add(old_item)
        db.session.commit()

        res = self.client.get(f"/items/{old_item.id}")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Vintage Kurta", html)
        self.assertIn("Cotton", html)
        self.assertIn("Clothing Type", html)
        # Empty field displays fallback '—' safely
        self.assertIn("—", html)


if __name__ == "__main__":
    unittest.main()

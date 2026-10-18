"""Tests for Stage 1: Login OTP Hint and SMS OTP Mode."""
import os
import time
import unittest
from app import create_app
from models import db, User, Item
import config
from utils.otp import send_sms_otp


class TestStage1(unittest.TestCase):
    def setUp(self):
        self.test_db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "test_stage1.db")
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.test_db_path}",
            "WTF_CSRF_ENABLED": False,
            "OTP_MODE": "demo",
        })
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()
            user = User(name="Test User", phone="9000000001", village_or_city="Bengaluru")
            db.session.add(user)
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except OSError:
                pass

    def test_config_otp_mode_default(self):
        """config.py specifies OTP_MODE='demo' by default."""
        self.assertTrue(hasattr(config, "OTP_MODE"))
        self.assertEqual(config.OTP_MODE, "demo")

    def test_login_page_shows_demo_mode_and_otp(self):
        """Login page displays 'Demo mode' and '1234'."""
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Demo mode", html)
        self.assertIn("1234", html)

    def test_otp_step_shows_big_green_box_and_fill_otp_button(self):
        """OTP step displays green demo box, 'Fill OTP' button, and autofocus."""
        res = self.client.post("/login", data={"phone": "9000000001"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Demo mode", html)
        self.assertIn("1234", html)
        self.assertIn("Fill OTP", html)
        self.assertIn("autofocus", html)

    def test_demo_login_success(self):
        """Entering 1234 logs in successfully in demo mode."""
        self.client.post("/login", data={"phone": "9000000001"}, follow_redirects=True)
        res = self.client.post("/login", data={"otp": "1234"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Welcome, Test User!", html)

    def test_utils_otp_stub(self):
        """utils.otp.send_sms_otp returns True and is callable."""
        result = send_sms_otp("9000000001", "5678")
        self.assertTrue(result)

    def test_sms_mode_flow(self):
        """When OTP_MODE is sms, generates random 4-digit OTP with 5 min expiry."""
        self.app.config["OTP_MODE"] = "sms"
        with self.client.session_transaction() as sess:
            sess.clear()

        # Step 1: submit phone
        self.client.post("/login", data={"phone": "9000000001"}, follow_redirects=True)

        with self.client.session_transaction() as sess:
            otp = sess.get("login_otp")
            expires_at = sess.get("otp_expires_at")
            self.assertIsNotNone(otp)
            self.assertEqual(len(otp), 4)
            self.assertTrue(otp.isdigit())
            self.assertIsNotNone(expires_at)
            # Expiry should be roughly 300 seconds from now
            self.assertGreater(expires_at, time.time() + 250)

        # Invalid OTP fails
        res_fail = self.client.post("/login", data={"otp": "0000"}, follow_redirects=True)
        self.assertIn("Invalid OTP", res_fail.get_data(as_text=True))

        # Correct OTP succeeds
        res_ok = self.client.post("/login", data={"otp": otp}, follow_redirects=True)
        self.assertIn("Welcome, Test User!", res_ok.get_data(as_text=True))


class TestStage1Filters(unittest.TestCase):
    def setUp(self):
        self.test_db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "test_stage1_filters.db")
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.test_db_path}",
            "WTF_CSRF_ENABLED": False,
        })
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()
            owner = User(name="Owner User", phone="9000000002", village_or_city="Bengaluru", lat=12.9716, lng=77.5946)
            db.session.add(owner)
            db.session.commit()

            item1 = Item(
                title="Baby Romper Set",
                description="Cotton wear for infants",
                category="clothes",
                price_per_day=300.0,
                deposit=500.0,
                is_available=True,
                owner_id=owner.id,
                lat=12.9716,
                lng=77.5946,
            )
            item1.set_attributes({"age_group": "0–2", "size": "0-6M", "gender": "Boys", "clothing_type": "Ethnic Wear"})

            item2 = Item(
                title="Designer Wedding Saree",
                description="Pure silk red saree",
                category="clothes",
                price_per_day=850.0,
                deposit=1500.0,
                is_available=True,
                owner_id=owner.id,
                lat=12.9716,
                lng=77.5946,
            )
            item2.set_attributes({"age_group": "18+", "size": "Free Size", "gender": "Women", "clothing_type": "Saree"})

            item3 = Item(
                title="Telugu Comedy Stories",
                description="Humorous Telugu classic",
                category="books",
                price_per_day=35.0,
                deposit=100.0,
                is_available=True,
                owner_id=owner.id,
                lat=12.9716,
                lng=77.5946,
            )
            item3.set_attributes({"language": "Telugu", "genre": "Comedy"})

            db.session.add_all([item1, item2, item3])
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except OSError:
                pass

    def test_price_1_gives_empty_state_with_suggestion(self):
        """price 1 gives the empty state with the suggestion."""
        res = self.client.get("/browse?max_price=1")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Empty state header and suggestion
        self.assertIn("No items match your selected filters", html)
        self.assertIn("No items match all filters. Removing 'Max price Rs 1' gives", html)
        self.assertIn("Max price Rs 1", html)
        # Removable chip with &times; or x
        self.assertIn("&times;", html)
        # Clear all filters button
        self.assertIn("Clear all filters", html)
        # You might like section
        self.assertIn("You might like", html)

    def test_empty_price_is_ignored(self):
        """empty price is ignored and max price input is empty by default."""
        # Empty max_price query
        res = self.client.get("/browse?max_price=")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertNotIn("No items match your selected filters", html)

        # Both min and max price empty
        res2 = self.client.get("/browse?min_price=&max_price=")
        self.assertEqual(res2.status_code, 200)
        html2 = res2.get_data(as_text=True)
        self.assertNotIn("No items match your selected filters", html2)

        # Default browse page: max price input has placeholder and is not prefilled with 1.0
        res_default = self.client.get("/browse")
        html_def = res_default.get_data(as_text=True)
        self.assertIn('placeholder="Max/day"', html_def)
        self.assertIn('name="max_price"', html_def)
        self.assertIn('name="max_price" min="0" step="1" placeholder="Max/day"\n             value=""', html_def)
        self.assertNotIn('name="max_price" value="1.0"', html_def)

    def test_changing_age_group_resets_invalid_size(self):
        """changing age group resets an invalid size."""
        # Adult size 'M' is invalid for kids age group '0–2'
        res = self.client.get("/browse?category=clothes&attr_age_group=0–2&attr_size=M")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        # Size 'M' should be reset, so Baby Romper is displayed!
        self.assertIn("Baby Romper Set", html)

        # Also test with hyphen 0-2 and size XL
        res2 = self.client.get("/browse?category=clothes&attr_age_group=0-2&attr_size=XL")
        self.assertEqual(res2.status_code, 200)
        html2 = res2.get_data(as_text=True)
        self.assertIn("Baby Romper Set", html2)

        # Also test 18+ with a kids size '0-6M': invalid size is reset, adult item is displayed
        res3 = self.client.get("/browse?category=clothes&attr_age_group=18%2B&attr_size=0-6M")
        self.assertEqual(res3.status_code, 200)
        html3 = res3.get_data(as_text=True)
        self.assertIn("Designer Wedding Saree", html3)


if __name__ == "__main__":
    unittest.main()

"""
Comprehensive test suite for:
1. OTP verification with proper SMS gateway handling (Fast2SMS, Twilio, demo mode, and failure error messages).
2. Product filtering functionality ensuring products load correctly from database.
3. Boys and Girls clothing sections.
4. Age-based categories (0–2, 3–5, 6–8, 9–12, 13–17, 18+ years).
5. Multi-attribute product filters (gender, age_group, clothing_type, size, price range, brand).
"""
import os
import unittest
from unittest.mock import patch, MagicMock
from app import create_app
from models import db, User, Item
from utils.otp import send_sms_otp, SMSResult
import config


class TestOtpAndClothingFeatures(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    # =========================================================================
    # Requirement 1: OTP verification & error messages on delivery failure
    # =========================================================================
    def test_otp_invalid_phone_rejected(self):
        """Invalid phone numbers (<10 digits or empty) return clear error."""
        res = send_sms_otp("", "1234")
        self.assertFalse(res)
        self.assertIn("Invalid phone number", res.message)

        res2 = send_sms_otp("12345", "1234")
        self.assertFalse(res2)
        self.assertIn("10-digit", res2.message)

        # In login route
        resp = self.client.post("/login", data={"phone": "123"}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("Please enter a valid 10-digit mobile number", html)

    def test_otp_sms_mode_without_credentials_flashes_clear_error(self):
        """When OTP_MODE is 'sms' and no gateway credentials configured, flashes clear error."""
        with patch.dict(os.environ, {"OTP_MODE": "sms", "FAST2SMS_API_KEY": "", "TWILIO_ACCOUNT_SID": "", "STRICT_SMS_CONFIG": "1"}, clear=False):
            with self.app.test_client() as c:
                resp = c.post("/login", data={"phone": "9876543210"}, follow_redirects=True)
                self.assertEqual(resp.status_code, 200)
                html = resp.data.decode("utf-8")
                self.assertIn("SMS gateway credentials not configured", html)

    def test_otp_fast2sms_success_and_failure(self):
        """Test Fast2SMS delivery success and error response handling."""
        # Fast2SMS success
        fake_resp = MagicMock()
        fake_resp.getcode.return_value = 200
        fake_resp.read.return_value = b'{"return": true, "message": ["SMS sent successfully."]}'
        fake_resp.__enter__.return_value = fake_resp

        with patch("urllib.request.urlopen", return_value=fake_resp):
            with patch.dict(os.environ, {"FAST2SMS_API_KEY": "dummy-key"}):
                res = send_sms_otp("9876543210", "4567")
                self.assertTrue(res)
                self.assertIn("Fast2SMS", res.message)

        # Fast2SMS rejection
        fake_err_resp = MagicMock()
        fake_err_resp.getcode.return_value = 200
        fake_err_resp.read.return_value = b'{"return": false, "message": "Invalid API Key or balance expired"}'
        fake_err_resp.__enter__.return_value = fake_err_resp

        with patch("urllib.request.urlopen", return_value=fake_err_resp):
            with patch.dict(os.environ, {"FAST2SMS_API_KEY": "bad-key"}):
                res = send_sms_otp("9876543210", "4567")
                self.assertFalse(res)
                self.assertIn("Invalid API Key or balance expired", res.message)

    def test_otp_twilio_success_and_failure(self):
        """Test Twilio SMS delivery success and error response handling."""
        # Twilio success
        fake_resp = MagicMock()
        fake_resp.getcode.return_value = 201
        fake_resp.read.return_value = b'{"sid": "SM1234567890", "status": "queued"}'
        fake_resp.__enter__.return_value = fake_resp

        with patch("urllib.request.urlopen", return_value=fake_resp):
            with patch.dict(os.environ, {"TWILIO_ACCOUNT_SID": "AC123", "TWILIO_AUTH_TOKEN": "token123"}):
                res = send_sms_otp("9876543210", "4567")
                self.assertTrue(res)
                self.assertIn("Twilio", res.message)

        # Twilio error
        fake_err = MagicMock()
        fake_err.getcode.return_value = 400
        fake_err.read.return_value = b'{"code": 21211, "message": "The \'To\' number is not a valid phone number."}'
        fake_err.__enter__.return_value = fake_err

        with patch("urllib.request.urlopen", return_value=fake_err):
            with patch.dict(os.environ, {"TWILIO_ACCOUNT_SID": "AC123", "TWILIO_AUTH_TOKEN": "token123"}):
                res = send_sms_otp("9876543210", "4567")
                self.assertFalse(res)
                self.assertIn("not a valid phone number", res.message)

    def test_otp_resend_error_displayed_on_failure(self):
        """Resending OTP via SMS displays error message if gateway delivery fails."""
        with patch.dict(os.environ, {"OTP_MODE": "sms", "FAST2SMS_API_KEY": "", "STRICT_SMS_CONFIG": "1"}):
            with self.client.session_transaction() as sess:
                sess["login_phone"] = "9876543210"
                sess["login_step"] = "otp"

            resp = self.client.post("/resend-otp", follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            html = resp.data.decode("utf-8")
            self.assertIn("Failed to resend OTP", html)

    # =========================================================================
    # Requirement 2 & 5: Product Filtering functionality & Loading from Database
    # =========================================================================
    def test_clothes_browse_loads_products_from_database(self):
        """Browsing clothes category shows the marketplace page with tab tiles.

        Updated: the old browse.html 'Boys Collection'/'Girls Collection' sections
        were replaced by the Men/Women/Children tab marketplace layout.
        """
        resp = self.client.get("/browse?category=clothes")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        # Tab labels (new layout)
        self.assertIn("Men", html)
        self.assertIn("Women", html)
        self.assertIn("Children", html)
        # Default tab (Women) item appears
        self.assertIn("Silk Lehenga", html)
        # Children tab items accessible via tab param
        resp2 = self.client.get("/browse?category=clothes&tab=children")
        html2 = resp2.data.decode("utf-8")
        self.assertIn("Boys Royal Kurta Pajama Set", html2)
        self.assertIn("Baby Girls Silk Pattu Pavadai", html2)

    # =========================================================================
    # Requirement 3: Separate categories for Boys and Girls
    # =========================================================================
    def test_boys_clothing_section_filtering(self):
        """Dedicated boys clothing filter returns only boys items."""
        # Using clothing_section parameter
        resp = self.client.get("/browse?category=clothes&clothing_section=boys")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("Boys Royal Kurta Pajama Set", html)
        self.assertIn("Boys Festive Dhoti Kurta", html)
        self.assertIn("Boys Classic Navy Blazer Suit", html)
        self.assertNotIn("Baby Girls Silk Pattu Pavadai", html)
        self.assertNotIn("Girls Layered Birthday Frock", html)

        # Using gender=Boys direct attribute
        resp2 = self.client.get("/browse?category=clothes&attr_gender=Boys")
        self.assertEqual(resp2.status_code, 200)
        html2 = resp2.data.decode("utf-8")
        self.assertIn("Boys Royal Kurta Pajama Set", html2)
        self.assertNotIn("Girls Layered Birthday Frock", html2)

    def test_girls_clothing_section_filtering(self):
        """Dedicated girls clothing filter returns only girls items."""
        # Using clothing_section parameter
        resp = self.client.get("/browse?category=clothes&clothing_section=girls")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("Baby Girls Silk Pattu Pavadai", html)
        self.assertIn("Girls Layered Birthday Frock", html)
        self.assertIn("Girls Festive Chaniya Choli", html)
        self.assertNotIn("Boys Royal Kurta Pajama Set", html)
        self.assertNotIn("Teen Boys Tuxedo Blazer Set", html)

        # Using gender=Girls direct attribute
        resp2 = self.client.get("/browse?category=clothes&attr_gender=Girls")
        self.assertEqual(resp2.status_code, 200)
        html2 = resp2.data.decode("utf-8")
        self.assertIn("Baby Girls Silk Pattu Pavadai", html2)
        self.assertNotIn("Boys Royal Kurta Pajama Set", html2)

    # =========================================================================
    # Requirement 4: Age-based clothing categories (0–2, 3–5, 6–8, 9–12, 13–17, 18+)
    # =========================================================================
    def test_age_group_filtering_across_all_brackets(self):
        """Filter by each age bracket: 0–2, 3–5, 6–8, 9–12, 13–17, 18+."""
        age_tests = [
            ("0–2", ["Boys Royal Kurta Pajama Set", "Baby Girls Silk Pattu Pavadai"], ["Boys Festive Dhoti Kurta", "Silk Lehenga"]),
            ("3–5", ["Boys Festive Dhoti Kurta", "Girls Layered Birthday Frock"], ["Boys Royal Kurta Pajama Set", "Silk Lehenga"]),
            ("6–8", ["Boys Indo-Western Sherwani Set", "Girls Festive Chaniya Choli"], ["Boys Royal Kurta Pajama Set", "Baby Girls Silk Pattu Pavadai"]),
            ("9–12", ["Boys Classic Navy Blazer Suit", "Girls Embroidered Anarkali Gown"], ["Boys Festive Dhoti Kurta", "Silk Lehenga"]),
            ("13–17", ["Teen Boys Tuxedo Blazer Set", "Teen Girls Crop Top Lehenga"], ["Boys Royal Kurta Pajama Set", "Baby Girls Silk Pattu Pavadai"]),
            ("18+", ["Silk Lehenga", "Designer Sherwani", "Pattu Saree"], ["Boys Royal Kurta Pajama Set", "Girls Festive Chaniya Choli"]),
        ]

        for ag, expected_present, expected_absent in age_tests:
            with self.subTest(age_group=ag):
                resp = self.client.get(f"/browse?category=clothes&attr_age_group={ag}")
                self.assertEqual(resp.status_code, 200)
                html = resp.data.decode("utf-8")
                for item_title in expected_present:
                    self.assertIn(item_title, html, f"Expected '{item_title}' in age group {ag}")
                for item_title in expected_absent:
                    self.assertNotIn(item_title, html, f"Expected '{item_title}' NOT in age group {ag}")

    # =========================================================================
    # Requirement 5: Working product filters for clothing type, size, price range, brand
    # =========================================================================
    def test_clothing_type_filter(self):
        """Filter by clothing_type (Lehenga, Sherwani, Kurta Set, Frock, etc.)."""
        # Kurta Set
        resp = self.client.get("/browse?category=clothes&attr_clothing_type=Kurta+Set")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("Boys Royal Kurta Pajama Set", html)
        self.assertIn("Boys Festive Dhoti Kurta", html)
        self.assertNotIn("Silk Lehenga", html)

        # Lehenga
        resp_leh = self.client.get("/browse?category=clothes&attr_clothing_type=Lehenga")
        self.assertEqual(resp_leh.status_code, 200)
        html_leh = resp_leh.data.decode("utf-8")
        self.assertIn("Silk Lehenga", html_leh)
        self.assertIn("Girls Festive Chaniya Choli", html_leh)
        self.assertNotIn("Boys Classic Navy Blazer Suit", html_leh)

    def test_size_filter(self):
        """Filter by size for kids and adult clothes."""
        # Kids size 1-2Y
        resp = self.client.get("/browse?category=clothes&attr_size=1-2Y")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("Boys Royal Kurta Pajama Set", html)
        self.assertNotIn("Girls Layered Birthday Frock", html)

        # Adult size M
        resp_m = self.client.get("/browse?category=clothes&attr_size=M")
        self.assertEqual(resp_m.status_code, 200)
        html_m = resp_m.data.decode("utf-8")
        self.assertIn("Silk Lehenga", html_m)
        self.assertNotIn("Boys Royal Kurta Pajama Set", html_m)

    def test_price_range_filter(self):
        """Filter by min_price and max_price per day."""
        # Under ₹200/day
        resp_cheap = self.client.get("/browse?category=clothes&max_price=200")
        self.assertEqual(resp_cheap.status_code, 200)
        html_cheap = resp_cheap.data.decode("utf-8")
        self.assertIn("Boys Royal Kurta Pajama Set", html_cheap)  # 120/day
        self.assertIn("Baby Girls Silk Pattu Pavadai", html_cheap) # 140/day
        self.assertNotIn("Silk Lehenga", html_cheap)              # 500/day
        self.assertNotIn("Designer Sherwani", html_cheap)         # 800/day

        # Between ₹300 and ₹600/day
        resp_mid = self.client.get("/browse?category=clothes&min_price=300&max_price=600")
        self.assertEqual(resp_mid.status_code, 200)
        html_mid = resp_mid.data.decode("utf-8")
        self.assertIn("Silk Lehenga", html_mid)                   # 500/day
        self.assertIn("Pattu Saree", html_mid)                    # 400/day
        self.assertNotIn("Boys Royal Kurta Pajama Set", html_mid) # 120/day
        self.assertNotIn("Designer Sherwani", html_mid)          # 800/day

    def test_brand_filter(self):
        """Filter clothes by brand (Zara Kids, FabIndia Kids, Shravani, Manyavar Kids)."""
        # Zara Kids
        resp_zara = self.client.get("/browse?category=clothes&brand=Zara+Kids")
        self.assertEqual(resp_zara.status_code, 200)
        html_zara = resp_zara.data.decode("utf-8")
        self.assertIn("Boys Classic Navy Blazer Suit", html_zara)
        self.assertIn("Girls Layered Birthday Frock", html_zara)
        self.assertNotIn("Silk Lehenga", html_zara)

        # Shravani
        resp_shr = self.client.get("/browse?category=clothes&brand=Shravani")
        self.assertEqual(resp_shr.status_code, 200)
        html_shr = resp_shr.data.decode("utf-8")
        self.assertIn("Silk Lehenga", html_shr)
        self.assertIn("Baby Girls Silk Pattu Pavadai", html_shr)
        self.assertNotIn("Boys Classic Navy Blazer Suit", html_shr)

    def test_multi_filter_combination(self):
        """Combining gender + age_group + clothing_type + price range."""
        resp = self.client.get(
            "/browse?category=clothes&clothing_section=boys&attr_age_group=0–2&attr_clothing_type=Kurta+Set&max_price=150"
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("Boys Royal Kurta Pajama Set", html)
        self.assertNotIn("Boys Festive Dhoti Kurta", html) # > 150
        self.assertNotIn("Baby Girls Silk Pattu Pavadai", html) # Girls


if __name__ == "__main__":
    unittest.main()

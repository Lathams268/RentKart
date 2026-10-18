"""Unit tests for RentKart OTP login flow in demo mode."""
import os
import unittest
from app import create_app
from models import db, User
import config


class TestOtpLoginFlow(unittest.TestCase):
    def setUp(self):
        self.test_db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "test_otp.db")
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.test_db_path}",
            "WTF_CSRF_ENABLED": False,
            "OTP_MODE": "demo",
            "DEMO_OTP": "1234",
        })
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()
            self.test_user = User(
                name="Suresh Kumar",
                phone="9876541234",
                village_or_city="Mandya",
            )
            db.session.add(self.test_user)
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

    def test_demo_mode_contains_1234_and_demo_mode(self):
        """Login page in demo mode contains '1234' and 'Demo mode' in both step 1 and step 2."""
        # Step 1: phone entry page
        res1 = self.client.get("/login")
        self.assertEqual(res1.status_code, 200)
        html1 = res1.get_data(as_text=True)
        self.assertIn("Demo mode", html1)
        self.assertIn("1234", html1)

        # Step 2: OTP page
        res2 = self.client.post("/login", data={"phone": "9876541234"}, follow_redirects=True)
        self.assertEqual(res2.status_code, 200)
        html2 = res2.get_data(as_text=True)
        self.assertIn("Demo mode", html2)
        self.assertIn("1234", html2)
        self.assertIn("Fill OTP", html2)
        self.assertIn("RentKart: Your OTP is 1234. Do not share it.", html2)

    def test_phone_is_masked(self):
        """Phone number middle digits are masked (e.g. +91 XXXXXX1234)."""
        res = self.client.post("/login", data={"phone": "9876541234"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("+91 XXXXXX1234", html)
        self.assertIn("OTP sent to +91 XXXXXX1234", html)

    def test_wrong_otp_rejected_and_phone_kept(self):
        """Wrong OTP flashes 'Wrong OTP, try again' and keeps phone number."""
        self.client.post("/login", data={"phone": "9876541234"}, follow_redirects=True)
        res = self.client.post("/login", data={"otp": "9999"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Wrong OTP, try again", html)

        # Phone is kept in session and masked display remains
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("login_phone"), "9876541234")
            self.assertEqual(sess.get("login_step"), "otp")
        self.assertIn("+91 XXXXXX1234", html)

    def test_correct_otp_logs_in(self):
        """Entering correct OTP (1234) logs in successfully."""
        self.client.post("/login", data={"phone": "9876541234"}, follow_redirects=True)
        res = self.client.post("/login", data={"otp": "1234"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Welcome, Suresh Kumar!", html)

        # Session login data cleaned up
        with self.client.session_transaction() as sess:
            self.assertNotIn("login_step", sess)
            self.assertNotIn("login_phone", sess)


if __name__ == "__main__":
    unittest.main()

"""SMS OTP tests — requests.post is always mocked; never send a real SMS."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app import create_app
from models import db, User
from utils.otp import generate_otp, hash_otp, normalize_phone, otp_matches, reset_rate_limits


def _ok_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.content = b'{"return": true}'
    resp.json.return_value = {"return": True, "message": ["SMS sent"]}
    resp.text = '{"return": true}'
    return resp


def _payload(mock_post):
    kwargs = mock_post.call_args.kwargs if mock_post.call_args.kwargs else {}
    if "data" in kwargs:
        return kwargs["data"]
    args = mock_post.call_args.args
    return args[1] if len(args) > 1 else {}


class TestRealOtpSms(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret-key",
            "OTP_MODE": "sms",
            "SMS_API_KEY": "test-sms-key",
            "FAST2SMS_ROUTE": "otp",
            "OTP_LENGTH": 4,
            "OTP_EXPIRY_MINUTES": 5,
            "OTP_MAX_ATTEMPTS": 5,
            "OTP_RESEND_SECONDS": 30,
            "OTP_MAX_SENDS": 3,
            "OTP_SEND_WINDOW_MINUTES": 10,
            "DEMO_OTP": "1234",
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        db.session.add(User(name="Asha", phone="9876543210", village_or_city="Bengaluru"))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        reset_rate_limits()

    def test_normalize_and_hash(self):
        self.assertEqual(normalize_phone("+91 98765 43210"), "9876543210")
        self.assertEqual(normalize_phone("09876543210"), "9876543210")
        self.assertIsNone(normalize_phone("12345"))
        self.assertIsNone(normalize_phone("5876543210"))
        a, b = generate_otp(4), generate_otp(4)
        self.assertTrue(a.isdigit() and len(a) == 4)
        self.assertTrue(otp_matches(a, hash_otp(a)))
        self.assertFalse(otp_matches(a, hash_otp(b)) and a != b)

    @patch("requests.post")
    def test_provider_called_once_with_header_and_number(self, mock_post):
        mock_post.return_value = _ok_response()
        res = self.client.post("/login", data={"phone": "9876543210"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(mock_post.call_count, 1)
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://www.fast2sms.com/dev/bulkV2")
        self.assertEqual(kwargs["headers"]["authorization"], "test-sms-key")
        self.assertEqual(kwargs["timeout"], 10)
        data = kwargs["data"]
        self.assertEqual(data["route"], "otp")
        self.assertEqual(data["numbers"], "9876543210")
        self.assertEqual(len(str(data["variables_values"])), 4)

    @patch("requests.post")
    def test_sms_page_has_no_otp_and_no_demo_mode(self, mock_post):
        mock_post.return_value = _ok_response()
        res = self.client.post("/login", data={"phone": "9876543210"}, follow_redirects=True)
        html = res.get_data(as_text=True)
        self.assertNotIn("Demo mode", html)
        self.assertNotIn("Fill OTP", html)
        otp = _payload(mock_post)["variables_values"]
        self.assertNotIn(str(otp), html)
        with self.client.session_transaction() as sess:
            self.assertNotIn("login_otp", sess)
            self.assertTrue(sess.get("otp_hash"))

    @patch("requests.post")
    def test_balance_error_shown(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b'{"return": false, "message": "Insufficient balance"}'
        resp.json.return_value = {"return": False, "message": "Insufficient balance"}
        resp.text = "Insufficient balance"
        mock_post.return_value = resp
        res = self.client.post("/login", data={"phone": "9876543210"}, follow_redirects=True)
        html = res.get_data(as_text=True)
        self.assertIn("balance", html.lower())
        self.assertIn('name="phone"', html)

    @patch("requests.post")
    def test_timeout_handled(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.Timeout("timed out")
        res = self.client.post("/login", data={"phone": "9876543210"}, follow_redirects=True)
        html = res.get_data(as_text=True)
        self.assertIn("unreachable", html.lower())
        self.assertIn('name="phone"', html)

    def test_invalid_numbers_rejected(self):
        for bad in ("123", "5555555555", "012345"):
            res = self.client.post("/login", data={"phone": bad}, follow_redirects=True)
            html = res.get_data(as_text=True)
            self.assertIn("valid", html.lower())
            self.assertIn('name="phone"', html)

    @patch("requests.post")
    def test_two_sends_give_different_otps_old_fails(self, mock_post):
        mock_post.return_value = _ok_response()
        self.client.post("/login", data={"phone": "9876543210"}, follow_redirects=True)
        first = str(_payload(mock_post)["variables_values"])
        self.client.get("/change-number", follow_redirects=True)
        self.client.post("/login", data={"phone": "9876543210"}, follow_redirects=True)
        second = str(_payload(mock_post)["variables_values"])
        self.assertNotEqual(first, second)
        res = self.client.post("/login", data={"otp": first}, follow_redirects=True)
        html = res.get_data(as_text=True)
        self.assertIn("Wrong OTP", html)

    @patch("requests.post")
    def test_resend_before_30s_refused(self, mock_post):
        mock_post.return_value = _ok_response()
        self.client.post("/login", data={"phone": "9876543210"}, follow_redirects=True)
        res = self.client.post("/resend-otp", follow_redirects=True)
        html = res.get_data(as_text=True)
        self.assertIn("wait", html.lower())
        self.assertEqual(mock_post.call_count, 1)

    def test_missing_key_does_not_fallback(self):
        self.app.config["SMS_API_KEY"] = ""
        res = self.client.post("/login", data={"phone": "9876543210"}, follow_redirects=True)
        html = res.get_data(as_text=True)
        self.assertIn("SMS service is not configured", html)
        self.assertIn('name="phone"', html)


class TestDemoOtpStillWorks(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "demo.db"),
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret-key",
            "OTP_MODE": "demo",
            "DEMO_OTP": "1234",
            "SMS_API_KEY": "",
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        db.session.add(User(name="Asha", phone="9876543210", village_or_city="Bengaluru"))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    @patch("requests.post")
    def test_demo_mode_still_works(self, mock_post):
        res1 = self.client.get("/login")
        html1 = res1.get_data(as_text=True)
        self.assertIn("Demo mode", html1)
        self.assertIn("1234", html1)
        res2 = self.client.post("/login", data={"phone": "9876543210"}, follow_redirects=True)
        html2 = res2.get_data(as_text=True)
        self.assertIn("Demo mode", html2)
        self.assertIn("Fill OTP", html2)
        mock_post.assert_not_called()
        res3 = self.client.post("/login", data={"otp": "1234"}, follow_redirects=True)
        self.assertIn("Welcome, Asha!", res3.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()

"""SMS OTP tests — requests.post is always mocked; never send a real SMS.

The login flow now uses utils.sms, so these tests exercise the MSG91 Flow API
(the default SMS_PROVIDER). Provider keys are dummy values.
"""
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
    resp.content = b'{"type": "success", "message": "Message sent"}'
    resp.json.return_value = {"type": "success", "message": "Message sent"}
    resp.text = '{"type": "success"}'
    return resp


def _payload(mock_post):
    """MSG91 sends a JSON body: template id + one recipient with the OTP."""
    kwargs = mock_post.call_args.kwargs if mock_post.call_args.kwargs else {}
    return kwargs.get("json") or {}


def _otp_from(mock_post):
    return str(_payload(mock_post)["recipients"][0]["OTP"])


class TestRealOtpSms(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        # Force sms mode + a dummy key in the ENVIRONMENT: utils.otp reads
        # os.environ before app.config, so a shell OTP_MODE=demo would otherwise
        # leak in and stop requests.post from ever being called.
        self._env_saved = {}
        for _k in ("OTP_MODE", "SMS_PROVIDER", "MSG91_AUTH_KEY", "MSG91_TEMPLATE_ID"):
            self._env_saved[_k] = os.environ.get(_k)
        os.environ["OTP_MODE"] = "sms"
        os.environ["SMS_PROVIDER"] = "msg91"
        os.environ["MSG91_AUTH_KEY"] = "test-auth-key"
        os.environ["MSG91_TEMPLATE_ID"] = "test-template"
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret-key",
            "OTP_MODE": "sms",
            "SMS_PROVIDER": "msg91",
            "MSG91_AUTH_KEY": "test-auth-key",
            "MSG91_TEMPLATE_ID": "test-template",
            "OTP_LENGTH": 6,
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
        for _k, _v in self._env_saved.items():
            if _v is None:
                os.environ.pop(_k, None)
            else:
                os.environ[_k] = _v

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
        self.assertEqual(args[0], "https://control.msg91.com/api/v5/flow/")
        self.assertEqual(kwargs["headers"]["authkey"], "test-auth-key")
        self.assertEqual(kwargs["timeout"], 10)
        payload = kwargs["json"]
        self.assertEqual(payload["template_id"], "test-template")
        recipient = payload["recipients"][0]
        self.assertEqual(recipient["mobiles"], "919876543210")
        self.assertEqual(len(recipient["OTP"]), 6)
        self.assertTrue(recipient["OTP"].isdigit())

    @patch("requests.post")
    def test_sms_page_has_no_otp_and_no_demo_mode(self, mock_post):
        mock_post.return_value = _ok_response()
        res = self.client.post("/login", data={"phone": "9876543210"}, follow_redirects=True)
        html = res.get_data(as_text=True)
        self.assertNotIn("Demo mode", html)
        self.assertNotIn("Fill OTP", html)
        otp = _otp_from(mock_post)
        self.assertNotIn(otp, html)
        with self.client.session_transaction() as sess:
            self.assertNotIn("login_otp", sess)
            self.assertTrue(sess.get("otp_hash"))

    @patch("requests.post")
    def test_balance_error_shown(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b'{"type": "error", "message": "Insufficient balance"}'
        resp.json.return_value = {"type": "error", "message": "Insufficient balance"}
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
        first = _otp_from(mock_post)
        self.client.get("/change-number", follow_redirects=True)
        self.client.post("/login", data={"phone": "9876543210"}, follow_redirects=True)
        second = _otp_from(mock_post)
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
        for key in ("MSG91_AUTH_KEY", "MSG91_TEMPLATE_ID"):
            os.environ.pop(key, None)
            self.app.config[key] = ""
        res = self.client.post("/login", data={"phone": "9876543210"}, follow_redirects=True)
        html = res.get_data(as_text=True)
        self.assertIn("SMS service is not configured", html)
        self.assertIn('name="phone"', html)


class TestDemoOtpStillWorks(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        # Pin demo mode in the environment so a shell OTP_MODE=sms cannot leak in.
        self._env_saved = {}
        for _k in ("OTP_MODE",):
            self._env_saved[_k] = os.environ.get(_k)
        os.environ["OTP_MODE"] = "demo"
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
        for _k, _v in self._env_saved.items():
            if _v is None:
                os.environ.pop(_k, None)
            else:
                os.environ[_k] = _v

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


class TestConsoleOtpBanner(unittest.TestCase):
    """Console mode must tell the user the OTP is in the terminal."""

    def setUp(self):
        reset_rate_limits()
        self._env_saved = os.environ.get("OTP_MODE")
        os.environ["OTP_MODE"] = "console"
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "console.db"),
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret-key",
            "OTP_MODE": "console",
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
        if self._env_saved is None:
            os.environ.pop("OTP_MODE", None)
        else:
            os.environ["OTP_MODE"] = self._env_saved

    def test_console_mode_shows_dev_banner(self):
        banner = "Dev mode: OTP is printed in the server terminal."
        html = self.client.get("/login").get_data(as_text=True)
        self.assertIn(banner, html)
        res = self.client.post("/login", data={"phone": "9876543210"},
                               follow_redirects=True)
        html = res.get_data(as_text=True)
        self.assertIn(banner, html)
        self.assertIn("Change number", html)
        self.assertIn("Resend", html)
        self.assertNotIn("Demo mode", html)


if __name__ == "__main__":
    unittest.main()

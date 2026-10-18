"""Phase-1 tests for RentKart using Flask test client."""
import sys, os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(__file__))

import unittest
import tempfile
import shutil
from app import create_app
from models import db, User, Item
import config


class RentKartPhase1(unittest.TestCase):
    """Covers: app starts, OTP login, add item in every category, detail labels."""

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

    # ---- helpers ----
    def _login(self, phone="9999999999", name="Test User", village="TestVille"):
        """Complete the two-step mock-OTP login."""
        # Step 1: send phone
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        # Step 2: send OTP + new-user fields
        resp = self.client.post("/login", data={
            "otp": "1234",
            "name": name,
            "village_or_city": village,
        }, follow_redirects=True)
        return resp

    def _add_item(self, category, extra_attrs=None):
        """POST an item in the given category with optional dynamic attrs."""
        data = {
            "category": category,
            "title": f"Test {category} item",
            "description": "Automated test item",
            "price_per_day": "100",
            "deposit": "50",
            "late_fee_per_day": "10",
        }
        if extra_attrs:
            data.update(extra_attrs)
        return self.client.post("/items/add", data=data, follow_redirects=True)

    # ---- tests ----
    def test_01_app_starts(self):
        """The app responds on /."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"RentKart", resp.data)

    def test_02_login_with_otp(self):
        """New user can log in with OTP 1234."""
        resp = self._login()
        self.assertIn(b"Welcome", resp.data)
        user = User.query.filter_by(phone="9999999999").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.name, "Test User")

    def test_03_login_existing_user(self):
        """Existing user logs in without re-entering name."""
        self._login(phone="8888888888", name="Existing", village="OldTown")
        self.client.get("/logout", follow_redirects=True)
        # Login again – should not need name/village
        self.client.post("/login", data={"phone": "8888888888"}, follow_redirects=True)
        resp = self.client.post("/login", data={"otp": "1234"}, follow_redirects=True)
        self.assertIn(b"Welcome", resp.data)

    def test_04_add_item_all_categories(self):
        """An item can be added in every configured category."""
        self._login()
        categories = config.CATEGORIES
        for cat_key, cat_def in categories.items():
            # Build dynamic attr fields
            attrs = {}
            for f in cat_def["fields"]:
                key = f"attr_{f['name']}"
                if f["type"] == "checkbox":
                    attrs[key] = "on"
                elif f["type"] == "select" and f["options"]:
                    attrs[key] = f["options"][0]
                elif f["type"] == "number":
                    attrs[key] = "5"
                else:
                    attrs[key] = "test_value"
            resp = self._add_item(cat_key, attrs)
            self.assertEqual(resp.status_code, 200, f"Failed to add item for {cat_key}")

        # Verify count
        self.assertEqual(Item.query.count(), len(categories))

    def test_05_item_detail_shows_labels(self):
        """Item detail page shows category-specific field labels."""
        self._login()
        categories = config.CATEGORIES
        for cat_key, cat_def in categories.items():
            attrs = {}
            for f in cat_def["fields"]:
                key = f"attr_{f['name']}"
                if f["type"] == "checkbox":
                    attrs[key] = "on"
                elif f["type"] == "select" and f["options"]:
                    attrs[key] = f["options"][0]
                elif f["type"] == "number":
                    attrs[key] = "42"
                else:
                    attrs[key] = "sample"
            self._add_item(cat_key, attrs)

        items = Item.query.all()
        for item in items:
            resp = self.client.get(f"/items/{item.id}")
            self.assertEqual(resp.status_code, 200)
            cat_def = categories[item.category]
            for f in cat_def["fields"]:
                self.assertIn(
                    f["label"].encode(),
                    resp.data,
                    f"Label '{f['label']}' missing on detail page for {item.category}",
                )

    def test_06_invalid_otp_rejected(self):
        """Wrong OTP is rejected."""
        self.client.post("/login", data={"phone": "7777777777"}, follow_redirects=True)
        resp = self.client.post("/login", data={
            "otp": "0000",
            "name": "Bad",
            "village_or_city": "Nowhere",
        }, follow_redirects=True)
        self.assertIn(b"Invalid OTP", resp.data)

    def test_07_add_item_requires_login(self):
        """/items/add redirects to login when not authenticated."""
        resp = self.client.get("/items/add", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers.get("Location", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)

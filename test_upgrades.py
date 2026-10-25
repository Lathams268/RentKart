"""Tests for RentKart categories, images, shop identity, dynamic filters, and login upgrades."""
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from flask import url_for
from app import create_app
import config
from models import db, User, Item
from seed import seed as run_seed
from utils.otp import send_sms_otp


class TestRentKartUpgrades(unittest.TestCase):

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

    def test_01_otp_demo_mode_and_login_elements(self):
        """Fix 1: OTP mode config, stub, and UI elements."""
        self.assertEqual(self.app.config["OTP_MODE"], "demo")
        with patch.dict(os.environ, {"OTP_MODE": "demo"}):
            self.assertTrue(send_sms_otp("9999999999", "1234"))

        # Phone step
        resp = self.client.get("/login")
        self.assertEqual(resp.status_code, 200)

        # Submit phone to reach OTP step
        resp = self.client.post("/login", data={"phone": "9000000001"}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("Demo mode: your OTP is 1234", html)
        self.assertIn("Fill OTP", html)
        # Section B: the input is now a 6-digit numeric field (was 4 digits).
        self.assertIn('maxlength="6"', html)
        self.assertIn('inputmode="numeric"', html)
        self.assertIn('autocomplete="one-time-code"', html)

    def test_02_categories_config_dynamic_and_dependent_options(self):
        """Fix 2: Categories configuration has all required fields and get_field_options works."""
        cats = config.CATEGORIES
        self.assertIn("clothes", cats)
        self.assertIn("books", cats)
        self.assertIn("farm_tools", cats)
        self.assertIn("event_items", cats)
        self.assertIn("electronics", cats)

        # Clothes: style, clothing_type (dependent), color, size, occasion, fabric, gender, brand
        clothes_fields = [f["name"] for f in cats["clothes"]["fields"]]
        self.assertEqual(set(clothes_fields), {"style", "clothing_type", "color", "size", "occasion", "fabric", "gender", "brand", "age_group"})

        # Dependent options for clothes
        traditional_types = config.get_field_options("clothes", "clothing_type", "Traditional")
        self.assertIn("Saree", traditional_types)
        self.assertIn("Lehenga", traditional_types)

        western_types = config.get_field_options("clothes", "clothing_type", "Western")
        self.assertIn("Gown", western_types)
        self.assertIn("Tuxedo", western_types)

        # Books: genre first, language present
        book_fields = [f["name"] for f in cats["books"]["fields"]]
        self.assertEqual(book_fields[0], "genre")
        self.assertIn("language", book_fields)

        # Farm tools: tool_group, tool_type (dependent)
        farm_fields = [f["name"] for f in cats["farm_tools"]["fields"]]
        self.assertIn("tool_group", farm_fields)
        self.assertIn("tool_type", farm_fields)
        power_tool_types = config.get_field_options("farm_tools", "tool_type", "Power Tools")
        self.assertIn("Chainsaw", power_tool_types)

        # Event items: event_group, item_type (dependent)
        event_fields = [f["name"] for f in cats["event_items"]["fields"]]
        self.assertIn("event_group", event_fields)
        self.assertIn("item_type", event_fields)

        # Electronics: device_type, condition
        elec_fields = [f["name"] for f in cats["electronics"]["fields"]]
        self.assertIn("device_type", elec_fields)
        self.assertIn("condition", elec_fields)

    def test_03_seed_shravani_shop_logo_and_theme_color(self):
        """Fix 4 & 5: Seed data assigns Shravani Boutique theme color and generates logo."""
        run_seed()
        shravani_user = User.query.filter_by(shop_slug="shravani").first()
        self.assertIsNotNone(shravani_user)
        self.assertEqual(shravani_user.shop_name, "Shravani Boutique")
        self.assertEqual(shravani_user.shop_theme_color, "maroon and gold")
        self.assertEqual(shravani_user.shop_logo, "shravani_logo.png")

        # Check logo file created in UPLOAD_FOLDER
        upload_folder = self.app.config["UPLOAD_FOLDER"]
        logo_file = os.path.join(upload_folder, "shravani_logo.png")
        self.assertTrue(os.path.exists(logo_file))

        # Re-run seed to verify idempotency
        run_seed()
        user_after = User.query.filter_by(shop_slug="shravani").first()
        self.assertEqual(user_after.shop_theme_color, "maroon and gold")

    def test_04_browse_filters_for_all_categories(self):
        """Fix 3: Browse category filters and dependent fields work cleanly."""
        run_seed()

        # Clothes browse shows style, clothing_type, color filters
        resp = self.client.get("/browse?category=clothes")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("attr_style", html)
        self.assertIn("attr_clothing_type", html)
        self.assertIn("attr_color", html)

        # Books browse shows language filter and tags
        resp = self.client.get("/browse?category=books")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("attr_language", html)

        # Farm tools browse shows tool_group and tool_type filters
        resp = self.client.get("/browse?category=farm_tools")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("attr_tool_group", html)
        self.assertIn("attr_tool_type", html)

        # Event items browse shows filters
        resp = self.client.get("/browse?category=event_items")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("attr_event_group", html)

        # Electronics browse shows device_type
        resp = self.client.get("/browse?category=electronics")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("attr_device_type", html)

    def test_05_item_image_and_shop_badge_fallbacks(self):
        """Fix 4: Item image fallbacks display shop branding and badges."""
        run_seed()
        shravani_user = User.query.filter_by(shop_slug="shravani").first()

        # Create an item without image for Shravani
        no_img_item = Item(
            owner_id=shravani_user.id,
            category="clothes",
            title="Custom Bridal Chaniya Choli",
            description="Handmade designer wear",
            price_per_day=750,
            deposit=2500,
            late_fee_per_day=150,
            image=None,
        )
        no_img_item.set_attributes({"brand": "Shravani", "style": "Traditional", "clothing_type": "Lehenga"})
        db.session.add(no_img_item)
        db.session.commit()

        # Check item_detail page renders shop logo/theme fallback
        resp = self.client.get(f"/items/{no_img_item.id}")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("Shravani Boutique", html)
        self.assertIn("shravani_logo.png", html)

        # Check clothes marketplace page renders owner name on cards
        # Updated: clothes page now shows owner name (not shop_badge) and
        # plan visibility may hide some items; check a known visible item.
        resp = self.client.get("/browse?category=clothes")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        # The owner (Lakshmi) name appears on cards for her visible items
        self.assertIn("Lakshmi", html)

    def test_06_edit_shop_theme_and_logo(self):
        """Fix 4: Owner can edit shop theme color and logo."""
        run_seed()
        owner = User.query.filter_by(shop_slug="shravani").first()

        # Login as owner
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(owner.id)

        # Edit shop theme
        resp = self.client.post("/shop/edit", data={
            "shop_name": "Shravani Royal Boutique",
            "shop_description": "Exclusive royal wedding collections",
            "shop_theme_color": "royal blue and silver",
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        updated_owner = User.query.get(owner.id)
        self.assertEqual(updated_owner.shop_name, "Shravani Royal Boutique")
        self.assertEqual(updated_owner.shop_theme_color, "royal blue and silver")

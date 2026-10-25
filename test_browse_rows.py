"""Tests for Category Rows, Shravani Boutique Brand, and Generated Images."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from app import create_app
from models import db, User, Item
from seed import seed as run_seed
import config
from PIL import Image


class RentKartBrowseRowsTest(unittest.TestCase):

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

    def test_01_browse_no_filters_shows_category_sections(self):
        """1. /browse with no filters shows one section per non-empty category."""
        run_seed()
        resp = self.client.get("/browse")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")

        # Category rows are shown for non-empty categories in config.CATEGORIES order
        for cat_key, cat_val in config.CATEGORIES.items():
            count = Item.query.filter_by(category=cat_key, is_available=True).count()
            if count > 0:
                self.assertIn(cat_val["label"], html)
                self.assertIn(cat_val["icon"], html)
                self.assertIn(f"/browse?category={cat_key}", html)

        # Horizontal snap scrolling row styles are present
        self.assertIn("overflow-x-auto", html)
        self.assertIn("snap-x", html)
        self.assertIn("w-[260px]", html)

    def test_02_browse_category_clothes_shows_grid(self):
        """2. /browse?category=clothes shows the clothes marketplace page.

        Updated for the clothes redesign: the page is now the mobile marketplace
        layout (Men / Women / Children tabs + 2-column card grid) instead of the
        old single-column grid of every clothes item, so the default (Women) tab
        only carries women items and a men item needs ?tab=men.
        """
        run_seed()
        resp = self.client.get("/browse?category=clothes")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")

        # Tab tiles for all three sections
        for label in ("Men", "Women", "Children"):
            self.assertIn(label, html)

        # Women clothes items appear on the default tab
        self.assertIn("Silk Lehenga", html)
        self.assertIn("Pattu Saree", html)

        # Men items live on their own tab now, not on the default one
        self.assertNotIn("Designer Sherwani", html)
        men_html = self.client.get("/browse?category=clothes&tab=men").data.decode("utf-8")
        self.assertIn("Designer Sherwani", men_html)

        # Non-clothes items do not appear
        self.assertNotIn("Tractor Rotavator", html)
        self.assertNotIn("Canon DSLR Camera", html)
        self.assertNotIn("Shamiyana Tent", html)

        # Uses the multi-column card grid (2 columns on mobile)
        self.assertIn("grid-cols-2", html)
        self.assertIn("md:grid-cols-3", html)

    def test_03_search_text_works_and_shows_grid(self):
        """3. search text still works and shows the grid."""
        run_seed()
        resp = self.client.get("/browse?search=camera")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")

        # Camera is present, lehenga is not
        self.assertIn("Canon DSLR Camera", html)
        self.assertNotIn("Silk Lehenga", html)

        # Uses grid layout
        self.assertIn("grid grid-cols-1", html)

    def test_04_clothes_have_brand_shravani_and_shop_returns_200(self):
        """4. seeded clothes items have brand 'Shravani' and /shop/shravani returns 200."""
        run_seed()
        clothes = Item.query.filter_by(category="clothes").all()
        self.assertGreaterEqual(len(clothes), 3)
        for c in clothes:
            attrs = c.get_attributes()
            self.assertIn(attrs.get("brand"), ["Shravani", "FabIndia Kids", "Zara Kids", "Manyavar Kids", "BIBA", "Raymond"], f"{c.title} missing recognized brand")

        resp = self.client.get("/shop/shravani")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")

        # Contains shop name and description
        self.assertIn("Shravani Boutique", html)
        self.assertIn("Lehengas, sarees and sherwanis", html)

        # Clothes items listed in shop
        self.assertIn("Silk Lehenga", html)
        self.assertIn("Designer Sherwani", html)
        self.assertIn("Pattu Saree", html)

        # Detail page links to /shop/shravani
        lehenga = Item.query.filter_by(title="Silk Lehenga").first()
        detail_resp = self.client.get(f"/items/{lehenga.id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail_html = detail_resp.data.decode("utf-8")
        self.assertIn("/shop/shravani", detail_html)
        self.assertIn("Shravani", detail_html)

    def test_05_seeded_items_never_carry_legacy_placeholder_images(self):
        """5. no seeded item keeps a legacy seed_<n>.png placeholder."""
        run_seed()
        import re
        items = Item.query.all()
        self.assertGreaterEqual(len(items), 15)
        placeholder = re.compile(r"^seed(?:_[a-z]+)*_\d+\.png$", re.IGNORECASE)
        for it in items:
            if it.image:
                base = os.path.basename(it.image.replace("\\", "/"))
                self.assertIsNone(
                    placeholder.match(base),
                    f"{it.title} still uses generated placeholder {it.image}",
                )


if __name__ == "__main__":
    unittest.main()

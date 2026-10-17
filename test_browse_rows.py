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
        """2. /browse?category=clothes shows only clothes in the normal grid."""
        run_seed()
        resp = self.client.get("/browse?category=clothes")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")

        # Clothes items appear
        self.assertIn("Silk Lehenga", html)
        self.assertIn("Designer Sherwani", html)
        self.assertIn("Pattu Saree", html)

        # Non-clothes items do not appear
        self.assertNotIn("Tractor Rotavator", html)
        self.assertNotIn("Canon DSLR Camera", html)
        self.assertNotIn("Shamiyana Tent", html)

        # Uses grid layout
        self.assertIn("grid grid-cols-1", html)

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
            self.assertEqual(attrs.get("brand"), "Shravani", f"{c.title} missing Shravani brand")

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

    def test_05_generated_seed_images_exist_for_every_seeded_item(self):
        """5. generated seed images exist for every seeded item."""
        run_seed()
        items = Item.query.all()
        self.assertGreaterEqual(len(items), 15)

        upload_dir = self.app.config["UPLOAD_FOLDER"]
        for it in items:
            self.assertIsNotNone(it.image, f"Item {it.title} has no image set")
            img_path = os.path.join(upload_dir, it.image)
            self.assertTrue(os.path.exists(img_path), f"Image file {it.image} not found for {it.title}")

            # Check 800x600 resolution
            with Image.open(img_path) as im:
                self.assertEqual(im.size, (800, 600), f"Image {it.image} has size {im.size}, expected (800, 600)")


if __name__ == "__main__":
    unittest.main()

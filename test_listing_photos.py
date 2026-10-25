"""Listing photo tests: upload -> resize -> serve, gallery markup, seed coverage.

Owner uploads are written to a throw-away folder inside ``static/media`` so the
files are served exactly like production (``/static/media/...``) and cleaned up
after each test. Seed photo tests use the committed ``static/seed_images`` set.
"""
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from PIL import Image

from app import create_app
from models import db, Item, User
from seed import seed as run_seed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEED_DIR = os.path.join(BASE_DIR, "static", "seed_images")


def _blob(fmt="JPEG", size=(1200, 900), color=(180, 60, 60)):
    """In-memory image bytes for a multipart upload."""
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format=fmt)
    return buf.getvalue()


class ListingPhotoTest(unittest.TestCase):
    def setUp(self):
        os.makedirs(os.path.join(BASE_DIR, "static", "media"), exist_ok=True)
        # Keep uploads under /static so utils.illustrations resolves them, but
        # in a folder unique to this test.
        self.media_dir = tempfile.mkdtemp(
            prefix="test_photos_", dir=os.path.join(BASE_DIR, "static", "media"))
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
            "MEDIA_FOLDER": self.media_dir,
            "MEDIA_BACKEND": "local",
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "photo-test-secret",
            "OTP_MODE": "console",
            "DEMO_OTP": "1234",
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.owner = User(name="Photo Owner", phone="9111111111",
                          village_or_city="Bengaluru", lat=12.9716, lng=77.5946)
        db.session.add(self.owner)
        db.session.commit()
        self._login()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.media_dir, ignore_errors=True)

    # -- helpers ------------------------------------------------------------
    def _login(self):
        self.client.get("/logout")
        self.client.post("/login", data={"phone": self.owner.phone})
        return self.client.post("/login", data={
            "otp": "1234", "name": self.owner.name,
            "village_or_city": self.owner.village_or_city,
        }, follow_redirects=True)

    def _add_listing(self, title, files, extra=None):
        data = {
            "category": "clothes",
            "title": title,
            "description": "Photo upload regression listing",
            "price_per_day": "499",
            "deposit": "1000",
            "late_fee_per_day": "50",
            "tags": "dress,test",
            "photos": files,
        }
        if extra:
            data.update(extra)
        return self.client.post("/items/add", data=data,
                                content_type="multipart/form-data",
                                follow_redirects=True)

    def _stored_path(self, key):
        return os.path.join(BASE_DIR, "static", key.replace("/", os.sep))

    # -- tests --------------------------------------------------------------
    def test_01_upload_two_photos_stores_large_and_thumb(self):
        resp = self._add_listing("Photo Test Dress", [
            (io.BytesIO(_blob("JPEG", (1400, 1000))), "front.jpg"),
            (io.BytesIO(_blob("PNG", (900, 700), (40, 90, 160))), "back.png"),
        ])
        self.assertEqual(resp.status_code, 200)

        item = Item.query.filter_by(title="Photo Test Dress").first()
        self.assertIsNotNone(item)
        keys = item.get_images()
        self.assertEqual(len(keys), 2)
        self.assertEqual(item.image, keys[0])

        for key in keys:
            self.assertTrue(key.startswith("media/test_photos_"), key)
            large_path = self._stored_path(key)
            thumb_path = large_path[:-4] + "_thumb.jpg"
            self.assertTrue(os.path.isfile(large_path), large_path)
            self.assertTrue(os.path.isfile(thumb_path), thumb_path)

        large = Image.open(self._stored_path(keys[0]))
        thumb = Image.open(self._stored_path(keys[0])[:-4] + "_thumb.jpg")
        self.assertLessEqual(max(large.size), 1600)
        self.assertLessEqual(max(thumb.size), 600)
        self.assertLess(thumb.size[0], large.size[0])
        self.assertEqual(large.format, "JPEG")
        self.assertEqual(thumb.format, "JPEG")

        html = resp.get_data(as_text=True)
        self.assertIn("Item listed successfully", html)
        self.assertIn("/static/" + keys[0], html)      # cover in the gallery
        self.assertIn('id="lightbox"', html)           # zoom lightbox
        self.assertIn("gallery-thumb", html)           # thumbnail strip
        self.assertIn("data-photos", html)             # gallery data for JS
        self.assertIn('loading="lazy"', html)

    def test_02_webp_and_png_are_reencoded_to_jpeg(self):
        try:
            webp = _blob("WEBP", (800, 600), (30, 120, 60))
        except Exception:  # noqa: BLE001 - Pillow built without WebP
            self.skipTest("Pillow build does not support WebP")
        resp = self._add_listing("WebP Photo Listing", [
            (io.BytesIO(webp), "look.webp"),
            (io.BytesIO(_blob("PNG", (700, 500), (90, 90, 90))), "plain.png"),
        ])
        self.assertEqual(resp.status_code, 200)
        item = Item.query.filter_by(title="WebP Photo Listing").first()
        self.assertIsNotNone(item)
        keys = item.get_images()
        self.assertEqual(len(keys), 2)
        for key in keys:
            self.assertTrue(key.endswith(".jpg"), key)
            with Image.open(self._stored_path(key)) as saved:
                self.assertEqual(saved.format, "JPEG")

    def test_03_invalid_file_is_rejected_with_clear_message(self):
        resp = self._add_listing("Broken Photo Listing", [
            (io.BytesIO(b"this is not an image at all"), "fake.jpg"),
        ])
        html = resp.get_data(as_text=True)
        self.assertIn("not a valid image", html)
        self.assertIsNone(Item.query.filter_by(title="Broken Photo Listing").first())

    def test_04_oversize_file_is_rejected(self):
        big = b"\xff\xd8\xff\xe0" + b"0" * (5 * 1024 * 1024 + 2048)
        resp = self._add_listing("Huge Photo Listing", [
            (io.BytesIO(big), "huge.jpg"),
        ])
        html = resp.get_data(as_text=True)
        self.assertIn("larger than 5 MB", html)
        self.assertIsNone(Item.query.filter_by(title="Huge Photo Listing").first())

    def test_05_at_most_six_photos_are_kept(self):
        files = [(io.BytesIO(_blob("JPEG", (320, 240), (i * 30, 80, 120))),
                  f"p{i}.jpg") for i in range(7)]
        resp = self._add_listing("Seven Photo Listing", files)
        html = resp.get_data(as_text=True)
        self.assertIn("Only the first 6 photos were kept", html)
        item = Item.query.filter_by(title="Seven Photo Listing").first()
        self.assertIsNotNone(item)
        self.assertEqual(len(item.get_images()), 6)
        self.assertEqual(item.image, item.get_images()[0])

    def test_06_edit_keeps_ticked_photos_and_can_clear_all(self):
        self._add_listing("Editable Photo Listing", [
            (io.BytesIO(_blob("JPEG", (900, 700), (200, 30, 30))), "one.jpg"),
            (io.BytesIO(_blob("JPEG", (900, 700), (30, 30, 200))), "two.jpg"),
        ])
        item = Item.query.filter_by(title="Editable Photo Listing").first()
        self.assertIsNotNone(item)
        keys = item.get_images()
        self.assertEqual(len(keys), 2)

        # Keep only the second photo: it becomes the new cover.
        self.client.post(f"/items/{item.id}/edit", data={
            "category": "clothes",
            "title": item.title,
            "description": item.description or "",
            "price_per_day": "500",
            "deposit": "1000",
            "late_fee_per_day": "50",
            "keep_image": [keys[1]],
            "photos_managed": "1",
            "is_available": "on",
        }, follow_redirects=True)
        item = Item.query.get(item.id)
        self.assertEqual(item.get_images(), [keys[1]])
        self.assertEqual(item.image, keys[1])

        # Untick everything: the listing goes back to the placeholder.
        self.client.post(f"/items/{item.id}/edit", data={
            "category": "clothes",
            "title": item.title,
            "description": item.description or "",
            "price_per_day": "500",
            "deposit": "1000",
            "late_fee_per_day": "50",
            "photos_managed": "1",
            "is_available": "on",
        }, follow_redirects=True)
        item = Item.query.get(item.id)
        self.assertEqual(item.get_images(), [])
        self.assertIsNone(item.image)

    def test_07_seed_gives_every_category_five_real_photos(self):
        run_seed()
        minimum = {"clothes": 5, "electronics": 5, "farm_tools": 5,
                   "bikes": 5, "event_items": 5, "books": 5}
        for category, need in minimum.items():
            items = Item.query.filter_by(category=category).all()
            with_photos = [i for i in items if str(i.image or "").startswith("seed_images/")]
            self.assertGreaterEqual(
                len(with_photos), need,
                f"{category}: {len(with_photos)} items with a real photo, need {need}")

        # Cameras and tents are named sub-categories in the brief.
        cameras = [i for i in Item.query.filter_by(category="electronics").all()
                   if "camera" in i.title.lower()]
        tents = [i for i in Item.query.filter_by(category="event_items").all()
                 if "tent" in i.title.lower()]
        self.assertGreaterEqual(len(cameras), 5, "cameras with photos")
        self.assertGreaterEqual(len(tents), 5, "tents with photos")

        # Every demo-category listing: cover on disk, gallery stored, no drawing.
        for category in minimum:
            for item in Item.query.filter_by(category=category).all():
                self.assertTrue(str(item.image or "").startswith("seed_images/"),
                                f"{item.title} cover={item.image!r}")
                cover = os.path.join(BASE_DIR, "static", item.image.replace("/", os.sep))
                self.assertTrue(os.path.isfile(cover), cover)
                self.assertGreaterEqual(len(item.get_images()), 3, item.title)

    def test_08_search_for_dress_returns_dress_items(self):
        run_seed()
        resp = self.client.get("/browse?q=dress")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        for title in ("Wine Cocktail Party Dress", "Floral Summer Midi Dress",
                      "Girls Unicorn Party Frock Dress"):
            self.assertIn(title, html)
        self.assertNotIn("Tractor Rotavator", html)

        # Cards use the real seed photo, lazy loading and object-fit: cover.
        self.assertIn("/static/seed_images/clothes/", html)
        self.assertIn('loading="lazy"', html)
        self.assertIn("object-cover", html)

    def test_09_item_without_photo_falls_back_to_art(self):
        from utils.illustrations import item_picture

        item = Item(owner_id=self.owner.id, category="clothes",
                    title="No Photo Lehenga", description="No photos uploaded",
                    price_per_day=100, deposit=500, late_fee_per_day=10)
        item.set_attributes({"style": "Traditional", "clothing_type": "Lehenga"})
        db.session.add(item)
        db.session.commit()

        pic = item_picture(item)
        self.assertNotEqual(pic["kind"], "photo")
        self.assertIn(pic["kind"], ("illustration", "category"))

        resp = self.client.get(f"/items/{item.id}")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("/art/", html)
        self.assertNotIn("/static/seed_images/", html)


if __name__ == "__main__":
    unittest.main()

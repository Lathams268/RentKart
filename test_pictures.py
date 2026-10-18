"""Tests for the item picture lookup order in utils.illustrations.item_picture:
uploaded photo > demo_photos/<slug> > stock/<cat>/<subcat> > stock/<cat>/default
> drawing. Real photos use cover; legacy seed_<n>.png never counts as a photo."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from app import create_app
from models import db, User, Item
import utils.illustrations as ill
from utils.illustrations import item_picture, ensure_illustrations, item_slug, BASE_DIR

SPIRITUAL = "Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)"


class PictureResolutionTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # Point the demo-photo lookup at an isolated temp folder.
        self._orig_photos = ill.DEMO_PHOTOS_DIR
        self.photos = os.path.join(self.tmp, "demo_photos")
        os.makedirs(self.photos, exist_ok=True)
        ill.DEMO_PHOTOS_DIR = self.photos

        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
            "WTF_CSRF_ENABLED": False,
        })
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        ensure_illustrations()
        self.owner = User(name="Tester", phone="8000000099", village_or_city="Bengaluru")
        db.session.add(self.owner)
        db.session.commit()

    def tearDown(self):
        ill.DEMO_PHOTOS_DIR = self._orig_photos
        for name in ("real_photo.jpg", "uploaded_test.jpg"):
            p = os.path.join(BASE_DIR, "static", "uploads", name)
            if os.path.exists(p):
                os.remove(p)
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- helpers ---
    def _make_item(self, title, category, attrs=None, image=None):
        it = Item(owner_id=self.owner.id, category=category, title=title,
                  description="demo", price_per_day=10, deposit=100,
                  late_fee_per_day=1, image=image)
        it.set_attributes(attrs or {})
        db.session.add(it)
        db.session.commit()
        return it

    def _write(self, rel_path, data=b"\xff\xd8\xff\xe0fakeimagebytes"):
        full = os.path.join(self.photos, rel_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as fh:
            fh.write(data)
        return full

    def _spiritual_book(self, title="Bhagavad Gita As It Is", image=None):
        return self._make_item(title, "books", {"genre": SPIRITUAL}, image=image)

    # --- legacy placeholder / drawings ---
    def test_01_seed_placeholder_image_falls_back_to_illustration(self):
        it = self._make_item("Canon DSLR Camera", "electronics",
                             {"device_type": "Camera"}, image="seed_15.png")
        pic = item_picture(it)
        self.assertNotIn("seed_15", pic["path"])
        self.assertTrue(pic["path"].startswith("illustrations/"), pic["path"])
        self.assertEqual(pic["kind"], "illustration")

    def test_03_books_inspirational_genre_uses_motivation_drawing(self):
        it = self._make_item("The Monk Who Sold His Ferrari", "books",
                             {"genre": "Inspirational / Motivation"})
        pic = item_picture(it)
        self.assertEqual(pic["kind"], "illustration")
        self.assertTrue(pic["path"].endswith("illustrations/motivation.svg"), pic["path"])

    def test_07_no_files_at_all_uses_drawing(self):
        """With no photo files present the sub-category drawing is used."""
        it = self._spiritual_book()
        pic = item_picture(it)
        self.assertEqual(pic["kind"], "illustration")
        self.assertTrue(pic["path"].endswith("illustrations/spiritual.svg"), pic["path"])

    # --- stock photo (step 3) ---
    def test_04_stock_photo_used_for_spiritual_book(self):
        self._write("stock/books/spiritual.jpg")
        it = self._spiritual_book()
        pic = item_picture(it)
        self.assertEqual(pic["kind"], "stock")
        self.assertTrue(pic["path"].endswith("stock/books/spiritual.jpg"), pic["path"])
        self.assertEqual(pic["fit"], "cover")

    def test_09_stock_default_used_when_no_subcat_photo(self):
        self._write("stock/books/default.jpg")
        it = self._spiritual_book()
        pic = item_picture(it)
        self.assertEqual(pic["kind"], "stock")
        self.assertTrue(pic["path"].endswith("stock/books/default.jpg"), pic["path"])

    # --- slug photo (step 2) beats stock (step 3/4) ---
    def test_05_slug_photo_beats_stock_photo(self):
        self._write("stock/books/spiritual.jpg")
        slug = "bhagavad-gita-as-it-is"
        self._write(slug + ".jpg")
        it = self._spiritual_book()
        pic = item_picture(it)
        self.assertEqual(pic["kind"], "demo")
        self.assertTrue(pic["path"].endswith(slug + ".jpg"), pic["path"])

    # --- uploaded photo (step 1) beats everything ---
    def test_02_and_06_uploaded_photo_beats_slug_and_stock(self):
        self._write("stock/books/spiritual.jpg")
        self._write("bhagavad-gita-as-it-is.jpg")
        upload = os.path.join(BASE_DIR, "static", "uploads", "uploaded_test.jpg")
        with open(upload, "wb") as fh:
            fh.write(b"\xff\xd8\xff\xe0uploadedrealphoto")
        it = self._spiritual_book(image="uploaded_test.jpg")
        pic = item_picture(it)
        self.assertEqual(pic["kind"], "photo")
        self.assertIn("uploads/uploaded_test.jpg", pic["path"])
        self.assertEqual(pic["fit"], "cover")

    def test_02_real_uploaded_photo_wins_over_illustration(self):
        rel = os.path.join(BASE_DIR, "static", "uploads", "real_photo.jpg")
        with open(rel, "wb") as fh:
            fh.write(b"\xff\xd8\xff\xe0realjpegbytes")
        it = self._make_item("Silk Lehenga", "clothes",
                             {"clothing_type": "Lehenga"}, image="real_photo.jpg")
        pic = item_picture(it)
        self.assertEqual(pic["kind"], "photo")
        self.assertIn("uploads/real_photo.jpg", pic["path"])

    # --- every accepted extension works ---
    def test_08_extensions_jpg_png_webp(self):
        for ext in (".jpg", ".png", ".webp"):
            with self.subTest(ext=ext):
                # clean any previous stock file
                for e in ill.PHOTO_EXTS:
                    p = os.path.join(self.photos, "stock", "books", "spiritual" + e)
                    if os.path.exists(p):
                        os.remove(p)
                self._write("stock/books/spiritual" + ext)
                it = self._spiritual_book()
                pic = item_picture(it)
                self.assertEqual(pic["kind"], "stock")
                self.assertTrue(pic["path"].endswith("spiritual" + ext), pic["path"])


if __name__ == "__main__":
    unittest.main()

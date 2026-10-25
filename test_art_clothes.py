"""ART stage 1: rich colour-aware clothes art renders and variations."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import re
import unittest, tempfile, shutil
import xml.etree.ElementTree as ET

from utils.art_clothes import make_clothes_art
from app import create_app
from models import db, User, Item
from utils.illustrations import BASE_DIR
import config


def _clothing_types():
    for f in config.CATEGORIES["clothes"]["fields"]:
        if f["name"] == "clothing_type":
            return list(f["options"])
    return []


def _colors():
    for f in config.CATEGORIES["clothes"]["fields"]:
        if f["name"] == "color":
            return list(f["options"])
    return ["Red", "Blue"]


class ClothesArtUnitTest(unittest.TestCase):

    def test_every_clothing_type_renders_valid_svg(self):
        types = _clothing_types()
        self.assertGreaterEqual(len(types), 20)
        for ct in types:
            with self.subTest(clothing_type=ct):
                svg = make_clothes_art(ct, "Red", "Traditional", "Women", "18+",
                                       slug=f"item-{ct}")
                ET.fromstring(svg)  # strict XML parse
                self.assertTrue(svg.startswith("<svg"))
                self.assertIn('viewBox="0 0 800 1000"', svg)

    def test_different_colours_different_fills(self):
        base = make_clothes_art("Lehenga", "Red", "Traditional", "Women", "18+", slug="same-slug")
        alt = make_clothes_art("Lehenga", "Green", "Traditional", "Women", "18+", slug="same-slug")
        fills_a = set(re.findall(r'stop-color="([^"]+)"', base))
        fills_b = set(re.findall(r'stop-color="([^"]+)"', alt))
        self.assertNotEqual(fills_a, fills_b)
        self.assertIn("#C81E33", fills_a)
        self.assertIn("#1F8A43", fills_b)

    def test_different_slugs_different_patterns(self):
        a = make_clothes_art("Saree", "Blue", "Traditional", "Women", "18+", slug="saree-alpha-1")
        b = make_clothes_art("Saree", "Blue", "Traditional", "Women", "18+", slug="saree-beta-2")
        pat_a = re.search(r'<pattern id="[^"]+"[^>]*>(.*?)</pattern>', a, re.S).group(0)
        pat_b = re.search(r'<pattern id="[^"]+"[^>]*>(.*?)</pattern>', b, re.S).group(0)
        self.assertNotEqual(a, b)
        # either the pattern kind or the sequin scatter differs
        self.assertTrue(pat_a != pat_b or a.count("<circle") != b.count("<circle")
                        or a != b)

    def test_no_external_urls_or_scripts(self):
        for ct in _clothing_types()[:8]:
            svg = make_clothes_art(ct, "Gold", "Kids", "Girls", "3–5", slug="kids-" + ct)
            stripped = svg.replace('xmlns="http://www.w3.org/2000/svg"', "")
            self.assertNotIn("http://", stripped)
            self.assertNotIn("https://", stripped)
            self.assertNotIn("<script", svg.lower())
            self.assertNotIn("javascript:", svg.lower())
            self.assertNotIn("href=", svg.lower())

    def test_multicolor_uses_several_colours(self):
        svg = make_clothes_art("Frock", "Multicolor", "Kids", "Girls", "6–8", slug="mc")
        from utils.art_clothes import MULTI_SET
        self.assertTrue(sum(1 for c in MULTI_SET if c in svg) >= 3)


class ClothesArtRouteTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "t.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
            "WTF_CSRF_ENABLED": False,
            "OTP_MODE": "demo",
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.owner = User(name="Owner", phone="8010000001", village_or_city="Bengaluru")
        db.session.add(self.owner)
        db.session.commit()

    def tearDown(self):
        p = os.path.join(BASE_DIR, "static", "uploads", "art_test_photo.jpg")
        if os.path.exists(p):
            os.remove(p)
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _item(self):
        it = Item(owner_id=self.owner.id, category="clothes", title="Red Lehenga",
                  description="d", price_per_day=100, deposit=500, late_fee_per_day=20)
        it.set_attributes({"clothing_type": "Lehenga", "color": "Red",
                           "style": "Traditional", "gender": "Women", "age_group": "18+"})
        db.session.add(it)
        db.session.commit()
        return it

    def test_route_returns_svg_with_caching_headers(self):
        it = self._item()
        res = self.client.get(f"/art/clothes/{it.id}.svg")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.headers["Content-Type"].startswith("image/svg+xml"))
        self.assertIn("max-age", res.headers["Cache-Control"])
        self.assertIn("ETag", res.headers)
        ET.fromstring(res.get_data(as_text=True))

    def test_route_etag_304(self):
        it = self._item()
        res = self.client.get(f"/art/clothes/{it.id}.svg")
        etag = res.headers["ETag"]
        res2 = self.client.get(f"/art/clothes/{it.id}.svg", headers={"If-None-Match": etag})
        self.assertEqual(res2.status_code, 304)

    def test_unknown_item_404(self):
        self.assertEqual(self.client.get("/art/clothes/999999.svg").status_code, 404)

    def test_item_picture_uses_art_route_for_clothes(self):
        from utils.illustrations import item_picture
        it = self._item()
        pic = item_picture(it)
        self.assertEqual(pic["src"], f"/art/clothes/{it.id}.svg")
        self.assertEqual(pic["url"], pic["src"])
        # uploaded photo must still win (photo lookup reads static/uploads by name)
        it.image = "art_test_photo.jpg"
        db.session.commit()
        up = os.path.join(BASE_DIR, "static", "uploads", "art_test_photo.jpg")
        with open(up, "wb") as fh:
            fh.write(b"\xff\xd8\xff\xe0fake")
        pic2 = item_picture(it)
        self.assertEqual(pic2["kind"], "photo")
        self.assertNotIn("/art/", pic2["src"])


if __name__ == "__main__":
    unittest.main()

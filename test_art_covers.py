"""ART stage 3: generated book covers, /art/cover route, escaping and fitting."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import re
import unittest, tempfile, shutil
import xml.etree.ElementTree as ET

from utils.art_covers import make_cover_svg, fit_title, genre_key
from app import create_app
from models import db, User, Item
import config


def _genres():
    for f in config.CATEGORIES["books"]["fields"]:
        if f["name"] == "genre":
            return list(f["options"])
    return []


class CoverUnitTest(unittest.TestCase):

    def test_every_genre_renders_valid_cover(self):
        genres = _genres()
        self.assertGreaterEqual(len(genres), 12)
        for g in genres:
            with self.subTest(genre=g):
                svg = make_cover_svg("Midnight Lantern", "K. Ramesh", g,
                                     "English", slug="book-" + genre_key(g))
                root = ET.fromstring(svg)
                self.assertEqual(root.get("viewBox"), "0 0 600 900")
                self.assertIn("<text", svg)          # title present
                self.assertGreater(len(list(root.iter())), 15)

    def test_indian_language_titles(self):
        for title, lang in (("అందరికీ ప్రణామం", "Telugu"),
                            ("मोहत्याग", "Hindi"),
                            ("ನುಡಿಯ ಕಲೆ", "Kannada")):
            with self.subTest(language=lang):
                svg = make_cover_svg(title, "ರಾಷ್ಟ್ರಕವಿ", "Poetry", lang, "sc-" + lang)
                ET.fromstring(svg)
                self.assertIn(title, svg)
                self.assertIn("Noto Sans Telugu", svg)
                self.assertIn("Noto Sans Devanagari", svg)
                self.assertIn("Noto Sans Kannada", svg)

    def test_dangerous_titles_are_escaped(self):
        evil = '<script>alert(1)</script> & "quotes"'
        svg = make_cover_svg(evil, "A&B", "Fiction", "English", "ev")
        ET.fromstring(svg)  # still well-formed
        self.assertNotIn("<script>", svg)
        self.assertIn("&amp;", svg)
        self.assertIn("&quot;", svg)

    def test_long_title_wrapped_to_four_lines(self):
        long_title = " ".join("approximately" if i % 2 else "wordmark" for i in range(28))
        size, lines = fit_title(long_title)
        self.assertLessEqual(len(lines), 4)
        svg = make_cover_svg(long_title, "X", "Education / Exam Prep", "English", "long")
        n = len(re.findall(r'<text [^>]*font-weight="800"', svg))
        self.assertLessEqual(n, 4)
        self.assertLessEqual(size, 58)

    def test_no_external_urls(self):
        svg = make_cover_svg("T", "A", "Comedy / Humor", "English", "c")
        stripped = svg.replace('xmlns="http://www.w3.org/2000/svg"', "")
        self.assertNotIn("http://", stripped)
        self.assertNotIn("https://", stripped)
        self.assertNotIn("href=", svg.lower())

    def test_slug_gives_deterministic_variants(self):
        a = make_cover_svg("Same", "Auth", "Fiction", "English", "slug-one")
        b = make_cover_svg("Same", "Auth", "Fiction", "English", "slug-one")
        c = make_cover_svg("Same", "Auth", "Fiction", "English", "slug-two")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)  # texture stripes differ


class CoverRouteTest(unittest.TestCase):

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
        self.owner = User(name="Owner", phone="8010000003", village_or_city="Bengaluru")
        db.session.add(self.owner)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _book(self, title="Chintu's Big Day", genre="Children", author="R. Kai",
              language="English"):
        it = Item(owner_id=self.owner.id, category="books", title=title,
                  description="d", price_per_day=40, deposit=200, late_fee_per_day=10)
        it.set_attributes({"genre": genre, "author": author, "language": language})
        db.session.add(it)
        db.session.commit()
        return it

    def test_cover_route_headers_and_etag(self):
        it = self._book()
        res = self.client.get(f"/art/cover/{it.id}.svg")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.headers["Content-Type"].startswith("image/svg+xml"))
        self.assertIn("max-age", res.headers["Cache-Control"])
        etag = res.headers["ETag"]
        res2 = self.client.get(f"/art/cover/{it.id}.svg", headers={"If-None-Match": etag})
        self.assertEqual(res2.status_code, 304)
        ET.fromstring(res.get_data(as_text=True))

    def test_cover_route_escapes_title_in_response(self):
        it = self._book(title='<script>evil & "quoted"</script>')
        res = self.client.get(f"/art/cover/{it.id}.svg")
        body = res.get_data(as_text=True)
        self.assertNotIn("<script>evil", body)
        ET.fromstring(body)

    def test_unknown_item_404(self):
        self.assertEqual(self.client.get("/art/cover/999999.svg").status_code, 404)

    def test_item_picture_uses_cover_route_for_books(self):
        from utils.illustrations import item_picture
        it = self._book()
        pic = item_picture(it)
        self.assertEqual(pic["src"], f"/art/cover/{it.id}.svg")
        # kind/path stay the stable illustration fallback (old behaviour kept)
        self.assertEqual(pic["kind"], "illustration")


if __name__ == "__main__":
    unittest.main()

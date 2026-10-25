"""Search and listing visibility (section C + E).

Unit tests for utils/search.py (case-insensitive, partial, fuzzy, tags,
category labels) and HTTP tests for /browse: "dress" / "Dress" / "dres" /
"party dress" all find the dress, filters + sorting work, and the empty state
replaces the old silent "not found".
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from models import db, Item, User
from utils.search import (MATCH_THRESHOLD, keyword_category, normalize,
                          score_item, search_items, stem, tokens)


class BrowseSearch(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "OTP_MODE": "console",
            "PAYMENT_MODE": "mock",
            "SECRET_KEY": "search-tests",
            "SQLALCHEMY_DATABASE_URI":
                "sqlite:///" + os.path.join(self.tmp, "search.db").replace("\\", "/"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.pune = User(name="Pune Owner", phone="9000000001",
                         phone_e164="+919000000001", village_or_city="Pune",
                         role="owner", lat=18.52, lng=73.85)
        self.mumbai = User(name="Mumbai Owner", phone="9000000002",
                           phone_e164="+919000000002", village_or_city="Mumbai",
                           role="owner", lat=19.07, lng=72.87)
        db.session.add_all([self.pune, self.mumbai])
        db.session.commit()

        self.dress = self._item(
            self.pune, "clothes", "Floral Summer Midi Dress", 800, 500,
            description="Flowy midi dress for parties and brunches.",
            tags="dress, party, women, midi")
        self.sherwani = self._item(
            self.pune, "clothes", "Royal Wedding Sherwani", 2500, 2000,
            description="Hand-embroidered sherwani with dupatta.",
            tags="sherwani, wedding, groom")
        self.camera = self._item(
            self.pune, "electronics", "Space Grey DSLR Camera", 1500, 3000,
            description="Great camera for weddings and travel vlogs.",
            tags="photography, dslr")
        self.bike = self._item(
            self.pune, "bikes", "Mountain Bike 21-Speed", 400, 1000,
            description="Trail-ready bicycle with helmet included.",
            tags="cycle, adventure")
        self.tent = self._item(
            self.pune, "tents", "Camping Dome Tent 4 Person", 600, 800,
            description="Waterproof tent for weekend camping.",
            tags="camping, outdoor")
        self.point_and_shoot = self._item(
            self.mumbai, "electronics", "Budget Point & Shoot Camera", 300, 500,
            description="Small camera for day trips.",
            tags="photography, compact")
        db.session.commit()

        self.items = [self.dress, self.sherwani, self.camera, self.bike,
                      self.tent, self.point_and_shoot]

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _item(self, owner, category, title, price, deposit, description="",
              tags=""):
        item = Item(owner_id=owner.id, category=category, title=title,
                    description=description, price_per_day=price,
                    deposit=deposit, late_fee_per_day=50.0,
                    delivery_available=False, cod_available=True,
                    tags=tags, lat=owner.lat, lng=owner.lng)
        item.set_attributes({})
        db.session.add(item)
        return item

    def _titles(self, query):
        return [item.title for item in search_items(self.items, query)]

    # -- 1. text normalization helpers ------------------------------------
    def test_01_normalize_stem_tokens(self):
        self.assertEqual(normalize("  Party  DRESS! "), "party dress")
        self.assertEqual(normalize("Point & Shoot"), "point and shoot")
        self.assertEqual(stem("dresses"), "dress")
        self.assertEqual(stem("cameras"), "camera")
        self.assertEqual(stem("accessories"), "accessory")
        self.assertEqual(tokens("Rent a dress for the party"),
                         ["dress", "party"])          # stopwords dropped
        self.assertEqual(keyword_category("dress"), "clothes")
        self.assertEqual(keyword_category("party dress"), "clothes")

    # -- 2. the reported bug: "dress", "Dress", "dres", "party dress" -----
    def test_02_dress_variants_all_match(self):
        for query in ("dress", "Dress", "DRESS", "dres", "dresse", "party dress"):
            self.assertIn("Floral Summer Midi Dress", self._titles(query), query)

    # -- 3. description, tags and category are searchable ------------------
    def test_03_matches_description_tags_and_category(self):
        self.assertIn("Budget Point & Shoot Camera", self._titles("camera"))
        wedding_hits = self._titles("wedding")
        self.assertIn("Royal Wedding Sherwani", wedding_hits)     # title + tag
        self.assertIn("Space Grey DSLR Camera", wedding_hits)     # description
        self.assertIn("Royal Wedding Sherwani", self._titles("groom"))  # tag only
        clothes_hits = self._titles("clothes")                    # category label
        self.assertIn("Floral Summer Midi Dress", clothes_hits)
        self.assertIn("Royal Wedding Sherwani", clothes_hits)
        self.assertNotIn("Camping Dome Tent 4 Person", clothes_hits)

    # -- 4. multi-word queries require every token ------------------------
    def test_04_multi_word_and_threshold(self):
        self.assertEqual(self._titles("summer dress"),
                         ["Floral Summer Midi Dress"])
        self.assertEqual(self._titles("camping tent"),
                         ["Camping Dome Tent 4 Person"])
        self.assertEqual(self._titles("dress tent"), [])
        self.assertEqual(self._titles("zzzznotathing"), [])
        self.assertGreater(score_item(self.dress, tokens("dress")), MATCH_THRESHOLD)
        self.assertEqual(score_item(self.dress, tokens("camping")), 0.0)

    # -- 5. browse: the original "dress not found" reproduction -----------
    def test_05_browse_finds_dress_for_all_spellings(self):
        for url in ("/browse?q=dress", "/browse?q=Dress",
                    "/browse?q=dres", "/browse?q=party+dress"):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertIn(b"Floral Summer Midi Dress", resp.data, url)
            self.assertNotIn(b"Camping Dome Tent", resp.data, url)

    # -- 6. filters: category, price, location ----------------------------
    def test_06_category_and_price_filters(self):
        resp = self.client.get("/browse?category=electronics")
        self.assertIn(b"Space Grey DSLR Camera", resp.data)
        self.assertIn(b"Budget Point &amp; Shoot Camera", resp.data)
        self.assertNotIn(b"Floral Summer Midi Dress", resp.data)

        resp = self.client.get("/browse?category=electronics&max_price=1000")
        self.assertNotIn(b"Space Grey DSLR Camera", resp.data)
        self.assertIn(b"Budget Point &amp; Shoot Camera", resp.data)

    def test_07_location_filter(self):
        resp = self.client.get("/browse?category=electronics&location=Pune")
        self.assertIn(b"Space Grey DSLR Camera", resp.data)
        self.assertNotIn(b"Budget Point &amp; Shoot Camera", resp.data)

        none = self.client.get("/browse?category=electronics&location=Delhi")
        self.assertIn(b"No items match your selected filters", none.data)

    # -- 7. sorting --------------------------------------------------------
    def test_08_sorting_by_price(self):
        resp = self.client.get("/browse?category=electronics&sort=cheapest")
        cheap = resp.data.find(b"Budget Point &amp; Shoot Camera")
        pricey = resp.data.find(b"Space Grey DSLR Camera")
        self.assertGreaterEqual(cheap, 0)
        self.assertGreaterEqual(pricey, 0)
        self.assertLess(cheap, pricey)

        resp = self.client.get("/browse?category=electronics&sort=price_high")
        cheap = resp.data.find(b"Budget Point &amp; Shoot Camera")
        pricey = resp.data.find(b"Space Grey DSLR Camera")
        self.assertLess(pricey, cheap)

    # -- 8. empty state instead of a silent "not found" --------------------
    def test_09_empty_state_lists_categories(self):
        resp = self.client.get("/browse?q=xyzzynotathing")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"No items match", resp.data)
        self.assertIn(b"browse one of these categories", resp.data)
        self.assertIn(b'value="electronics"', resp.data)  # filter form still usable


if __name__ == "__main__":
    unittest.main()

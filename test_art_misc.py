"""ART stage 2: farm tools, events, electronics, security, furniture art."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import re
import unittest, tempfile, shutil
import xml.etree.ElementTree as ET

from utils.art_tools import make_tool_art, resolve_key as tool_resolve
from utils.art_events import make_event_art, resolve_key as event_resolve
from utils.art_misc import make_misc_art, resolve_key as misc_resolve
from app import create_app
from models import db, User, Item
import config


def _options(category, field_name):
    for f in config.CATEGORIES[category]["fields"]:
        if f["name"] == field_name:
            if f.get("options"):
                return list(f["options"])
            vals = set()
            for v in (f.get("options_by") or {}).values():
                vals.update(v if isinstance(v, (list, tuple)) else [v])
            return sorted(vals)
    return []


def _subkeys(category):
    return [s["key"] for s in config.CATEGORIES[category]["subcategories"]]


def _assert_scene(test, svg):
    """Valid non-empty SVG with background + floor shadow + label ribbon."""
    test.assertTrue(svg.startswith("<svg"))
    root = ET.fromstring(svg)  # strict XML
    test.assertEqual(root.get("viewBox"), "0 0 800 1000")
    elems = list(root.iter())
    # an empty scene (bg + defs + floor + ribbon only) is exactly 20 elements
    test.assertGreater(len(elems), 20, "art is nearly empty (blank box?)")
    test.assertIn('<ellipse', svg)   # floor shadow
    test.assertIn("<text", svg)      # label ribbon
    stripped = svg.replace('xmlns="http://www.w3.org/2000/svg"', "")
    test.assertNotIn("http://", stripped)
    test.assertNotIn("https://", stripped)
    test.assertNotIn("<script", svg.lower())
    test.assertNotIn("href=", svg.lower())


SECURITY_TYPES = ["Dome CCTV", "Bullet CCTV", "PTZ Camera", "Door Frame Metal Detector",
                  "Hand-held Detector", "X-ray Scanner", "Walkie-Talkie Set", "Barricades"]
FURNITURE_TYPES = ["Chair", "Sofa", "Table", "Bed", "Cupboard", "Shelves"]


class FarmToolsArtTest(unittest.TestCase):

    def test_every_subcategory_and_tool_type(self):
        for key in _subkeys("farm_tools"):
            with self.subTest(subcategory=key):
                self.assertIsNotNone(tool_resolve(key, ""))
                _assert_scene(self, make_tool_art(subcat_key=key, slug="sub-" + key))
        for opt in _options("farm_tools", "tool_type"):
            with self.subTest(tool_type=opt):
                self.assertIsNotNone(tool_resolve("", opt))
                _assert_scene(self, make_tool_art(tool_type=opt, slug="tt-" + opt))

    def test_different_tools_look_different(self):
        a = make_tool_art(tool_type="Plough", slug="x")
        b = make_tool_art(tool_type="Water Tank", slug="x")
        self.assertNotEqual(a, b)

    def test_label_ribbon_shows_tool_name(self):
        svg = make_tool_art(tool_type="Sickle Set", slug="x")
        self.assertIn("Sickle Set", svg)


class EventsArtTest(unittest.TestCase):

    def test_every_subcategory_and_item_type(self):
        for key in _subkeys("event_items"):
            with self.subTest(subcategory=key):
                self.assertIsNotNone(event_resolve(key, ""))
                _assert_scene(self, make_event_art(subcat_key=key, slug="sub-" + key))
        for opt in _options("event_items", "item_type"):
            with self.subTest(item_type=opt):
                self.assertIsNotNone(event_resolve("", opt))
                _assert_scene(self, make_event_art(item_type=opt, slug="it-" + opt))

    def test_style_changes_palette(self):
        a = make_event_art(item_type="Mandap Decor", style="Traditional", slug="same")
        b = make_event_art(item_type="Mandap Decor", style="Modern", slug="same")
        fa = set(re.findall(r'stop-color="([^"]+)"', a))
        fb = set(re.findall(r'stop-color="([^"]+)"', b))
        self.assertNotEqual(fa, fb)


class ElectronicsSecurityFurnitureArtTest(unittest.TestCase):

    def test_electronics_subcategories_and_device_types(self):
        for key in _subkeys("electronics"):
            with self.subTest(subcategory=key):
                self.assertIsNotNone(misc_resolve("electronics", "", key))
                _assert_scene(self, make_misc_art("electronics", subcat_key=key, slug="sub-" + key))
        for opt in _options("electronics", "device_type"):
            with self.subTest(device_type=opt):
                self.assertIsNotNone(misc_resolve("electronics", opt, ""))
                _assert_scene(self, make_misc_art("electronics", type_value=opt, slug="d-" + opt))

    def test_security_types(self):
        for opt in SECURITY_TYPES:
            with self.subTest(security_type=opt):
                self.assertIsNotNone(misc_resolve("security", opt, ""))
                _assert_scene(self, make_misc_art("security", type_value=opt, slug="s-" + opt))

    def test_furniture_types(self):
        for opt in FURNITURE_TYPES:
            with self.subTest(furniture=opt):
                self.assertIsNotNone(misc_resolve("furniture", opt, ""))
                _assert_scene(self, make_misc_art("furniture", type_value=opt, slug="f-" + opt))


class ItemArtRouteTest(unittest.TestCase):

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
        self.owner = User(name="Owner", phone="8010000002", village_or_city="Bengaluru")
        db.session.add(self.owner)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _item(self, category, attrs):
        it = Item(owner_id=self.owner.id, category=category, title=category + " item",
                  description="d", price_per_day=100, deposit=500, late_fee_per_day=20)
        it.set_attributes(attrs)
        db.session.add(it)
        db.session.commit()
        return it

    def test_route_serves_each_family(self):
        cases = [
            ("farm_tools", {"tool_type": "Mini Tractor"}),
            ("event_items", {"item_type": "Shamiyana Tent", "style": "Traditional"}),
            ("electronics", {"device_type": "Camera"}),
        ]
        for category, attrs in cases:
            with self.subTest(category=category):
                it = self._item(category, attrs)
                res = self.client.get(f"/art/item/{it.id}.svg")
                self.assertEqual(res.status_code, 200)
                self.assertTrue(res.headers["Content-Type"].startswith("image/svg+xml"))
                self.assertIn("max-age", res.headers["Cache-Control"])
                ET.fromstring(res.get_data(as_text=True))
                etag = res.headers["ETag"]
                res2 = self.client.get(f"/art/item/{it.id}.svg",
                                       headers={"If-None-Match": etag})
                self.assertEqual(res2.status_code, 304)

    def test_item_picture_uses_art_route(self):
        from utils.illustrations import item_picture
        for category, attrs in [("farm_tools", {"tool_type": "Plough"}),
                                ("event_items", {"item_type": "Chairs"}),
                                ("electronics", {"device_type": "Drone"})]:
            with self.subTest(category=category):
                it = self._item(category, attrs)
                pic = item_picture(it)
                self.assertEqual(pic["src"], f"/art/item/{it.id}.svg")

    def test_unknown_item_404(self):
        self.assertEqual(self.client.get("/art/item/999999.svg").status_code, 404)


if __name__ == "__main__":
    unittest.main()

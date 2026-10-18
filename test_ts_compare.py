"""STAGE 3 – TrustShield comparison tests (suggestions only, never charges)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import io
import unittest, tempfile, shutil
from PIL import Image, ImageEnhance, ImageDraw

from app import create_app
from models import db, DamageRecord, DamageCase, Item
import utils.ts_compare as tsc


class TestTsCompare(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.app = create_app({
            "TESTING": True, "OTP_MODE": "demo",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(cls.tmp, "t.db"),
            "UPLOAD_FOLDER": os.path.join(cls.tmp, "uploads"),
        })
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        db.create_all()

    @classmethod
    def tearDownClass(cls):
        db.session.remove(); cls.ctx.pop()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _save(self, img, name):
        p = os.path.join(self.tmp, name)
        img.convert("RGB").save(p, format="JPEG")
        return p

    def test_identical_images_no_flags(self):
        base = Image.new("RGB", (256, 256), (90, 120, 60))
        d = ImageDraw.Draw(base)
        d.rectangle([40, 40, 120, 120], fill=(20, 30, 200))
        a = self._save(base, "a.jpg")
        b = self._save(base, "b.jpg")
        res = tsc.compare_pair(self.app, a, b)
        self.assertEqual(res["regions"], [])
        self.assertGreaterEqual(res["similarity"], 0.999)

    def test_drawn_patch_gives_region_and_overlay(self):
        orig = Image.new("RGB", (256, 256), (200, 200, 200))
        ret = orig.copy()
        ImageDraw.Draw(ret).rectangle([60, 60, 180, 180], fill=(0, 0, 0))
        a = self._save(orig, "p_a.jpg")
        b = self._save(ret, "p_b.jpg")
        res = tsc.compare_pair(self.app, a, b)
        self.assertGreaterEqual(len(res["regions"]), 1)
        self.assertIsNotNone(res["overlay_stored_name"])
        from utils.ts_evidence import abs_path
        self.assertTrue(os.path.isfile(abs_path(self.app, res["overlay_stored_name"])))

    def test_brightness_only_flags_nothing_or_low(self):
        orig = Image.new("RGB", (256, 256), (60, 90, 120))
        ImageDraw.Draw(orig).rectangle([20, 20, 100, 100], fill=(200, 200, 200))
        bright = ImageEnhance.Brightness(orig).enhance(1.7)
        a = self._save(orig, "br_a.jpg")
        b = self._save(bright, "br_b.jpg")
        res = tsc.compare_pair(self.app, a, b)
        ok = (len(res["regions"]) == 0) or (res["confidence"] in ("low", "medium"))
        self.assertTrue(ok, f"brightness change over-flagged: {res['regions']} {res['confidence']}")

    def test_compare_never_creates_charge_or_record(self):
        orig = Image.new("RGB", (256, 256), (210, 210, 210))
        ret = orig.copy()
        ImageDraw.Draw(ret).rectangle([10, 10, 240, 60], fill=(0, 0, 0))
        a = self._save(orig, "c_a.jpg")
        b = self._save(ret, "c_b.jpg")
        dr_before = DamageRecord.query.count()
        dc_before = DamageCase.query.count()
        tsc.compare_pair(self.app, a, b)   # suggestion only
        self.assertEqual(DamageRecord.query.count(), dr_before)
        self.assertEqual(DamageCase.query.count(), dc_before)

    def test_existing_overlap_helper(self):
        item = Item(owner_id=1, category="electronics", title="X", price_per_day=100, deposit=100)
        db.session.add(item); db.session.commit()
        ex = DamageRecord(item_id=item.id, damage_type="Scratch", angle="front", status="existing")
        db.session.add(ex); db.session.commit()
        found = tsc.overlaps_existing("front", [ex])
        self.assertIsNotNone(found)
        self.assertIsNone(tsc.overlaps_existing("back", [ex]))


if __name__ == "__main__":
    unittest.main()

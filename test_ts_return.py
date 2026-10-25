"""STAGE 3 (route level) – TrustShield return evidence + comparison.

Proves the flow only ever makes SUGGESTIONS: uploading the return report and
running the Pillow comparison never creates a DamageRecord or a DamageCase, an
owner-confirmed change that overlaps a previously-reported damage is NOT
attributed to the renter, and "no new damage" finalises via the existing
settlement path.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import io
import unittest, tempfile, shutil
from datetime import date, timedelta
from PIL import Image, ImageDraw

from app import create_app
from models import (db, User, Item, Booking, ConditionReport, EvidenceFile,
                    DamageRecord, DamageCase, ComparisonResult, ReturnRecord)
from seed import seed as run_seed


def _jpeg(patch=False, size=(200, 200)):
    buf = io.BytesIO()
    img = Image.new("RGB", size, (200, 200, 200))
    if patch:
        ImageDraw.Draw(img).rectangle([40, 40, 160, 160], fill=(0, 0, 0))
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


class TestTsReturn(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True, "OTP_MODE": "demo",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "t.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
            "SERVER_NAME": "localhost",
        })
        self.ctx = self.app.app_context()
        self.ctx.push()
        run_seed()
        self.client = self.app.test_client()
        self.owner = User.query.filter_by(phone="9000000001").first()
        self.renter = User.query.filter_by(phone="9000000003").first()
        self.item = Item.query.filter_by(owner_id=self.owner.id).first()

    def tearDown(self):
        db.session.remove(); self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _login(self, phone):
        self.client.get("/logout")
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        self.client.post("/login", data={"otp": "1234", "name": "X",
                                         "village_or_city": "City"}, follow_redirects=True)

    def _picked_up_booking(self):
        b = Booking(item_id=self.item.id, renter_id=self.renter.id,
                    start_date=date.today() + timedelta(days=1),
                    end_date=date.today() + timedelta(days=2), days=2,
                    total_rent=100.0, deposit=100.0, total_payable=200.0,
                    status="approved", payment_method="cash",
                    payment_status="pay_on_pickup", delivery_method="pickup",
                    trustshield=True)
        db.session.add(b); db.session.commit()
        # Owner handover + renter confirm -> picked_up + report confirmed
        self._login(self.owner.phone)
        self.client.post(f"/ts/bookings/{b.id}/handover",
                         data={"photo": [(_jpeg(), f"{i}.jpg") for i in range(5)],
                               "angle": [f"a{i}" for i in range(5)]},
                         content_type="multipart/form-data", follow_redirects=True)
        self._login(self.renter.phone)
        self.client.post(f"/ts/bookings/{b.id}/condition",
                         data={"action": "confirm", "confirm_accept": "1"},
                         follow_redirects=True)
        db.session.refresh(b)
        self.assertEqual(b.status, "picked_up")
        return b

    def _post_return(self, b, patch=False):
        self._login(self.owner.phone)
        return self.client.post(f"/ts/bookings/{b.id}/return",
                                data={"photo": [(_jpeg(patch=patch), f"{i}.jpg") for i in range(5)],
                                      "angle": [f"a{i}" for i in range(5)],
                                      "actual_return_date": date.today().isoformat()},
                                content_type="multipart/form-data", follow_redirects=True)

    def test_return_creates_only_suggestions(self):
        b = self._picked_up_booking()
        dr_before = DamageRecord.query.filter_by(status="new_proposed").count()
        dc_before = DamageCase.query.count()
        self._post_return(b, patch=True)
        # Comparison ran and stored per-angle suggestion rows.
        self.assertGreater(ComparisonResult.query.filter_by(booking_id=b.id).count(), 0)
        # But NO charge / NO new-proposed damage / NO case was created by itself.
        self.assertEqual(DamageRecord.query.filter_by(status="new_proposed").count(), dr_before)
        self.assertEqual(DamageCase.query.count(), dc_before)
        self.assertIsNone(ReturnRecord.query.filter_by(booking_id=b.id).first())

    def test_review_page_lists_angles(self):
        b = self._picked_up_booking()
        self._post_return(b, patch=True)
        page = self.client.get(f"/ts/bookings/{b.id}/review")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Possible change", page.data)

    def test_existing_overlap_not_attributed(self):
        b = self._picked_up_booking()
        ex = DamageRecord(item_id=self.item.id, damage_type="Scratch",
                          angle="a0", status="existing", source_phase="handover")
        db.session.add(ex); db.session.commit()
        self._post_return(b, patch=True)
        self._login(self.owner.phone)
        before = DamageRecord.query.filter_by(status="new_proposed").count()
        self.client.post(f"/ts/bookings/{b.id}/review",
                         data={"action": "confirm_new", "angle": "a0", "rule_key": "scratch"},
                         follow_redirects=True)
        self.assertEqual(DamageRecord.query.filter_by(status="new_proposed").count(), before)
        cr = ComparisonResult.query.filter_by(booking_id=b.id, angle="a0").first()
        self.assertTrue(cr.matched_existing)

    def test_confirm_genuinely_new_damage_creates_proposed(self):
        b = self._picked_up_booking()
        self._post_return(b, patch=True)
        self._login(self.owner.phone)
        self.client.post(f"/ts/bookings/{b.id}/review",
                         data={"action": "confirm_new", "angle": "a2", "rule_key": "tear"},
                         follow_redirects=True)
        dr = DamageRecord.query.filter_by(item_id=self.item.id, status="new_proposed",
                                          angle="a2").first()
        self.assertIsNotNone(dr)
        self.assertEqual(dr.attributed_renter_id, self.renter.id)

    def test_no_new_damage_finalizes_via_existing_settlement(self):
        b = self._picked_up_booking()
        self._post_return(b, patch=False)   # identical -> no regions
        self._login(self.owner.phone)
        self.client.post(f"/ts/bookings/{b.id}/review",
                         data={"action": "no_new_damage"}, follow_redirects=True)
        db.session.refresh(b)
        rec = ReturnRecord.query.filter_by(booking_id=b.id).first()
        self.assertIsNotNone(rec)
        self.assertEqual(b.status, "returned")
        self.assertEqual(rec.damage_deduction, 0.0)
        self.assertEqual(rec.refund_amount, 100.0)


if __name__ == "__main__":
    unittest.main()

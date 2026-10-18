"""STAGE 5 - TrustShield dashboards, item history, seed (additive feature).

Covers: the renter dashboard shows the four cards for every TrustShield booking
with the correct deposit-refund status, the owner dashboard shows pending
actions, /items/<id>/condition-history works, the pages render for clothing,
electronics, books and furniture, and running the seed twice creates no
duplicates.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import io
import unittest, tempfile, shutil
from datetime import date, timedelta, datetime
from PIL import Image

from app import create_app
from models import (db, User, Item, Booking, ReturnRecord, DamageRecord,
                    DamageCase, ConditionReport, EvidenceFile)
from seed import seed as run_seed
import seed_trustshield


def _jpeg(size=(160, 160)):
    buf = io.BytesIO()
    Image.new("RGB", size, (180, 180, 180)).save(buf, format="JPEG")
    buf.seek(0)
    return buf


class TestTsDashboard(unittest.TestCase):

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
        self.admin = User.query.filter_by(phone="9999999999").first()

    def tearDown(self):
        db.session.remove(); self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _login(self, phone):
        self.client.get("/logout")
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        self.client.post("/login", data={"otp": "1234", "name": "X",
                                         "village_or_city": "City"}, follow_redirects=True)

    def _item(self, category, title="TS Item"):
        it = Item(owner_id=self.owner.id, category=category, title=title,
                  price_per_day=100, deposit=1000, late_fee_per_day=50)
        db.session.add(it); db.session.commit()
        return it

    def _booking(self, item, status="picked_up", deposit=1000):
        b = Booking(item_id=item.id, renter_id=self.renter.id,
                    start_date=date.today() - timedelta(days=2),
                    end_date=date.today() - timedelta(days=1), days=2,
                    total_rent=200.0, deposit=deposit, total_payable=deposit + 200.0,
                    status=status, payment_method="cash", payment_status="paid_demo",
                    delivery_method="pickup", trustshield=True)
        db.session.add(b); db.session.commit()
        return b

    def _add_handover(self, b, item):
        rep = ConditionReport(booking_id=b.id, item_id=item.id, phase="handover",
                              status="confirmed", created_by=self.owner.id)
        db.session.add(rep); db.session.flush()
        db.session.add(EvidenceFile(report_id=rep.id, booking_id=b.id, item_id=item.id,
                                    kind="photo", angle="front", stored_name="x.jpg",
                                    size_bytes=10, original_name="x.jpg",
                                    mime="image/jpeg", exif_stripped=True,
                                    uploaded_by=self.owner.id))
        db.session.commit()
        return rep

    def test_four_cards_each_deposit_state(self):
        item = self._item("electronics")
        # 1. Held: waiting for condition review (picked_up, no case)
        b1 = self._booking(item, status="picked_up")
        self._add_handover(b1, item)
        # 2. Held: under dispute
        b2 = self._booking(item, status="picked_up")
        self._add_handover(b2, item)
        case = DamageCase(booking_id=b2.id, item_id=item.id, created_by=self.owner.id,
                          status="disputed", proposed_total=400, verified_total=0,
                          finalized=False)
        db.session.add(case); db.session.commit()
        # 3. Refunded (full)
        b3 = self._booking(item, status="returned")
        self._add_handover(b3, item)
        db.session.add(ReturnRecord(booking_id=b3.id, actual_return_date=date.today(),
                                    deposit_held=1000, total_deductions=0,
                                    refund_amount=1000)); db.session.commit()
        # 4. Partly refunded
        b4 = self._booking(item, status="returned")
        self._add_handover(b4, item)
        db.session.add(ReturnRecord(booking_id=b4.id, actual_return_date=date.today(),
                                    deposit_held=1000, total_deductions=300,
                                    damage_deduction=300, refund_amount=700))
        db.session.commit()

        self._login(self.renter.phone)
        rv = self.client.get("/dashboard/renter")
        html = rv.get_data(as_text=True)
        self.assertEqual(rv.status_code, 200)
        # All four card headings present.
        for heading in ("Original condition", "Return condition",
                        "Damage report", "Deposit refund"):
            self.assertIn(heading, html)
        # Each deposit-state text rendered.
        self.assertIn("Held: waiting for condition review", html)
        self.assertIn("Held: under dispute", html)
        self.assertIn("Refunded Rs 1,000", html)
        self.assertIn("Partly refunded (Rs 700 refunded, Rs 300 deducted)", html)

    def test_owner_dashboard_lists_pending(self):
        item = self._item("clothes")
        b = self._booking(item, status="approved")
        self._login(self.owner.phone)
        rv = self.client.get("/dashboard/owner")
        html = rv.get_data(as_text=True)
        self.assertEqual(rv.status_code, 200)
        self.assertIn("TrustShield", html)
        self.assertIn(f"/ts/bookings/{b.id}/handover", html)

    def test_condition_history_page(self):
        item = self._item("furniture", "TS Study Table")
        b = self._booking(item, status="picked_up")
        self._add_handover(b, item)
        db.session.add(DamageRecord(item_id=item.id, booking_id=b.id, damage_type="Scratch",
                                    area="top", description="old", status="existing",
                                    reported_by=self.owner.id))
        db.session.commit()
        self._login(self.owner.phone)
        rv = self.client.get(f"/items/{item.id}/condition-history")
        self.assertEqual(rv.status_code, 200)
        html = rv.get_data(as_text=True)
        self.assertIn("Condition History", html)
        self.assertIn("Scratch", html)
        self.assertIn("Mark as repaired", html)
        # A third user (renter who is not owner/admin) gets 403.
        self._login(self.renter.phone)
        rv2 = self.client.get(f"/items/{item.id}/condition-history")
        self.assertEqual(rv2.status_code, 403)

    def test_pages_work_for_all_categories(self):
        for cat in ("clothes", "electronics", "books", "furniture"):
            item = self._item(cat, f"Item {cat}")
            b = self._booking(item, status="approved")
            self._login(self.owner.phone)
            rv = self.client.get(f"/ts/bookings/{b.id}/handover")
            self.assertEqual(rv.status_code, 200, f"handover failed for {cat}")

    def test_seed_twice_no_duplicates(self):
        # setUp's run_seed() already calls seed_trustshield.run() (via seed.py),
        # so the demo TrustShield items must already exist exactly once.
        self.assertIsNotNone(Item.query.filter_by(
            title=seed_trustshield.DEMO_TITLES[0]).first())
        mid = Item.query.count()
        second = seed_trustshield.run()   # a second run must be a no-op
        self.assertFalse(second)
        self.assertEqual(Item.query.count(), mid)
        # And it never created the demo set twice.
        self.assertEqual(Item.query.filter(
            Item.title.in_(seed_trustshield.DEMO_TITLES)).count(),
            len(seed_trustshield.DEMO_TITLES))


if __name__ == "__main__":
    unittest.main()

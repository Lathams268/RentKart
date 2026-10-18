"""STAGE 4 – verified penalty, finalization, disputes, admin (TrustShield).

Covers the rule ranges, the above-range quote requirement, the deposit cap, the
"nothing is deducted until verified" guarantee, acceptance finalization, the
deadline path (goes to admin, charges nothing), partial acceptance, dispute
validation, one-dispute-per-case, non-admin 403 and admin reduce/reject maths.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import io
import unittest, tempfile, shutil
from datetime import date, timedelta, datetime
from PIL import Image, ImageDraw

from app import create_app
from models import (db, User, Item, Booking, DamageRecord, DamageCase,
                    DamageClaimItem, Dispute, ReturnRecord)
from seed import seed as run_seed
from utils.ts_penalty import propose_cost


def _jpeg(patch=False, size=(200, 200)):
    buf = io.BytesIO()
    img = Image.new("RGB", size, (200, 200, 200))
    if patch:
        ImageDraw.Draw(img).rectangle([40, 40, 160, 160], fill=(0, 0, 0))
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


class TestTsPenaltyDisputes(unittest.TestCase):

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
        self.item = Item(owner_id=self.owner.id, category="electronics",
                         title="Test Laptop", price_per_day=100, deposit=5000,
                         late_fee_per_day=50)
        db.session.add(self.item); db.session.commit()

    def tearDown(self):
        db.session.remove(); self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _login(self, phone):
        self.client.get("/logout")
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        self.client.post("/login", data={"otp": "1234", "name": "X",
                                         "village_or_city": "City"}, follow_redirects=True)

    def _booking(self):
        b = Booking(item_id=self.item.id, renter_id=self.renter.id,
                    start_date=date.today() + timedelta(days=1),
                    end_date=date.today() + timedelta(days=2), days=2,
                    total_rent=1000.0, deposit=5000.0, total_payable=6000.0,
                    status="approved", payment_method="cash",
                    payment_status="pay_on_pickup", delivery_method="pickup",
                    trustshield=True)
        db.session.add(b); db.session.commit()
        return b

    def _to_review(self, b):
        """Handover -> renter confirm -> return -> comparison."""
        self._login(self.owner.phone)
        self.client.post(f"/ts/bookings/{b.id}/handover",
                         data={"photo": [(_jpeg(), f"{i}.jpg") for i in range(5)],
                               "angle": [f"a{i}" for i in range(5)]},
                         content_type="multipart/form-data", follow_redirects=True)
        self._login(self.renter.phone)
        self.client.post(f"/ts/bookings/{b.id}/condition",
                         data={"action": "confirm", "confirm_accept": "1"},
                         follow_redirects=True)
        self._login(self.owner.phone)
        self.client.post(f"/ts/bookings/{b.id}/return",
                         data={"photo": [(_jpeg(patch=True), f"{i}.jpg") for i in range(5)],
                               "angle": [f"a{i}" for i in range(5)],
                               "actual_return_date": date.today().isoformat()},
                         content_type="multipart/form-data", follow_redirects=True)

    def _confirm_damage(self, b, angle, rule_key):
        self._login(self.owner.phone)
        self.client.post(f"/ts/bookings/{b.id}/review",
                         data={"action": "confirm_new", "angle": angle, "rule_key": rule_key},
                         follow_redirects=True)

    def _proposed_records(self, b):
        return DamageRecord.query.filter_by(booking_id=b.id, status="new_proposed")\
            .order_by(DamageRecord.id).all()

    def _propose(self, b, spec):
        """spec: list of (rule, amount, quote_pdf|None). Applied to each record in id order."""
        recs = self._proposed_records(b)
        data = {}
        for i, (rule, amount, quote) in enumerate(spec):
            data[f"rule_{recs[i].id}"] = rule
            data[f"amount_{recs[i].id}"] = str(amount)
            if quote is not None:
                data[f"quote_{recs[i].id}"] = (io.BytesIO(quote), "quote.pdf")
        self._login(self.owner.phone)
        return self.client.post(f"/ts/bookings/{b.id}/propose", data=data,
                                content_type="multipart/form-data", follow_redirects=True)

    def _case_with_two_claims(self):
        b = self._booking()
        self._to_review(b)
        self._confirm_damage(b, "a2", "scratch")   # electronics scratch 150-500
        self._confirm_damage(b, "a3", "screen")    # electronics screen 800-4000
        self._propose(b, [("scratch", 150, None), ("screen", 800, None)])
        case = DamageCase.query.filter_by(booking_id=b.id).first()
        return b, case

    # ---- unit: ranges ----
    def test_range_rules(self):
        p = propose_cost("electronics", "screen", 5000)
        self.assertEqual((p["min"], p["max"], p["default"]), (800, 4000, 800))
        lost = propose_cost("electronics", "lost", 5000)
        self.assertEqual(lost["min"], 5000)
        self.assertEqual(lost["max"], 5000)

    # ---- above range requires attachment ----
    def test_above_range_requires_attachment(self):
        b = self._booking()
        self._to_review(b)
        self._confirm_damage(b, "a2", "scratch")   # max 500
        self._propose(b, [("scratch", 600, None)])  # above max, no quote
        self.assertIsNone(DamageCase.query.filter_by(booking_id=b.id).first())
        # with a quote attached -> accepted
        self._propose(b, [("scratch", 600, PDF)])
        case = DamageCase.query.filter_by(booking_id=b.id).first()
        self.assertIsNotNone(case)
        self.assertTrue(case.claims[0].requires_quote)

    # ---- cap ----
    def test_cap_blocks_over_deposit(self):
        b = self._booking()
        self._to_review(b)
        self._confirm_damage(b, "a2", "screen")
        self._confirm_damage(b, "a3", "screen")
        # deposit is 5000; two screens at 4000 each = 8000 > cap (100% of deposit)
        self._propose(b, [("screen", 4000, None), ("screen", 4000, None)])
        self.assertIsNone(DamageCase.query.filter_by(booking_id=b.id).first())

    # ---- nothing deducted while awaiting customer ----
    def test_nothing_deducted_while_awaiting(self):
        b, case = self._case_with_two_claims()
        self.assertEqual(case.status, "awaiting_customer")
        self.assertIsNone(ReturnRecord.query.filter_by(booking_id=b.id).first())
        self.assertEqual(b.status, "picked_up")

    # ---- acceptance finalizes ----
    def test_acceptance_finalizes(self):
        b, case = self._case_with_two_claims()   # 150 + 800 = 950
        self._login(self.renter.phone)
        self.client.post(f"/ts/bookings/{b.id}/damage-report",
                         data={"action": "accept_all"}, follow_redirects=True)
        rec = ReturnRecord.query.filter_by(booking_id=b.id).first()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.damage_deduction, 950)
        self.assertEqual(rec.refund_amount, 5000 - 950)   # late = 0
        self.assertTrue(case.finalized)

    # ---- deadline charges nothing ----
    def test_deadline_goes_to_admin_no_charge(self):
        b, case = self._case_with_two_claims()
        case.review_deadline = datetime.utcnow() - timedelta(hours=1)
        db.session.commit()
        self._login(self.renter.phone)
        self.client.get(f"/ts/bookings/{b.id}/damage-report")
        db.session.refresh(case)
        self.assertEqual(case.status, "admin_review")
        self.assertIsNone(ReturnRecord.query.filter_by(booking_id=b.id).first())

    # ---- partial acceptance sends only disputed to admin ----
    def test_partial_acceptance(self):
        b, case = self._case_with_two_claims()
        c1, c2 = case.claims[0], case.claims[1]
        self._login(self.renter.phone)
        self.client.post(f"/ts/bookings/{b.id}/damage-report",
                         data={"action": "accept_some_dispute_rest",
                               "accept_claim": str(c1.id),
                               "reason": "amount_too_high",
                               "comment": "The screen charge seems too high for me."},
                         follow_redirects=True)
        dispute = Dispute.query.filter_by(case_id=case.id).first()
        self.assertIsNotNone(dispute)
        self.assertEqual(dispute.get_claim_ids(), [c2.id])
        db.session.refresh(c1); db.session.refresh(c2)
        self.assertEqual(c1.status, "accepted")
        self.assertEqual(c2.status, "disputed")
        self.assertIsNone(ReturnRecord.query.filter_by(booking_id=b.id).first())

    # ---- dispute validation ----
    def test_short_comment_rejected(self):
        b, case = self._case_with_two_claims()
        self._login(self.renter.phone)
        self.client.post(f"/ts/bookings/{b.id}/damage-report",
                         data={"action": "dispute_all", "reason": "other", "comment": "short"},
                         follow_redirects=True)
        self.assertIsNone(Dispute.query.filter_by(case_id=case.id).first())

    def test_no_reason_rejected(self):
        b, case = self._case_with_two_claims()
        self._login(self.renter.phone)
        self.client.post(f"/ts/bookings/{b.id}/damage-report",
                         data={"action": "dispute_all", "reason": "", "comment": "A long enough comment here"},
                         follow_redirects=True)
        self.assertIsNone(Dispute.query.filter_by(case_id=case.id).first())

    def test_second_dispute_refused(self):
        b, case = self._case_with_two_claims()
        self._login(self.renter.phone)
        good = {"action": "dispute_all", "reason": "not_my_damage",
                "comment": "This damage was not caused by me at all."}
        self.client.post(f"/ts/bookings/{b.id}/damage-report", data=good, follow_redirects=True)
        self.client.post(f"/ts/bookings/{b.id}/damage-report", data=good, follow_redirects=True)
        self.assertEqual(Dispute.query.filter_by(case_id=case.id).count(), 1)

    # ---- non-admin 403 ----
    def test_non_admin_403(self):
        self._login(self.renter.phone)
        self.assertEqual(self.client.get("/admin/ts/disputes").status_code, 403)

    # ---- admin reduce / reject refund ----
    def _dispute_all(self, b, case):
        self._login(self.renter.phone)
        self.client.post(f"/ts/bookings/{b.id}/damage-report",
                         data={"action": "dispute_all", "reason": "amount_too_high",
                               "comment": "I think both charges are too high for me."},
                         follow_redirects=True)
        return Dispute.query.filter_by(case_id=case.id).first()

    def test_admin_reduce_and_reject(self):
        b, case = self._case_with_two_claims()   # 150 + 800
        dispute = self._dispute_all(b, case)
        c1, c2 = case.claims[0], case.claims[1]
        self._login(self.admin.phone)
        self.client.post(f"/admin/ts/disputes/{dispute.id}",
                         data={f"decision_{c1.id}": "reduce", f"amount_{c1.id}": "100",
                               f"decision_{c2.id}": "reject", "note": "adjusted"},
                         follow_redirects=True)
        rec = ReturnRecord.query.filter_by(booking_id=b.id).first()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.damage_deduction, 100)   # only the reduced claim survives
        self.assertEqual(rec.refund_amount, 5000 - 100)

    def test_admin_uphold(self):
        b, case = self._case_with_two_claims()   # 150 + 800 = 950
        dispute = self._dispute_all(b, case)
        c1, c2 = case.claims[0], case.claims[1]
        self._login(self.admin.phone)
        self.client.post(f"/admin/ts/disputes/{dispute.id}",
                         data={f"decision_{c1.id}": "uphold", f"decision_{c2.id}": "uphold",
                               "note": "evidence is clear"},
                         follow_redirects=True)
        rec = ReturnRecord.query.filter_by(booking_id=b.id).first()
        self.assertEqual(rec.damage_deduction, 950)
        self.assertEqual(rec.refund_amount, 5000 - 950)


if __name__ == "__main__":
    unittest.main()

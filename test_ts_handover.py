"""STAGE 2 – TrustShield handover evidence + customer confirmation tests."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import io
import unittest, tempfile, shutil
from datetime import date, timedelta
from PIL import Image

from app import create_app
from models import db, User, Item, Booking, ConditionReport, DamageRecord
from seed import seed as run_seed


def _jpeg(size=(120, 90)):
    buf = io.BytesIO()
    Image.new("RGB", size, (10, 200, 120)).save(buf, format="JPEG")
    buf.seek(0)
    return buf


class TestTsHandover(unittest.TestCase):

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

    def _booking(self, trustshield=True, status="approved", pay="pay_on_pickup"):
        b = Booking(item_id=self.item.id, renter_id=self.renter.id,
                    start_date=date.today() + timedelta(days=1),
                    end_date=date.today() + timedelta(days=2), days=2,
                    total_rent=100.0, deposit=100.0, total_payable=200.0,
                    status=status, payment_method="cash", payment_status=pay,
                    delivery_method="pickup", trustshield=trustshield)
        db.session.add(b); db.session.commit()
        return b

    def _post_handover(self, booking_id, n_photos):
        photos = [(_jpeg(), f"{i}.jpg") for i in range(n_photos)]
        angles = [f"angle{i}" for i in range(n_photos)]
        data = {"photo": photos, "angle": angles}
        return self.client.post(f"/ts/bookings/{booking_id}/handover",
                                data=data, content_type="multipart/form-data",
                                follow_redirects=True)

    def test_min_photos_enforced(self):
        b = self._booking()
        self._login(self.owner.phone)
        self._post_handover(b.id, 1)   # below MIN_PHOTOS_HANDOVER (4)
        db.session.refresh(b)
        self.assertEqual(b.status, "approved")
        self.assertIsNone(ConditionReport.query.filter_by(booking_id=b.id).first())

    def test_not_picked_up_until_confirmed(self):
        b = self._booking()
        self._login(self.owner.phone)
        self._post_handover(b.id, 5)
        db.session.refresh(b)
        self.assertEqual(b.status, "awaiting_customer_confirmation")
        self.assertEqual(b.payment_status, "pay_on_pickup")
        rep = ConditionReport.query.filter_by(booking_id=b.id).first()
        self.assertIsNotNone(rep)
        self.assertEqual(rep.phase, "handover")
        self.assertGreaterEqual(len(rep.get_angles()), 4)

    def test_confirm_keeps_cash_on_pickup(self):
        b = self._booking()
        self._login(self.owner.phone)
        self._post_handover(b.id, 5)
        self._login(self.renter.phone)
        # confirm WITHOUT checkbox -> not accepted
        self.client.post(f"/ts/bookings/{b.id}/condition",
                         data={"action": "confirm"}, follow_redirects=True)
        db.session.refresh(b)
        self.assertEqual(b.status, "awaiting_customer_confirmation")
        # confirm WITH checkbox
        self.client.post(f"/ts/bookings/{b.id}/condition",
                         data={"action": "confirm", "confirm_accept": "1"},
                         follow_redirects=True)
        db.session.refresh(b)
        self.assertEqual(b.status, "picked_up")
        self.assertEqual(b.payment_status, "paid_demo")   # cash-on-pickup preserved

    def test_mismatch_keeps_approved(self):
        b = self._booking()
        self._login(self.owner.phone)
        self._post_handover(b.id, 5)
        self._login(self.renter.phone)
        self.client.post(f"/ts/bookings/{b.id}/condition",
                         data={"action": "mismatch", "mismatch_reason": "Screen cracked not shown"},
                         follow_redirects=True)
        db.session.refresh(b)
        self.assertEqual(b.status, "approved")

    def test_third_user_403(self):
        b = self._booking()
        outsider = User(name="Out", phone="9555555555", village_or_city="X", lat=12.0, lng=77.0)
        db.session.add(outsider); db.session.commit()
        self._login("9555555555")
        self.assertEqual(self.client.get(f"/ts/bookings/{b.id}/handover").status_code, 403)
        self.assertEqual(self.client.get(f"/ts/bookings/{b.id}/condition").status_code, 403)

    def test_existing_damages_recorded(self):
        b = self._booking()
        self._login(self.owner.phone)
        data = {"photo": [(_jpeg(), f"{i}.jpg") for i in range(5)],
                "angle": [f"a{i}" for i in range(5)],
                "d_type": ["Stain"], "d_area": ["collar"], "d_angle": ["front"],
                "d_desc": ["old coffee stain"]}
        self.client.post(f"/ts/bookings/{b.id}/handover", data=data,
                         content_type="multipart/form-data", follow_redirects=True)
        dr = DamageRecord.query.filter_by(item_id=self.item.id, status="existing").first()
        self.assertIsNotNone(dr)
        self.assertEqual(dr.damage_type, "Stain")

    def test_old_booking_still_one_click_handover(self):
        b = self._booking(trustshield=False)
        self._login(self.owner.phone)
        resp = self.client.post(f"/bookings/{b.id}/handover",
                                data={"handover_note": "quick"}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        db.session.refresh(b)
        self.assertEqual(b.status, "picked_up")


if __name__ == "__main__":
    unittest.main()

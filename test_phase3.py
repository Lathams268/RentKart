"""Phase-3 tests – booking flow, pricing, availability, status transitions, dashboards."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from datetime import date, timedelta
from app import create_app
from models import db, User, Item, Booking
from utils.booking import calculate_days, calculate_price, booking_snapshot, is_available
from seed import seed as run_seed


class RentKartPhase3(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
            "WTF_CSRF_ENABLED": False,
            "SERVER_NAME": "localhost",
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- Helpers ---
    def _login(self, phone="9999999999", name="Test User", village="TestCity"):
        self.client.get("/logout")
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        return self.client.post("/login", data={
            "otp": "1234",
            "name": name,
            "village_or_city": village,
        }, follow_redirects=True)

    def _create_user(self, name, phone, village="City"):
        user = User(name=name, phone=phone, village_or_city=village, lat=12.97, lng=77.59)
        db.session.add(user)
        db.session.commit()
        return user

    def _create_item(self, owner, title="Test Item", price_per_day=500.0, deposit=1000.0):
        item = Item(
            owner_id=owner.id,
            category="electronics",
            title=title,
            description="A test rental item",
            price_per_day=price_per_day,
            deposit=deposit,
            late_fee_per_day=50.0,
            lat=owner.lat,
            lng=owner.lng,
        )
        db.session.add(item)
        db.session.commit()
        return item

    # --- 1. price calculation is correct for 3 days ---
    def test_01_price_calculation_for_3_days(self):
        owner = self._create_user("Owner1", "9111111111")
        item = self._create_item(owner, price_per_day=500.0, deposit=1000.0)

        start = date.today() + timedelta(days=5)
        end = start + timedelta(days=2)  # inclusive 3 days: day 0, day 1, day 2

        days = calculate_days(start, end)
        self.assertEqual(days, 3)

        pricing = calculate_price(item, start, end)
        self.assertEqual(pricing["days"], 3)
        self.assertEqual(pricing["total_rent"], 1500.0)
        self.assertEqual(pricing["deposit"], 1000.0)
        self.assertEqual(pricing["total_payable"], 2500.0)

    # --- 2. booking an overlapping approved range is rejected ---
    def test_02_booking_overlapping_approved_range_rejected(self):
        owner = self._create_user("Owner2", "9222222221")
        renter1 = self._create_user("Renter1", "9222222222")
        renter2 = self._create_user("Renter2", "9222222223")
        item = self._create_item(owner, price_per_day=400.0, deposit=500.0)

        # Existing approved booking for day 10 to day 15
        start1 = date.today() + timedelta(days=10)
        end1 = date.today() + timedelta(days=15)
        p1 = calculate_price(item, start1, end1)
        b1 = Booking(
            item_id=item.id,
            renter_id=renter1.id,
            start_date=start1,
            end_date=end1,
            **booking_snapshot(p1),
            status="approved",
        )
        db.session.add(b1)
        db.session.commit()

        # Renter 2 attempts to book overlapping dates: day 12 to day 17
        self._login(phone=renter2.phone, name=renter2.name)
        start2 = date.today() + timedelta(days=12)
        end2 = date.today() + timedelta(days=17)

        # Check utility directly
        self.assertFalse(is_available(item, start2, end2))

        # Check route rejects the booking
        resp = self.client.post(
            f"/items/{item.id}/book",
            data={"start_date": start2.isoformat(), "end_date": end2.isoformat()},
            follow_redirects=True,
        )
        self.assertIn(b"Item is not available", resp.data)
        # Verify no booking was created for renter2
        self.assertEqual(Booking.query.filter_by(renter_id=renter2.id).count(), 0)

    # --- 3. owner approves, then a second overlapping request cannot be approved ---
    def test_03_owner_approves_second_overlapping_cannot_be_approved(self):
        owner = self._create_user("Owner3", "9333333331")
        r1 = self._create_user("RenterA", "9333333332")
        r2 = self._create_user("RenterB", "9333333333")
        item = self._create_item(owner, price_per_day=300.0, deposit=500.0)

        # Both request overlapping periods
        d1 = date.today() + timedelta(days=5)
        d2 = date.today() + timedelta(days=8)
        p1 = calculate_price(item, d1, d2)
        b1 = Booking(item_id=item.id, renter_id=r1.id, start_date=d1, end_date=d2, **booking_snapshot(p1), status="requested")

        d3 = date.today() + timedelta(days=7)
        d4 = date.today() + timedelta(days=10)
        p2 = calculate_price(item, d3, d4)
        b2 = Booking(item_id=item.id, renter_id=r2.id, start_date=d3, end_date=d4, **booking_snapshot(p2), status="requested")

        db.session.add_all([b1, b2])
        db.session.commit()

        # Owner logs in
        self._login(phone=owner.phone, name=owner.name)

        # Owner approves request 1 -> should succeed
        resp1 = self.client.post(f"/bookings/{b1.id}/approve", follow_redirects=True)
        self.assertIn(b"Booking approved", resp1.data)
        db.session.refresh(b1)
        self.assertEqual(b1.status, "approved")

        # Owner attempts to approve overlapping request 2 -> should be rejected
        resp2 = self.client.post(f"/bookings/{b2.id}/approve", follow_redirects=True)
        self.assertIn(b"overlaps these dates", resp2.data)
        db.session.refresh(b2)
        self.assertEqual(b2.status, "requested")

    # --- 4. handover changes status to picked_up ---
    def test_04_handover_changes_status_to_picked_up(self):
        owner = self._create_user("Owner4", "9444444441")
        renter = self._create_user("Renter4", "9444444442")
        item = self._create_item(owner)

        start = date.today()
        end = start + timedelta(days=2)
        p = calculate_price(item, start, end)
        booking = Booking(
            item_id=item.id,
            renter_id=renter.id,
            start_date=start,
            end_date=end,
            **booking_snapshot(p),
            status="approved",
            payment_method="cash",
            payment_status="pay_on_pickup",
        )
        db.session.add(booking)
        db.session.commit()

        # Owner logs in and attempts handover with invalid photo extension
        self._login(phone=owner.phone, name=owner.name)
        import io
        bad_photo = (io.BytesIO(b"fake txt"), "document.txt")
        bad_resp = self.client.post(
            f"/bookings/{booking.id}/handover",
            data={"handover_note": "Note", "handover_photo": bad_photo},
            follow_redirects=True,
        )
        self.assertIn(b"Photo must be png or jpg", bad_resp.data)
        db.session.refresh(booking)
        self.assertEqual(booking.status, "approved")

        # Now marks handed over successfully with note
        resp = self.client.post(
            f"/bookings/{booking.id}/handover",
            data={"handover_note": "Handed over with all cables intact."},
            follow_redirects=True,
        )
        self.assertIn(b"Rental is now active", resp.data)

        db.session.refresh(booking)
        self.assertEqual(booking.status, "picked_up")
        self.assertEqual(booking.payment_status, "paid_demo")
        self.assertEqual(booking.handover_note, "Handed over with all cables intact.")

    # --- 5. renter cannot approve (403) and owner cannot book own item ---
    def test_05_renter_cannot_approve_and_owner_cannot_book_own_item(self):
        owner = self._create_user("Owner5", "9555555551")
        renter = self._create_user("Renter5", "9555555552")
        item = self._create_item(owner)

        start = date.today() + timedelta(days=3)
        end = start + timedelta(days=5)
        p = calculate_price(item, start, end)
        booking = Booking(
            item_id=item.id,
            renter_id=renter.id,
            start_date=start,
            end_date=end,
            **booking_snapshot(p),
            status="requested",
        )
        db.session.add(booking)
        db.session.commit()

        # Part A: Renter tries to approve booking -> 403 Forbidden
        self._login(phone=renter.phone, name=renter.name)
        resp = self.client.post(f"/bookings/{booking.id}/approve")
        self.assertEqual(resp.status_code, 403)

        # Part B: Owner tries to book their own item -> blocked
        self._login(phone=owner.phone, name=owner.name)
        initial_booking_count = Booking.query.count()
        resp2 = self.client.post(
            f"/items/{item.id}/book",
            data={"start_date": start.isoformat(), "end_date": end.isoformat()},
            follow_redirects=True,
        )
        self.assertIn(b"cannot book your own item", resp2.data)
        self.assertEqual(Booking.query.count(), initial_booking_count)

    # --- 6. payment works for both UPI and cash ---
    def test_06_payment_works_for_both_upi_and_cash(self):
        owner = self._create_user("Owner6", "9666666661")
        renter = self._create_user("Renter6", "9666666662")
        item = self._create_item(owner)

        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=3)
        p = calculate_price(item, start, end)

        # Booking 1: Pay with UPI
        b1 = Booking(item_id=item.id, renter_id=renter.id, start_date=start, end_date=end, **booking_snapshot(p), status="requested")
        # Booking 2: Pay with Cash on pickup
        start2 = date.today() + timedelta(days=10)
        end2 = start2 + timedelta(days=12)
        p2 = calculate_price(item, start2, end2)
        b2 = Booking(item_id=item.id, renter_id=renter.id, start_date=start2, end_date=end2, **booking_snapshot(p2), status="requested")

        db.session.add_all([b1, b2])
        db.session.commit()

        self._login(phone=renter.phone, name=renter.name)

        # Verify payment page renders with demo banner
        get_resp = self.client.get(f"/bookings/{b1.id}/payment")
        self.assertEqual(get_resp.status_code, 200)
        self.assertIn(b"Demo mode", get_resp.data)
        self.assertIn(b"no real money", get_resp.data)

        # 1. UPI payment
        resp_upi = self.client.post(
            f"/bookings/{b1.id}/payment",
            data={"payment_method": "upi"},
            follow_redirects=True,
        )
        self.assertIn(b"UPI payment successful", resp_upi.data)
        db.session.refresh(b1)
        self.assertEqual(b1.payment_method, "upi")
        self.assertEqual(b1.payment_status, "paid_demo")

        # 2. Cash on pickup
        resp_cash = self.client.post(
            f"/bookings/{b2.id}/payment",
            data={"payment_method": "cash"},
            follow_redirects=True,
        )
        self.assertIn(b"Cash on pickup selected", resp_cash.data)
        db.session.refresh(b2)
        self.assertEqual(b2.payment_method, "cash")
        self.assertEqual(b2.payment_status, "pay_on_pickup")

        # 3. Accessing payment again when already paid redirects to detail
        resp_again = self.client.get(f"/bookings/{b1.id}/payment", follow_redirects=True)
        self.assertIn(b"Booking #", resp_again.data)

    # --- 7. both dashboards load with seeded data ---
    def test_07_both_dashboards_load_with_seeded_data(self):
        run_seed()

        # Check seed created requested, approved, and picked_up bookings
        self.assertGreaterEqual(Booking.query.filter_by(status="requested").count(), 1)
        self.assertGreaterEqual(Booking.query.filter_by(status="approved").count(), 1)
        self.assertGreaterEqual(Booking.query.filter_by(status="picked_up").count(), 1)

        # Owner dashboard (Priya owns items and has approved/active bookings)
        self._login(phone="9000000004", name="Priya")
        owner_resp = self.client.get("/dashboard/owner")
        self.assertEqual(owner_resp.status_code, 200)
        self.assertIn(b"Owner Dashboard", owner_resp.data)
        self.assertIn(b"Total Earnings", owner_resp.data)
        self.assertIn(b"My Items", owner_resp.data)

        # Renter dashboard (Priya has requested lehenga)
        renter_resp = self.client.get("/dashboard/renter")
        self.assertEqual(renter_resp.status_code, 200)
        self.assertIn(b"My Bookings", renter_resp.data)
        self.assertIn(b"REQUESTED", renter_resp.data)

        # Ramesh's owner dashboard (has incoming request)
        self.client.get("/logout")
        self._login(phone="9000000001", name="Ramesh")
        ramesh_owner = self.client.get("/dashboard/owner")
        self.assertEqual(ramesh_owner.status_code, 200)
        self.assertIn(b"Incoming Requests", ramesh_owner.data)
        self.assertIn(b"Approve", ramesh_owner.data)
        self.assertIn(b"Reject", ramesh_owner.data)

        # Ramesh's renter dashboard (has approved booking)
        ramesh_renter = self.client.get("/dashboard/renter")
        self.assertEqual(ramesh_renter.status_code, 200)
        self.assertIn(b"APPROVED", ramesh_renter.data)


if __name__ == "__main__":
    unittest.main(verbosity=2)

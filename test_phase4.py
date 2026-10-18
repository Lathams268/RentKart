"""Phase-4 tests – returns, late penalties, damage deductions, settlements, reviews, and trust scores."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from datetime import date, timedelta
from app import create_app
from models import db, User, Item, Booking, ReturnRecord, Review
from utils.booking import calculate_price, booking_snapshot
from utils.settlement import calculate_settlement
from utils.trust import calculate_trust_score, get_trust_level, get_user_trust


class RentKartPhase4(unittest.TestCase):

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

    def _create_item(self, owner, title="Test Item", price_per_day=500.0, deposit=1000.0, late_fee_per_day=100.0):
        item = Item(
            owner_id=owner.id,
            category="electronics",
            title=title,
            description="A test rental item",
            price_per_day=price_per_day,
            deposit=deposit,
            late_fee_per_day=late_fee_per_day,
            lat=owner.lat,
            lng=owner.lng,
        )
        db.session.add(item)
        db.session.commit()
        return item

    # --- 1. No damage and on time gives a full refund ---
    def test_01_no_damage_on_time_full_refund(self):
        end = date(2026, 10, 20)
        actual = date(2026, 10, 20)
        s = calculate_settlement(deposit=1000.0, end_date=end, actual_return_date=actual,
                                 late_fee_per_day=100.0, damage_level="none")
        self.assertEqual(s["late_days"], 0)
        self.assertEqual(s["late_penalty"], 0.0)
        self.assertEqual(s["damage_deduction"], 0.0)
        self.assertEqual(s["total_deductions"], 0.0)
        self.assertEqual(s["refund_amount"], 1000.0)
        self.assertEqual(s["extra_due"], 0.0)

    # --- 2. Deposit 1000, fee 100 per day, 2 days late, minor damage gives late penalty 200, damage 200, total 400, refund 600 ---
    def test_02_late_and_minor_damage_settlement(self):
        end = date(2026, 10, 20)
        actual = date(2026, 10, 22)  # 2 days late
        s = calculate_settlement(deposit=1000.0, end_date=end, actual_return_date=actual,
                                 late_fee_per_day=100.0, damage_level="minor")
        self.assertEqual(s["late_days"], 2)
        self.assertEqual(s["late_penalty"], 200.0)
        self.assertEqual(s["damage_percent"], 20.0)
        self.assertEqual(s["damage_deduction"], 200.0)
        self.assertEqual(s["total_deductions"], 400.0)
        self.assertEqual(s["refund_amount"], 600.0)
        self.assertEqual(s["extra_due"], 0.0)

    # --- 3. Lost item gives refund 0 and no negative numbers ---
    def test_03_lost_item_refund_zero_no_negative(self):
        end = date(2026, 10, 20)
        actual = date(2026, 10, 20)
        s = calculate_settlement(deposit=1000.0, end_date=end, actual_return_date=actual,
                                 late_fee_per_day=100.0, damage_level="lost")
        self.assertEqual(s["damage_percent"], 100.0)
        self.assertEqual(s["damage_deduction"], 1000.0)
        self.assertEqual(s["total_deductions"], 1000.0)
        self.assertEqual(s["refund_amount"], 0.0)
        self.assertGreaterEqual(s["refund_amount"], 0.0)
        self.assertGreaterEqual(s["extra_due"], 0.0)

    # --- 4. Deductions above the deposit show the correct extra_due ---
    def test_04_deductions_above_deposit_show_extra_due(self):
        end = date(2026, 10, 20)
        actual = date(2026, 10, 25)  # 5 days late
        # deposit 500, late fee 200/day -> late penalty 1000. major damage = 60% of 500 = 300.
        # total deductions = 1300. deposit = 500. extra_due = 800. refund = 0.
        s = calculate_settlement(deposit=500.0, end_date=end, actual_return_date=actual,
                                 late_fee_per_day=200.0, damage_level="major")
        self.assertEqual(s["late_penalty"], 1000.0)
        self.assertEqual(s["damage_deduction"], 300.0)
        self.assertEqual(s["total_deductions"], 1300.0)
        self.assertEqual(s["refund_amount"], 0.0)
        self.assertEqual(s["extra_due"], 800.0)

    # --- 5. A booking cannot be returned twice, and only the owner can return it ---
    def test_05_only_owner_can_return_and_cannot_return_twice(self):
        owner = self._create_user("Owner5", "9555555551")
        renter = self._create_user("Renter5", "9555555552")
        item = self._create_item(owner, deposit=1000.0, late_fee_per_day=50.0)

        start = date.today() - timedelta(days=5)
        end = date.today() - timedelta(days=1)
        p = calculate_price(item, start, end)
        b = Booking(item_id=item.id, renter_id=renter.id, start_date=start, end_date=end, **booking_snapshot(p),
                    status="picked_up", payment_method="upi", payment_status="paid_demo")
        db.session.add(b)
        db.session.commit()

        # Part A: Renter tries to return -> 403 Forbidden
        self._login(phone=renter.phone, name=renter.name)
        resp_renter = self.client.post(f"/bookings/{b.id}/return", data={
            "actual_return_date": date.today().isoformat(),
            "damage_level": "none",
        })
        self.assertEqual(resp_renter.status_code, 403)

        # Part B: Owner returns booking -> succeeds
        self._login(phone=owner.phone, name=owner.name)
        resp_owner = self.client.post(f"/bookings/{b.id}/return", data={
            "actual_return_date": date.today().isoformat(),
            "damage_level": "none",
        }, follow_redirects=True)
        self.assertIn(b"settlement", resp_owner.data.lower())
        db.session.refresh(b)
        self.assertEqual(b.status, "returned")
        self.assertIsNotNone(b.return_record)

        # Part C: Owner attempts to return the same booking again -> blocked (cannot return twice)
        initial_return_count = ReturnRecord.query.count()
        resp_twice = self.client.post(f"/bookings/{b.id}/return", data={
            "actual_return_date": date.today().isoformat(),
            "damage_level": "minor",
        }, follow_redirects=True)
        self.assertIn(b"already been returned", resp_twice.data)
        self.assertEqual(ReturnRecord.query.count(), initial_return_count)

    # --- 6. Settlement gives 403 for a third user ---
    def test_06_settlement_403_for_third_user(self):
        owner = self._create_user("Owner6", "9666666661")
        renter = self._create_user("Renter6", "9666666662")
        intruder = self._create_user("ThirdUser", "9666666663")
        item = self._create_item(owner)

        start = date.today() - timedelta(days=3)
        end = date.today()
        p = calculate_price(item, start, end)
        b = Booking(item_id=item.id, renter_id=renter.id, start_date=start, end_date=end, **booking_snapshot(p),
                    status="returned", payment_method="upi", payment_status="paid_demo")
        db.session.add(b)
        db.session.flush()

        rec = ReturnRecord(
            booking_id=b.id,
            actual_return_date=end,
            late_days=0,
            late_fee_per_day=item.late_fee_per_day,
            late_penalty=0.0,
            damage_level="none",
            damage_percent=0.0,
            damage_deduction=0.0,
            deposit_held=b.deposit,
            total_deductions=0.0,
            refund_amount=b.deposit,
            extra_due=0.0,
        )
        db.session.add(rec)
        db.session.commit()

        # Intruder attempts to view settlement -> 403 Forbidden
        self._login(phone=intruder.phone, name=intruder.name)
        resp_intruder = self.client.get(f"/bookings/{b.id}/settlement")
        self.assertEqual(resp_intruder.status_code, 403)

        # Owner can view settlement -> 200 OK
        self._login(phone=owner.phone, name=owner.name)
        resp_owner = self.client.get(f"/bookings/{b.id}/settlement")
        self.assertEqual(resp_owner.status_code, 200)
        self.assertIn(b"Settlement Receipt", resp_owner.data)

        # Renter can view settlement -> 200 OK
        self._login(phone=renter.phone, name=renter.name)
        resp_renter = self.client.get(f"/bookings/{b.id}/settlement")
        self.assertEqual(resp_renter.status_code, 200)
        self.assertIn(b"Settlement Receipt", resp_renter.data)

    # --- 7. A new user has trust score 50, a clean return raises it, a late return lowers it ---
    def test_07_trust_score_new_clean_and_late(self):
        user = self._create_user("TrustTester", "9777777771")
        owner = self._create_user("ItemOwner7", "9777777772")
        item = self._create_item(owner)

        # A: New user starts at 50
        self.assertEqual(calculate_trust_score(user), 50)

        # B: 1 clean return raises score by +10 to 60
        b_clean = Booking(item_id=item.id, renter_id=user.id, start_date=date(2026, 1, 1),
                          end_date=date(2026, 1, 3), days=3, total_rent=1500, deposit=500,
                          total_payable=2000, status="returned")
        db.session.add(b_clean)
        db.session.flush()
        rec_clean = ReturnRecord(booking_id=b_clean.id, actual_return_date=date(2026, 1, 3),
                                 late_days=0, damage_level="none")
        db.session.add(rec_clean)
        db.session.commit()

        self.assertEqual(calculate_trust_score(user), 60)

        # C: 1 late return lowers score by -10 (60 - 10 = 50)
        b_late = Booking(item_id=item.id, renter_id=user.id, start_date=date(2026, 1, 10),
                         end_date=date(2026, 1, 12), days=3, total_rent=1500, deposit=500,
                         total_payable=2000, status="returned")
        db.session.add(b_late)
        db.session.flush()
        rec_late = ReturnRecord(booking_id=b_late.id, actual_return_date=date(2026, 1, 14),
                                late_days=2, damage_level="none")
        db.session.add(rec_late)
        db.session.commit()

        self.assertEqual(calculate_trust_score(user), 50)

    # --- 8. A Highly Trusted renter's deposit is 50 percent of the item deposit ---
    def test_08_highly_trusted_renter_deposit_discount(self):
        owner = self._create_user("Owner8", "9888888881")
        trusted_renter = self._create_user("TrustedRenter", "9888888882")
        item = self._create_item(owner, price_per_day=500.0, deposit=1000.0)

        # Give renter 3 clean returns -> score = 50 + 30 = 80 (Highly Trusted)
        for i in range(3):
            b = Booking(item_id=item.id, renter_id=trusted_renter.id, start_date=date(2026, 2, 1 + i*4),
                        end_date=date(2026, 2, 3 + i*4), days=3, total_rent=1500, deposit=1000,
                        total_payable=2500, status="returned")
            db.session.add(b)
            db.session.flush()
            rec = ReturnRecord(booking_id=b.id, actual_return_date=date(2026, 2, 3 + i*4),
                               late_days=0, damage_level="none")
            db.session.add(rec)
        db.session.commit()

        # Check trust score and multiplier
        trust = get_user_trust(trusted_renter)
        self.assertGreaterEqual(trust["score"], 70)
        self.assertEqual(trust["label"], "Highly Trusted")
        self.assertEqual(trust["multiplier"], 0.5)

        # Renter books item with standard deposit of 1000
        self._login(phone=trusted_renter.phone, name=trusted_renter.name)
        start = date.today() + timedelta(days=5)
        end = date.today() + timedelta(days=7)
        resp = self.client.post(
            f"/items/{item.id}/book",
            data={"start_date": start.isoformat(), "end_date": end.isoformat()},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)

        new_booking = Booking.query.filter_by(renter_id=trusted_renter.id, status="requested").first()
        self.assertIsNotNone(new_booking)
        # 50 percent of 1000 = 500
        self.assertEqual(new_booking.deposit, 500.0)
        self.assertEqual(new_booking.total_payable, new_booking.total_rent + 500.0)

    # --- 9. One review per booking only ---
    def test_09_one_review_per_booking_only(self):
        owner = self._create_user("Owner9", "9999999991")
        renter = self._create_user("Renter9", "9999999992")
        intruder = self._create_user("Intruder9", "9999999993")
        item = self._create_item(owner)

        start = date.today() - timedelta(days=3)
        end = date.today()
        p = calculate_price(item, start, end)
        b = Booking(item_id=item.id, renter_id=renter.id, start_date=start, end_date=end, **booking_snapshot(p),
                    status="returned", payment_method="upi", payment_status="paid_demo")
        db.session.add(b)
        db.session.commit()

        # Non-renter cannot review -> 403 Forbidden
        self._login(phone=intruder.phone, name=intruder.name)
        resp_intruder = self.client.post(f"/bookings/{b.id}/review", data={"rating": 5, "comment": "Good!"})
        self.assertEqual(resp_intruder.status_code, 403)

        # Renter submits first review -> succeeds
        self._login(phone=renter.phone, name=renter.name)
        resp1 = self.client.post(f"/bookings/{b.id}/review", data={
            "rating": 5,
            "comment": "Super clean and punctual!",
        }, follow_redirects=True)
        self.assertIn(b"Thank you for your review", resp1.data)
        self.assertEqual(Review.query.filter_by(booking_id=b.id).count(), 1)

        # Renter attempts to submit a second review for the same booking -> rejected
        resp2 = self.client.post(f"/bookings/{b.id}/review", data={
            "rating": 4,
            "comment": "Trying again",
        }, follow_redirects=True)
        self.assertIn(b"already reviewed", resp2.data)
        self.assertEqual(Review.query.filter_by(booking_id=b.id).count(), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

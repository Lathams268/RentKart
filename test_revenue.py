"""Revenue feature tests: fee math, ledger lifecycle, refunds and flags."""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta

from flask import g

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from models import Booking, Item, Subscription, User, db
from models_revenue import (BannerAd, BookingAddon, FeaturedListing,
                            ProtectionClaim, RevenueEntry)
from utils.booking import calculate_price
from utils.revenue import (commission_percent_for, features, gst_parts,
                           is_featured, mark_booking_earned,
                           owner_pro_price_paise, record_booking_charges,
                           renter_fee_paise, reverse_booking,
                           save_booking_addons, save_settings,
                           sponsored_banner, to_paise)


class RevenueTestCase(unittest.TestCase):
    """Revenue switched ON for these tests."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "REVENUE_ENABLED": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
            "OTP_MODE": "demo",
        })
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------- helpers ----------
    def _user(self, phone, admin=False):
        user = User(name="U" + phone[-3:], phone=phone, village_or_city="C",
                    lat=12.9, lng=77.5, is_admin=admin)
        db.session.add(user)
        db.session.commit()
        return user

    def _item(self, owner, price=100.0, deposit=0.0, category="electronics"):
        item = Item(owner_id=owner.id, category=category, title="T",
                    price_per_day=price, deposit=deposit, late_fee_per_day=50.0)
        db.session.add(item)
        db.session.commit()
        return item

    def _booking(self, item, renter, rent=1000.0, fee=0.0, commission=5.0,
                 deposit=0.0, status="picked_up", payment_status="paid_demo"):
        today = date.today()
        booking = Booking(
            item_id=item.id, renter_id=renter.id, start_date=today, end_date=today,
            days=1, total_rent=rent, deposit=deposit,
            total_payable=rent + deposit + fee, platform_fee=fee,
            commission_percent=commission, status=status,
            payment_status=payment_status, payment_method="upi",
        )
        db.session.add(booking)
        db.session.commit()
        return booking

    def _login(self, user):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True
        # The test keeps one app context alive; clear Flask-Login's cached
        # anonymous user from the earlier request before reusing the client.
        g.pop("_login_user", None)
        return client.get("/admin/revenue")

    # ---------- fee math ----------
    def test_fee_minimum_applies(self):
        # 8% of Rs 100 is Rs 8, below the Rs 29 floor.
        self.assertEqual(renter_fee_paise(100), 2900)

    def test_fee_maximum_applies(self):
        # 8% of Rs 20,000 is Rs 1,600, above the Rs 999 cap.
        self.assertEqual(renter_fee_paise(20000), 99900)

    def test_fee_rounds_half_up_to_paise(self):
        self.app.config.update({
            "REVENUE_RENTER_FEE_PERCENT": 8,
            "REVENUE_RENTER_FEE_MIN_PAISE": 0,
            "REVENUE_RENTER_FEE_MAX_PAISE": 99900,
        })
        # 8% of 137 = 10.96 exactly -> 1096 paise
        self.assertEqual(renter_fee_paise(137), 1096)
        # 8% of 100.0625 = 8.005 -> 801 paise (half-up)
        self.assertEqual(renter_fee_paise(100.0625), 801)

    def test_category_override(self):
        save_settings({"renter_fee_category_overrides": {"clothes": 10}})
        self.assertEqual(renter_fee_paise(1000, "clothes"), 10000)
        self.assertEqual(renter_fee_paise(1000, "electronics"), 8000)

    def test_fee_is_part_of_total_but_deposit_is_not_charged_fee(self):
        owner = self._user("9000000201")
        renter = self._user("9000000202")
        item = self._item(owner, price=1000.0, deposit=5000.0)
        today = date.today()
        pricing = calculate_price(item, today, today, user=None)
        self.assertEqual(pricing["rent"], 1000.0)
        self.assertEqual(pricing["platform_fee"], 80.0)  # 8% of rent only
        self.assertEqual(pricing["total_payable"], 1000.0 + 5000.0 + 80.0)

        booking = self._booking(item, renter, rent=1000.0, fee=80.0,
                                commission=0.0, deposit=5000.0)
        record_booking_charges(booking)
        db.session.commit()
        fee_entry = RevenueEntry.query.filter_by(type="renter_fee").one()
        self.assertEqual(fee_entry.gross, 8000)
        self.assertEqual(RevenueEntry.query.filter_by(type="owner_commission").count(), 0)

    # ---------- commission ----------
    def test_commission_waiver_and_owner_pro(self):
        owner = self._user("9000000211")
        renter = self._user("9000000212")
        item = self._item(owner)
        self.assertEqual(commission_percent_for(owner), 0.0)  # launch waiver

        for _ in range(3):
            self._booking(item, renter, commission=0.0)
        self.assertEqual(commission_percent_for(owner), 5.0)

        today = date.today()
        db.session.add(Subscription(
            user_id=owner.id, plan="owner_pro", billing_cycle="monthly",
            status="active", start_date=today, end_date=today + timedelta(days=30),
            amount_paid=399.0, payment_method="upi",
        ))
        db.session.commit()
        self.assertEqual(commission_percent_for(owner), 2.0)

    def test_owner_pro_yearly_price(self):
        self.assertEqual(owner_pro_price_paise("monthly"), 39900)
        self.assertEqual(owner_pro_price_paise("yearly"), 383040)  # 20% off

    # ---------- ledger lifecycle ----------
    def test_ledger_pending_then_earned_then_refunded(self):
        owner = self._user("9000000221")
        renter = self._user("9000000222")
        item = self._item(owner)
        booking = self._booking(item, renter, rent=1000.0, fee=80.0, commission=5.0)

        record_booking_charges(booking)
        db.session.commit()
        entries = RevenueEntry.query.filter_by(booking_id=booking.id).all()
        self.assertEqual({e.type for e in entries}, {"renter_fee", "owner_commission"})
        self.assertTrue(all(e.status == "pending" for e in entries))

        mark_booking_earned(booking)
        db.session.commit()
        self.assertTrue(all(e.status == "earned" for e in entries))

        reverse_booking(booking, reason="cancelled by owner")
        db.session.commit()
        originals = RevenueEntry.query.filter(
            RevenueEntry.booking_id == booking.id,
            RevenueEntry.source_ref.is_(None),
        ).all()
        mirrors = RevenueEntry.query.filter(
            RevenueEntry.booking_id == booking.id,
            RevenueEntry.source_ref.like("reversal-%"),
        ).all()
        self.assertTrue(all(e.status == "refunded" for e in originals))
        self.assertEqual(len(mirrors), len(originals))
        self.assertEqual(sum(e.gross for e in originals + mirrors), 0)

    def test_gst_and_gateway_are_inclusive(self):
        gst, gateway, net = gst_parts(11800)
        self.assertEqual((gst, gateway, net), (1800, 236, 9764))
        self.assertEqual(gst + gateway + net, 11800)

    # ---------- add-ons ----------
    def test_protection_and_service_addons(self):
        owner = self._user("9000000231")
        renter = self._user("9000000232")
        item = self._item(owner, price=1000.0, deposit=0.0)
        today = date.today()
        pricing = calculate_price(item, today, today,
                                  addons={"protection": True,
                                          "service_delivery": True})
        self.assertEqual(pricing["protection_fee"], 50.0)   # 5% of 1000
        self.assertEqual(pricing["service_fee"], 99.0)
        self.assertEqual(pricing["addon_total"], 149.0)
        self.assertEqual(pricing["total_payable"], 1000.0 + 80.0 + 149.0)

        booking = self._booking(item, renter, rent=1000.0, fee=80.0, commission=0.0)
        save_booking_addons(booking, pricing)
        record_booking_charges(booking)
        db.session.commit()

        addons = BookingAddon.query.filter_by(booking_id=booking.id).all()
        self.assertEqual({a.kind for a in addons}, {"protection", "service_delivery"})
        protection = RevenueEntry.query.filter_by(type="protection").one()
        service = RevenueEntry.query.filter_by(type="service").one()
        self.assertEqual(protection.gross, 5000)
        self.assertEqual(service.gross, 2970)  # 30% margin on Rs 99

    def test_protection_claim_is_capped(self):
        owner = self._user("9000000241")
        renter = self._user("9000000242")
        admin = self._user("9000000243", admin=True)
        item = self._item(owner)
        booking = self._booking(item, renter, rent=1000.0, fee=80.0, commission=0.0)
        db.session.add(BookingAddon(
            booking_id=booking.id, kind="protection", label="Damage protection",
            amount_paise=5000, platform_paise=5000, owner_paise=0,
        ))
        db.session.commit()

        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                sess["_user_id"] = str(admin.id)
                sess["_fresh"] = True
            resp = client.post(
                f"/admin/revenue/protection/{booking.id}/claim",
                data={"amount": "999999", "note": "demo"},
            )
            self.assertEqual(resp.status_code, 302)
        claim = ProtectionClaim.query.one()
        self.assertEqual(claim.amount_paise, 500000)  # capped at Rs 5,000

    # ---------- featured / banners ----------
    def test_featured_listing_is_detected_and_expires(self):
        owner = self._user("9000000251")
        item = self._item(owner)
        now = __import__("datetime").datetime.utcnow()
        db.session.add(FeaturedListing(
            item_id=item.id, owner_id=owner.id, weeks=1, price_paise=9900,
            status="active", starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=6),
        ))
        db.session.commit()
        self.assertTrue(is_featured(item))

        row = FeaturedListing.query.one()
        row.ends_at = now - timedelta(days=1)
        db.session.commit()
        g.pop("_rk_featured_ids", None)  # per-request cache must be refreshed
        self.assertFalse(is_featured(item))

    def test_live_sponsored_banner_is_returned(self):
        today = date.today()
        ad = BannerAd(title="Demo", image_url="/static/illustrations/books.svg",
                      link_url="/browse", start_date=today - timedelta(days=1),
                      end_date=today + timedelta(days=5), price_paise=150000,
                      active=True)
        db.session.add(ad)
        db.session.commit()
        self.assertEqual(sponsored_banner().id, ad.id)

    # ---------- admin access ----------
    def test_admin_revenue_requires_login_and_admin_role(self):
        with self.app.test_client() as client:
            resp = client.get("/admin/revenue")
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/login", resp.headers["Location"])

        non_admin = self._user("9000000261")
        resp = self._login(non_admin)
        self.assertEqual(resp.status_code, 403)

        admin = self._user("9000000262", admin=True)
        resp = self._login(admin)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Revenue dashboard", resp.get_data(as_text=True))

    def test_admin_settings_and_ads_pages_render(self):
        admin = self._user("9000000271", admin=True)
        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                sess["_user_id"] = str(admin.id)
                sess["_fresh"] = True
            self.assertEqual(client.get("/admin/revenue/settings").status_code, 200)
            self.assertEqual(client.get("/admin/revenue/ads").status_code, 200)


class RevenueOffTestCase(unittest.TestCase):
    """Master flag off must keep the old checkout and write no ledger rows."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,  # revenue defaults OFF unless opted in
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
            "OTP_MODE": "demo",
        })
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_old_pricing_and_no_ledger(self):
        self.assertFalse(features()["renter_fee"])
        self.app.config.update({"RENTER_FEE_PERCENT": 2, "RENTER_FEE_MIN": 0,
                                "RENTER_FEE_MAX": 50})
        owner = User(name="O", phone="9000000301", village_or_city="C",
                     lat=12.9, lng=77.5)
        renter = User(name="R", phone="9000000302", village_or_city="C",
                      lat=12.9, lng=77.5)
        db.session.add_all([owner, renter])
        db.session.commit()
        item = Item(owner_id=owner.id, category="electronics", title="T",
                    price_per_day=100.0, deposit=500.0, late_fee_per_day=50.0,
                    delivery_available=True, delivery_charge=60.0)
        db.session.add(item)
        db.session.commit()

        today = date.today() + timedelta(days=1)
        pricing = calculate_price(item, today, today + timedelta(days=2),
                                  user=renter, delivery_method="delivery")
        self.assertEqual(pricing["platform_fee"], 6.0)
        self.assertEqual(pricing["total_payable"], 766.0)

        booking = Booking(
            item_id=item.id, renter_id=renter.id, start_date=today,
            end_date=today + timedelta(days=2), days=3, total_rent=300.0,
            deposit=400.0, total_payable=766.0, platform_fee=6.0,
            commission_percent=10.0, status="picked_up",
            payment_status="paid_demo", payment_method="upi",
        )
        db.session.add(booking)
        db.session.commit()
        self.assertEqual(record_booking_charges(booking), [])
        self.assertEqual(RevenueEntry.query.count(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

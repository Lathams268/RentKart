"""Phase-6 tests: subscriptions, commission, feedback system, and admin panel."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from datetime import date, timedelta
from app import create_app
from models import db, User, Item, Booking, ReturnRecord, Subscription, Feedback
from utils.settlement import calculate_settlement
from utils.plans import commission_for, get_plan


class RentKartPhase6(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
            "WTF_CSRF_ENABLED": False,
            "SERVER_NAME": "localhost",
            "OTP_MODE": "demo",
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- Helpers ---
    def _login(self, phone="9999999999", name="Test User", village="Bengaluru"):
        self.client.get("/logout")
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        return self.client.post("/login", data={
            "otp": "1234",
            "name": name,
            "village_or_city": village,
        }, follow_redirects=True)

    def _create_user(self, name, phone, village="Bengaluru", lat=12.9716, lng=77.5946, is_admin=False):
        user = User(name=name, phone=phone, village_or_city=village, lat=lat, lng=lng, is_admin=is_admin)
        db.session.add(user)
        db.session.commit()
        return user

    def _create_item(self, owner, title="Item", category="farm_tools", price_per_day=100.0, deposit=500.0):
        item = Item(
            owner_id=owner.id,
            category=category,
            title=title,
            description="Test Description",
            price_per_day=price_per_day,
            deposit=deposit,
            late_fee_per_day=20.0,
            lat=owner.lat,
            lng=owner.lng,
            is_available=True,
        )
        db.session.add(item)
        db.session.commit()
        return item

    # 1. A Free owner with 5 items cannot add a 6th
    def test_01_free_owner_with_5_items_cannot_add_6th(self):
        owner = self._create_user("Owner1", "9000000010")
        for i in range(5):
            self._create_item(owner, title=f"Owner1 Item {i+1}")

        self.assertEqual(Item.query.filter_by(owner_id=owner.id).count(), 5)
        self.assertEqual(owner.current_plan(), "free")

        self._login(phone=owner.phone, name=owner.name)
        res = self.client.post("/items/add", data={
            "category": "farm_tools",
            "title": "Owner1 6th Item",
            "description": "Exceeding limit",
            "price_per_day": "150",
            "deposit": "500",
            "late_fee_per_day": "30",
        }, follow_redirects=True)

        self.assertEqual(Item.query.filter_by(owner_id=owner.id).count(), 5)
        self.assertIn("Upgrade plan", res.get_data(as_text=True))

    # 2. After a demo subscription to Pro the owner can add more
    def test_02_after_pro_subscription_owner_can_add_more(self):
        owner = self._create_user("Owner2", "9000000020")
        for i in range(5):
            self._create_item(owner, title=f"Owner2 Item {i+1}")

        self._login(phone=owner.phone, name=owner.name)

        # Subscribe to Pro (demo)
        sub_res = self.client.post("/subscribe/pro", data={
            "payment_method": "upi",
            "billing_cycle": "monthly",
        }, follow_redirects=True)
        self.assertEqual(sub_res.status_code, 200)

        # Owner is now on Pro
        db.session.refresh(owner)
        self.assertEqual(owner.current_plan(), "pro")

        # Now can add 6th item
        add_res = self.client.post("/items/add", data={
            "category": "farm_tools",
            "title": "Owner2 6th Item Allowed",
            "description": "Allowed with Pro",
            "price_per_day": "200",
            "deposit": "600",
            "late_fee_per_day": "40",
        }, follow_redirects=True)

        self.assertEqual(Item.query.filter_by(owner_id=owner.id).count(), 6)
        self.assertIn("Owner2 6th Item Allowed", add_res.get_data(as_text=True))

    # 3. Commission: rent 1000 gives fee 100 on Free, 50 on Pro, 20 on Business
    def test_03_commission_percentages_and_calculation(self):
        # Math calculation test via calculate_settlement
        free_settle = calculate_settlement(
            deposit=500.0,
            end_date=date.today(),
            actual_return_date=date.today(),
            late_fee_per_day=0.0,
            damage_level="none",
            total_rent=1000.0,
            commission_percent=10.0,
        )
        self.assertEqual(free_settle["platform_fee"], 100.0)
        self.assertEqual(free_settle["owner_earning"], 900.0)

        pro_settle = calculate_settlement(
            deposit=500.0,
            end_date=date.today(),
            actual_return_date=date.today(),
            late_fee_per_day=0.0,
            damage_level="none",
            total_rent=1000.0,
            commission_percent=5.0,
        )
        self.assertEqual(pro_settle["platform_fee"], 50.0)
        self.assertEqual(pro_settle["owner_earning"], 950.0)

        biz_settle = calculate_settlement(
            deposit=500.0,
            end_date=date.today(),
            actual_return_date=date.today(),
            late_fee_per_day=0.0,
            damage_level="none",
            total_rent=1000.0,
            commission_percent=2.0,
        )
        self.assertEqual(biz_settle["platform_fee"], 20.0)
        self.assertEqual(biz_settle["owner_earning"], 980.0)

        # Helper commission_for test
        user_free = self._create_user("UserFree", "9000000031")
        user_pro = self._create_user("UserPro", "9000000032")
        user_biz = self._create_user("UserBiz", "9000000033")

        today = date.today()
        sub_pro = Subscription(user_id=user_pro.id, plan="pro", billing_cycle="monthly", status="active",
                               start_date=today, end_date=today + timedelta(days=30), amount_paid=99.0)
        sub_biz = Subscription(user_id=user_biz.id, plan="business", billing_cycle="monthly", status="active",
                               start_date=today, end_date=today + timedelta(days=30), amount_paid=299.0)
        db.session.add_all([sub_pro, sub_biz])
        db.session.commit()

        self.assertEqual(commission_for(user_free), 10.0)
        self.assertEqual(commission_for(user_pro), 5.0)
        self.assertEqual(commission_for(user_biz), 2.0)

    # 4. Renter's settlement view does not show the platform fee
    def test_04_renter_settlement_view_hides_platform_fee(self):
        owner = self._create_user("Owner4", "9000000041")
        renter = self._create_user("Renter4", "9000000042")
        item = self._create_item(owner, title="Camera Kit", price_per_day=200.0, deposit=500.0)

        today = date.today()
        booking = Booking(
            item_id=item.id,
            renter_id=renter.id,
            start_date=today - timedelta(days=5),
            end_date=today - timedelta(days=2),
            days=3,
            total_rent=600.0,
            deposit=500.0,
            total_payable=1100.0,
            status="returned",
            commission_percent=10.0,
        )
        db.session.add(booking)
        db.session.flush()

        rec = ReturnRecord(
            booking_id=booking.id,
            actual_return_date=today - timedelta(days=2),
            late_days=0,
            late_fee_per_day=20.0,
            late_penalty=0.0,
            damage_level="none",
            damage_percent=0.0,
            damage_deduction=0.0,
            deposit_held=500.0,
            total_deductions=0.0,
            refund_amount=500.0,
            extra_due=0.0,
            platform_fee=60.0,
            owner_earning=540.0,
        )
        db.session.add(rec)
        db.session.commit()

        # View as RENTER
        self._login(phone=renter.phone, name=renter.name)
        renter_view = self.client.get(f"/bookings/{booking.id}/settlement")
        self.assertEqual(renter_view.status_code, 200)
        renter_html = renter_view.get_data(as_text=True)
        self.assertNotIn("Platform Fee", renter_html)
        self.assertNotIn("platform_fee", renter_html)
        self.assertNotIn("Owner Accounting", renter_html)

        # View as OWNER
        self._login(phone=owner.phone, name=owner.name)
        owner_view = self.client.get(f"/bookings/{booking.id}/settlement")
        self.assertEqual(owner_view.status_code, 200)
        owner_html = owner_view.get_data(as_text=True)
        self.assertIn("Platform Fee", owner_html)
        self.assertIn("Net Owner Earning", owner_html)

    # 5. Cancelling keeps the plan active until end_date
    def test_05_cancelling_keeps_plan_active_until_end_date(self):
        user = self._create_user("User5", "9000000050")
        today = date.today()
        end_date = today + timedelta(days=25)

        sub = Subscription(
            user_id=user.id,
            plan="pro",
            billing_cycle="monthly",
            status="active",
            start_date=today - timedelta(days=5),
            end_date=end_date,
            amount_paid=99.0,
        )
        db.session.add(sub)
        db.session.commit()

        self._login(phone=user.phone, name=user.name)
        cancel_res = self.client.post("/subscription/cancel", follow_redirects=True)
        self.assertEqual(cancel_res.status_code, 200)

        db.session.refresh(sub)
        self.assertEqual(sub.status, "cancelled")
        # Plan stays active until end_date
        self.assertEqual(user.current_plan(), "pro")
        self.assertIn(str(end_date), cancel_res.get_data(as_text=True))

    # 6. An expired plan hides extra items from /browse but deletes nothing
    def test_06_expired_plan_hides_extra_items_from_browse(self):
        owner = self._create_user("Owner6", "9000000060")
        items = []
        for i in range(7):
            items.append(self._create_item(owner, title=f"ExpItem_{i+1:02d}"))

        today = date.today()
        # Subscription expired yesterday
        sub = Subscription(
            user_id=owner.id,
            plan="pro",
            billing_cycle="monthly",
            status="expired",
            start_date=today - timedelta(days=35),
            end_date=today - timedelta(days=1),
            amount_paid=99.0,
        )
        db.session.add(sub)
        db.session.commit()

        # Database still has all 7 items (nothing deleted)
        self.assertEqual(Item.query.filter_by(owner_id=owner.id).count(), 7)
        self.assertEqual(owner.current_plan(), "free")

        # Public browse should only show oldest 5 items (Free limit)
        res = self.client.get("/browse")
        html = res.get_data(as_text=True)

        for i in range(5):
            self.assertIn(f"ExpItem_{i+1:02d}", html)

        self.assertNotIn("ExpItem_06", html)
        self.assertNotIn("ExpItem_07", html)

    # 7. Business items come first only with the default sort
    def test_07_business_items_first_only_on_default_sort(self):
        owner_normal = self._create_user("OwnerNorm", "9000000071", lat=12.9716, lng=77.5946)
        owner_biz = self._create_user("OwnerBiz", "9000000072", lat=13.1000, lng=77.6000)

        today = date.today()
        sub_biz = Subscription(
            user_id=owner_biz.id,
            plan="business",
            billing_cycle="monthly",
            status="active",
            start_date=today,
            end_date=today + timedelta(days=30),
            amount_paid=299.0,
        )
        db.session.add(sub_biz)
        db.session.commit()

        # Normal owner item: cheaper (₹50) and closer
        item_normal = self._create_item(owner_normal, title="Normal Affordable Item", price_per_day=50.0)
        # Business owner item: more expensive (₹500)
        item_biz = self._create_item(owner_biz, title="Business Premium Item", price_per_day=500.0)

        # Default sort: Business item comes first
        def_res = self.client.get("/browse")
        def_html = def_res.get_data(as_text=True)
        pos_biz = def_html.find("Business Premium Item")
        pos_norm = def_html.find("Normal Affordable Item")
        self.assertTrue(pos_biz != -1 and pos_norm != -1)
        self.assertLess(pos_biz, pos_norm, "Business item must appear before Normal item on default sort")

        # Cheapest sort: Normal item (₹50) must come before Business item (₹500)
        cheap_res = self.client.get("/browse?sort=cheapest")
        cheap_html = cheap_res.get_data(as_text=True)
        pos_cheap_biz = cheap_html.find("Business Premium Item")
        pos_cheap_norm = cheap_html.find("Normal Affordable Item")
        self.assertLess(pos_cheap_norm, pos_cheap_biz, "Cheapest sort must put affordable item first")

    # 8. Feedback works for guest and logged-in user, 6th in hour blocked, 5 char rejected
    def test_08_feedback_guest_user_rate_limit_and_length(self):
        # 1. Reject 5-character message
        short_res = self.client.post("/feedback", json={"message": "Short", "type": "bug"})
        self.assertEqual(short_res.status_code, 400)
        self.assertIn("between 10 and 500 characters", short_res.get_json()["error"])

        # 2. Guest submit works
        guest_res = self.client.post("/feedback", json={"message": "Guest feedback with sufficient text", "type": "suggestion"})
        self.assertEqual(guest_res.status_code, 201)
        self.assertTrue(guest_res.get_json()["success"])

        # 3. Logged in user works
        user = self._create_user("UserFeedback", "9000000080")
        self._login(phone=user.phone, name=user.name)

        user_res = self.client.post("/feedback", json={"message": "User feedback submission 1 valid", "type": "complaint"})
        self.assertEqual(user_res.status_code, 201)

        # Submit 4 more (making total 5 for this user)
        for i in range(2, 6):
            r = self.client.post("/feedback", json={"message": f"User feedback submission {i} valid", "type": "other"})
            self.assertEqual(r.status_code, 201)

        # 6th submission in the hour must be blocked
        blocked_res = self.client.post("/feedback", json={"message": "User feedback submission 6 blocked", "type": "other"})
        self.assertEqual(blocked_res.status_code, 429)
        self.assertIn("Rate limit exceeded", blocked_res.get_json()["error"])

    # 9. /admin gives 403 for a normal user and 200 for admin
    def test_09_admin_access_control(self):
        normal_user = self._create_user("NormalUser", "9000000091", is_admin=False)
        admin_user = self._create_user("AdminUser", "9999999999", is_admin=True)

        # Normal user -> 403 Forbidden
        self._login(phone=normal_user.phone, name=normal_user.name)
        res_normal = self.client.get("/admin")
        self.assertEqual(res_normal.status_code, 403)

        res_fb_normal = self.client.get("/admin/feedback")
        self.assertEqual(res_fb_normal.status_code, 403)

        # Admin user -> 200 OK
        self._login(phone=admin_user.phone, name=admin_user.name)
        res_admin = self.client.get("/admin")
        self.assertEqual(res_admin.status_code, 200)

        res_fb_admin = self.client.get("/admin/feedback")
        self.assertEqual(res_fb_admin.status_code, 200)

    # 10. An admin reply shows on the user's /my-feedback page
    def test_10_admin_reply_shows_on_my_feedback_page(self):
        user = self._create_user("User10", "9000000100")
        admin = self._create_user("Admin10", "9999999999", is_admin=True)

        # User creates feedback
        fb = Feedback(
            user_id=user.id,
            type="suggestion",
            rating=5,
            message="Please add UPI AutoPay for subscriptions.",
            page_url="http://localhost:5000/subscription",
            status="new",
            reply_seen=True,
        )
        db.session.add(fb)
        db.session.commit()

        # Admin logs in and replies
        self._login(phone=admin.phone, name=admin.name)
        reply_res = self.client.post(f"/admin/feedback/{fb.id}/reply", data={
            "admin_reply": "Thank you! UPI AutoPay is coming next month.",
        }, follow_redirects=True)
        self.assertEqual(reply_res.status_code, 200)

        db.session.refresh(fb)
        self.assertEqual(fb.admin_reply, "Thank you! UPI AutoPay is coming next month.")
        self.assertFalse(fb.reply_seen)

        # User logs in and visits /my-feedback
        self._login(phone=user.phone, name=user.name)
        my_fb_res = self.client.get("/my-feedback")
        self.assertEqual(my_fb_res.status_code, 200)
        self.assertIn("Thank you! UPI AutoPay is coming next month.", my_fb_res.get_data(as_text=True))

        # After viewing, reply_seen is marked True
        db.session.refresh(fb)
        self.assertTrue(fb.reply_seen)


if __name__ == "__main__":
    unittest.main()

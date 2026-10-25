"""Booking + payment lifecycle (sections D + E).

Razorpay runs in test mode with fake keys: the server creates nothing online
here, it only verifies signatures we compute locally. Covers the tax line,
signature verification, order mismatch, retries, idempotent webhooks
(captured / failed / refund), the cancellation audit trail, the security
deposit refund on return, and the per-user event log used by the future
Trust Score.
"""
import hashlib
import hmac
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from models import (db, Booking, Item, Payment, ReturnRecord, User,
                    UserEvent, WebhookEvent)
from utils.booking import (booking_snapshot, calculate_price, generate_order_id)
from utils.events import events_for_user

KEY_SECRET = "rzp_test_secret"
WEBHOOK_SECRET = "whsec_suite_secret"


class PaymentLifecycle(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "OTP_MODE": "demo",
            "PAYMENT_MODE": "razorpay",
            "RAZORPAY_KEY_ID": "rzp_test_key",
            "RAZORPAY_KEY_SECRET": KEY_SECRET,
            "RAZORPAY_WEBHOOK_SECRET": WEBHOOK_SECRET,
            "TAX_PERCENT": 5,
            "SECRET_KEY": "payment-tests",
            "SQLALCHEMY_DATABASE_URI":
                "sqlite:///" + os.path.join(self.tmp, "pay.db").replace("\\", "/"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.owner = User(name="Owner", phone="9000000011",
                          phone_e164="+919000000011", village_or_city="Pune",
                          role="owner", lat=18.5, lng=73.8)
        self.renter = User(name="Renter", phone="9000000012",
                           phone_e164="+919000000012", village_or_city="Pune",
                           role="renter", lat=18.5, lng=73.8)
        db.session.add_all([self.owner, self.renter])
        db.session.commit()
        self.item = Item(owner_id=self.owner.id, category="electronics",
                         title="Camera", price_per_day=100.0, deposit=500.0,
                         late_fee_per_day=50.0, delivery_available=False,
                         cod_available=True)
        db.session.add(self.item)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers ---------------------------------------------------------
    def _login(self, phone):
        self.client.get("/logout")
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        return self.client.post("/login", data={"otp": "1234"},
                                follow_redirects=True)

    def _booking(self, status="pending_payment", payment_status="pending",
                 offset=2, days=2, **extra):
        start = date.today() + timedelta(days=offset)
        end = start + timedelta(days=days)
        pricing = calculate_price(self.item, start, end, user=self.renter)
        booking = Booking(
            item_id=self.item.id, renter_id=self.renter.id,
            start_date=start, end_date=end, order_id=generate_order_id(),
            payment_status=payment_status, **booking_snapshot(pricing),
            status=status, **extra)
        db.session.add(booking)
        db.session.commit()
        return booking

    def _paid_row(self, booking, provider="mock", provider_payment_id=None):
        row = Payment(booking_id=booking.id, order_id=booking.order_id,
                      attempt_no=1, method="cash", amount=booking.total_payable,
                      status="paid", provider=provider,
                      provider_payment_id=provider_payment_id,
                      paid_at=datetime.utcnow())
        db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def _signature(order_id, payment_id, secret=KEY_SECRET):
        return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(),
                        hashlib.sha256).hexdigest()

    def _webhook(self, event_id, event_type, payload, secret=WEBHOOK_SECRET):
        body = json.dumps({"id": event_id, "event": event_type,
                           "payload": payload}).encode()
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return self.client.post("/webhooks/razorpay", data=body,
                                content_type="application/json",
                                headers={"X-Razorpay-Signature": signature})

    # -- 1. price breakdown includes the tax line -------------------------
    def test_01_price_breakdown_includes_tax(self):
        start = date.today() + timedelta(days=2)
        pricing = calculate_price(self.item, start, start + timedelta(days=2),
                                  user=self.renter)
        self.assertAlmostEqual(pricing["tax_amount"],
                               round(pricing["rent"] * 0.05, 2))
        self.assertAlmostEqual(
            pricing["total_payable"],
            round(pricing["rent"] + pricing["deposit"]
                  + pricing["delivery_charge"] + pricing["platform_fee"]
                  + pricing["tax_amount"], 2))
        booking = self._booking()
        self.assertAlmostEqual(booking.tax_amount, pricing["tax_amount"])
        self.assertAlmostEqual(booking.total_payable, pricing["total_payable"])

    # -- 2. the pay page shows the breakdown and reuses the server order --
    def test_02_pay_page_shows_tax_and_reuses_order(self):
        booking = self._booking(razorpay_order_id="order_REUSE1")
        self._login(self.renter.phone)
        resp = self.client.get(f"/bookings/{booking.id}/pay")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Taxes", resp.data)
        self.assertIn(b"order_REUSE1", resp.data)
        self.assertEqual(Booking.query.get(booking.id).razorpay_order_id,
                         "order_REUSE1")

    # -- 3. signed payment confirms the booking and writes events ---------
    def test_03_signature_verified_payment_confirms(self):
        booking = self._booking(razorpay_order_id="order_SIG1")
        self._login(self.renter.phone)
        resp = self.client.post(f"/bookings/{booking.id}/pay", data={
            "method": "upi",
            "razorpay_order_id": "order_SIG1",
            "razorpay_payment_id": "pay_SIG1",
            "razorpay_signature": self._signature("order_SIG1", "pay_SIG1"),
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        db.session.expire_all()
        booking = Booking.query.get(booking.id)
        self.assertEqual(booking.status, "requested")
        self.assertEqual(booking.payment_status, "paid")
        paid = Payment.query.filter_by(booking_id=booking.id, status="paid").one()
        self.assertTrue(paid.signature_verified)
        self.assertEqual(paid.gateway_order_id, "order_SIG1")
        self.assertEqual(paid.provider_payment_id, "pay_SIG1")
        self.assertIsNotNone(paid.paid_at)
        paid_events = UserEvent.query.filter_by(booking_id=booking.id,
                                                kind="payment_paid").all()
        self.assertEqual(len(paid_events), 1)

        receipt = self.client.get(f"/bookings/{booking.id}/receipt")
        self.assertEqual(receipt.status_code, 200)
        self.assertIn(b"Taxes", receipt.data)
        kinds = {e.kind for e in events_for_user(self.renter)}
        self.assertIn("payment_paid", kinds)

    # -- 4. bad signatures / wrong order never mark anything paid ---------
    def test_04_bad_signature_and_order_mismatch_are_rejected(self):
        booking = self._booking(razorpay_order_id="order_BAD1")
        self._login(self.renter.phone)
        self.client.post(f"/bookings/{booking.id}/pay", data={
            "method": "upi", "razorpay_order_id": "order_BAD1",
            "razorpay_payment_id": "pay_BAD1",
            "razorpay_signature": "tampered",
        }, follow_redirects=True)
        db.session.expire_all()
        self.assertEqual(Booking.query.get(booking.id).status, "pending_payment")
        failed = Payment.query.filter_by(booking_id=booking.id).one()
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.failure_code, "signature_failed")

        self.client.post(f"/bookings/{booking.id}/pay", data={
            "method": "upi", "razorpay_order_id": "order_OTHER",
            "razorpay_payment_id": "pay_BAD2",
            "razorpay_signature": self._signature("order_OTHER", "pay_BAD2"),
        }, follow_redirects=True)
        db.session.expire_all()
        second = Payment.query.filter_by(booking_id=booking.id)\
            .order_by(Payment.attempt_no.desc()).first()
        self.assertEqual(second.failure_code, "order_mismatch")
        self.assertEqual(Booking.query.get(booking.id).payment_status, "pending")
        self.assertEqual(
            UserEvent.query.filter_by(booking_id=booking.id,
                                      kind="payment_failed").count(), 2)

    # -- 5. retries: fail once, then pay ---------------------------------
    def test_05_retry_after_failure_succeeds(self):
        booking = self._booking(razorpay_order_id="order_RETRY1")
        self._login(self.renter.phone)
        self.client.post(f"/bookings/{booking.id}/pay", data={
            "method": "upi", "razorpay_order_id": "order_RETRY1",
            "razorpay_payment_id": "pay_RETRY1", "razorpay_signature": "nope",
        }, follow_redirects=True)
        self.client.post(f"/bookings/{booking.id}/pay", data={
            "method": "upi", "razorpay_order_id": "order_RETRY1",
            "razorpay_payment_id": "pay_RETRY2",
            "razorpay_signature": self._signature("order_RETRY1", "pay_RETRY2"),
        }, follow_redirects=True)
        db.session.expire_all()
        rows = Payment.query.filter_by(booking_id=booking.id)\
            .order_by(Payment.attempt_no).all()
        self.assertEqual([r.status for r in rows], ["failed", "paid"])
        self.assertEqual(len({r.attempt_no for r in rows}), 2)
        self.assertEqual(Booking.query.get(booking.id).payment_status, "paid")

    # -- 6. webhooks: signature, capture, idempotency ---------------------
    def test_06_webhook_captured_is_idempotent(self):
        booking = self._booking(razorpay_order_id="order_WH1")
        payload = {"payment": {"entity": {
            "id": "pay_WH1", "order_id": "order_WH1",
            "amount": int(round(float(booking.total_payable) * 100)),
            "method": "upi",
        }}}
        first = self._webhook("evt_cap_1", "payment.captured", payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["status"], "paid")
        db.session.expire_all()
        self.assertEqual(Booking.query.get(booking.id).payment_status, "paid")
        self.assertEqual(Booking.query.get(booking.id).status, "requested")
        paid = Payment.query.filter_by(booking_id=booking.id, status="paid").one()
        self.assertTrue(paid.signature_verified)

        again = self._webhook("evt_cap_1", "payment.captured", payload)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.get_json()["status"], "duplicate")
        self.assertEqual(
            Payment.query.filter_by(booking_id=booking.id, status="paid").count(), 1)
        self.assertEqual(WebhookEvent.query.count(), 1)

        tampered = self.client.post("/webhooks/razorpay",
                                    data=json.dumps({"id": "evt_x"}).encode(),
                                    content_type="application/json",
                                    headers={"X-Razorpay-Signature": "bad"})
        self.assertEqual(tampered.status_code, 400)

        unknown = self._webhook("evt_unknown_1", "payment.link.paid", {})
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(unknown.get_json()["status"], "ignored")

    # -- 7. captured amount lower than the snapshot -----------------------
    def test_07_webhook_short_capture_is_rejected(self):
        booking = self._booking(razorpay_order_id="order_WH2")
        payload = {"payment": {"entity": {
            "id": "pay_WH2", "order_id": "order_WH2",
            "amount": int(round(float(booking.total_payable) * 100)) - 100,
            "method": "upi",
        }}}
        resp = self._webhook("evt_short_1", "payment.captured", payload)
        self.assertEqual(resp.get_json()["status"], "amount_mismatch")
        db.session.expire_all()
        row = Payment.query.filter_by(booking_id=booking.id).one()
        self.assertEqual(row.status, "failed")
        self.assertEqual(row.failure_code, "amount_mismatch")
        self.assertEqual(Booking.query.get(booking.id).payment_status, "pending")

    # -- 8. refund webhook updates the captured payment -------------------
    def test_08_webhook_refund_updates_payment(self):
        booking = self._booking(status="requested", payment_status="paid")
        self._paid_row(booking, provider="razorpay", provider_payment_id="pay_RF1")
        payload = {"refund": {"entity": {
            "id": "rfnd_1", "payment_id": "pay_RF1", "amount": 10000,
        }}}
        resp = self._webhook("evt_refund_1", "refund.processed", payload)
        self.assertEqual(resp.get_json()["status"], "refunded")
        row = Payment.query.filter_by(provider_payment_id="pay_RF1").one()
        self.assertAlmostEqual(row.refunded_amount, 100.0)
        self.assertEqual(row.refund_id, "rfnd_1")
        self.assertIsNotNone(row.refunded_at)

        again = self._webhook("evt_refund_1", "refund.processed", payload)
        self.assertEqual(again.get_json()["status"], "duplicate")
        db.session.expire_all()
        self.assertAlmostEqual(
            Payment.query.filter_by(provider_payment_id="pay_RF1").one().refunded_amount,
            100.0)

    # -- 9. cancellation records who/why and refunds ----------------------
    def test_09_cancel_records_who_why_and_refunds(self):
        booking = self._booking(status="requested", payment_status="paid")
        paid = self._paid_row(booking)
        self._login(self.renter.phone)
        resp = self.client.post(f"/bookings/{booking.id}/cancel", data={
            "reason": "plans_changed", "reason_note": "family trip",
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        db.session.expire_all()
        booking = Booking.query.get(booking.id)
        self.assertEqual(booking.status, "cancelled")
        self.assertEqual(booking.cancelled_by, self.renter.id)
        self.assertIsNotNone(booking.cancelled_at)
        self.assertEqual(booking.cancel_reason,
                         "My plans changed: family trip")
        self.assertEqual(booking.payment_status, "refunded")
        paid = Payment.query.get(paid.id)
        self.assertEqual(paid.status, "refunded")
        self.assertAlmostEqual(paid.refunded_amount, paid.amount)
        cancelled = UserEvent.query.filter_by(booking_id=booking.id,
                                              kind="booking_cancelled").one()
        detail = cancelled.get_detail()
        self.assertEqual(detail["role"], "renter")
        self.assertEqual(detail["reason"], "plans_changed")
        self.assertEqual(detail["note"], "family trip")
        self.assertEqual(
            UserEvent.query.filter_by(booking_id=booking.id,
                                      kind="payment_refunded").count(), 1)

    # -- 10. return refunds the deposit; renter completes -----------------
    def test_10_return_refunds_deposit_then_completes(self):
        booking = self._booking(status="picked_up", payment_status="paid")
        self._paid_row(booking)
        deposit_held = float(booking.deposit)   # snapshot (may include a trust discount)
        self._login(self.owner.phone)
        resp = self.client.post(f"/bookings/{booking.id}/return", data={
            "actual_return_date": booking.end_date.isoformat(),
            "damage_level": "none", "return_note": "returned in good shape",
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        db.session.expire_all()
        booking = Booking.query.get(booking.id)
        self.assertEqual(booking.status, "returned")
        record = ReturnRecord.query.filter_by(booking_id=booking.id).one()
        self.assertAlmostEqual(record.refund_amount, deposit_held)
        refund = Payment.query.filter_by(booking_id=booking.id,
                                         kind="deposit_refund").one()
        self.assertAlmostEqual(refund.amount, deposit_held)
        self.assertEqual(refund.status, "refunded")
        self.assertEqual(
            UserEvent.query.filter_by(booking_id=booking.id,
                                      kind="booking_returned").count(), 1)
        self.assertEqual(
            UserEvent.query.filter_by(booking_id=booking.id,
                                      kind="payment_refunded").count(), 1)

        self._login(self.renter.phone)
        done = self.client.post(f"/bookings/{booking.id}/complete",
                                follow_redirects=True)
        self.assertEqual(done.status_code, 200)
        db.session.expire_all()
        booking = Booking.query.get(booking.id)
        self.assertEqual(booking.status, "completed")
        self.assertIsNotNone(booking.completed_at)
        self.assertEqual(
            UserEvent.query.filter_by(booking_id=booking.id,
                                      kind="booking_completed").count(), 1)

    # -- 11. webhook refuses to run without a configured secret -----------
    def test_11_webhook_requires_configured_secret(self):
        app2 = create_app({
            "TESTING": True, "PAYMENT_MODE": "mock",
            "RAZORPAY_WEBHOOK_SECRET": "",
            "SECRET_KEY": "no-webhook-secret",
            "SQLALCHEMY_DATABASE_URI":
                "sqlite:///" + os.path.join(self.tmp, "nohook.db").replace("\\", "/"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads2"),
        })
        resp = app2.test_client().post("/webhooks/razorpay", data=b"{}",
                                       content_type="application/json")
        self.assertEqual(resp.status_code, 503)


if __name__ == "__main__":
    unittest.main()

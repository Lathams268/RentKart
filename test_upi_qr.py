"""Stage 4 tests – UPI deep link, scanner QR route, demo banner and safety.

Covers: build_upi_link encoding + amount, image/png for the renter and 403 for
others, the mock demo banner and "Simulate: I have paid" button, idempotent
payment, and that a QR request never marks a booking paid. No browser, no
network: the qrcode library renders the PNG in-process.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from datetime import date, datetime, timedelta
from app import create_app
from models import db, User, Item, Booking, Payment
from utils.booking import calculate_price, booking_snapshot, generate_order_id
from utils.upi import build_upi_link


class UpiQr(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True, "OTP_MODE": "demo", "PAYMENT_MODE": "mock",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove(); self.ctx.pop(); shutil.rmtree(self.tmp, ignore_errors=True)

    def _login(self, phone, name="U"):
        self.client.get("/logout")
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        return self.client.post("/login", data={"otp": "1234", "name": name,
                                "village_or_city": "City"}, follow_redirects=True)

    def _mk(self, phone, name="U"):
        u = User.query.filter_by(phone=phone).first()
        if not u:
            u = User(name=name, phone=phone, village_or_city="City", lat=12.9, lng=77.5)
            db.session.add(u); db.session.commit()
        return u

    def _item(self, owner):
        it = Item(owner_id=owner.id, category="electronics", title="Cam",
                  price_per_day=100.0, deposit=500.0, late_fee_per_day=50.0,
                  delivery_available=False, cod_available=True)
        db.session.add(it); db.session.commit()
        return it

    def _pending(self, renter, item):
        s = date.today() + timedelta(days=2); e = s + timedelta(days=2)
        p = calculate_price(item, s, e, user=renter, delivery_method="pickup")
        b = Booking(item_id=item.id, renter_id=renter.id, start_date=s, end_date=e,
                    order_id=generate_order_id(),
                    payment_expires_at=datetime.utcnow() + timedelta(minutes=15),
                    payment_status="pending", **booking_snapshot(p), status="pending_payment")
        db.session.add(b); db.session.commit()
        return b

    # 1. build_upi_link encodes values and amount equals booking total
    def test_01_build_upi_link_encodes_and_amount(self):
        link = build_upi_link("shop@bank", "Ravi & Co", 1250.5, "RK 001/xyz")
        self.assertTrue(link.startswith("upi://pay?"))
        self.assertIn("pa=shop%40bank", link)          # @ encoded
        self.assertIn("pn=Ravi%20%26%20Co", link)       # space and & encoded
        self.assertIn("am=1250.50", link)              # two decimals
        self.assertIn("cu=INR", link)
        self.assertIn("tn=RK%20001%2Fxyz", link)        # space and / encoded

    def test_02_link_amount_equals_booking_total(self):
        owner = self._mk("9000005001", "O"); renter = self._mk("9000005002", "R")
        item = self._item(owner); b = self._pending(renter, item)
        link = build_upi_link("demo@rentkart", "RentKart", b.total_payable, b.order_id)
        self.assertIn(f"am={float(b.total_payable):.2f}", link)

    # 2. QR route returns image/png for renter and 403 for others
    def test_03_qr_route_png_for_renter(self):
        owner = self._mk("9000005011", "O"); renter = self._mk("9000005012", "R")
        item = self._item(owner); b = self._pending(renter, item)
        self._login(renter.phone)
        resp = self.client.get(f"/bookings/{b.id}/upi-qr.png")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["Content-Type"], "image/png")
        self.assertEqual(resp.headers["Cache-Control"], "no-store")
        self.assertTrue(resp.data[:8].startswith(b"\x89PNG\r\n\x1a\n"))  # PNG magic

    def test_04_qr_route_403_for_others(self):
        owner = self._mk("9000005021", "O"); renter = self._mk("9000005022", "R")
        other = self._mk("9000005023", "X")
        item = self._item(owner); b = self._pending(renter, item)
        self._login(other.phone)
        resp = self.client.get(f"/bookings/{b.id}/upi-qr.png")
        self.assertEqual(resp.status_code, 403)

    def test_05_qr_route_404_when_not_pending(self):
        owner = self._mk("9000005031", "O"); renter = self._mk("9000005032", "R")
        item = self._item(owner); b = self._pending(renter, item)
        b.status = "requested"
        db.session.commit()
        self._login(renter.phone)
        resp = self.client.get(f"/bookings/{b.id}/upi-qr.png")
        self.assertEqual(resp.status_code, 404)

    # 3. demo banner and "Simulate: I have paid" appear in mock mode
    def test_06_mock_banner_and_simulate(self):
        owner = self._mk("9000005041", "O"); renter = self._mk("9000005042", "R")
        item = self._item(owner); b = self._pending(renter, item)
        self._login(renter.phone)
        resp = self.client.get(f"/bookings/{b.id}/pay")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Demo mode: this QR is for show, no real money is charged", resp.data)
        self.assertIn(b"Simulate: I have paid", resp.data)
        self.assertIn(b"demo@rentkart", resp.data)
        self.assertIn(b"Scan with any UPI app", resp.data)
        self.assertIn(b"upi-qr.png", resp.data)

    # 5. a QR request never marks a booking paid
    def test_07_qr_request_never_marks_paid(self):
        owner = self._mk("9000005051", "O"); renter = self._mk("9000005052", "R")
        item = self._item(owner); b = self._pending(renter, item)
        self._login(renter.phone)
        self.client.get(f"/bookings/{b.id}/upi-qr.png")
        self.client.get(f"/bookings/{b.id}/pay")
        db.session.refresh(b)
        self.assertEqual(b.status, "pending_payment")
        self.assertEqual(Payment.query.filter_by(booking_id=b.id, status="paid").count(), 0)

    # 4. paying twice is idempotent
    def test_08_paying_twice_is_idempotent(self):
        owner = self._mk("9000005061", "O"); renter = self._mk("9000005062", "R")
        item = self._item(owner); b = self._pending(renter, item)
        self._login(renter.phone)
        self.client.post(f"/bookings/{b.id}/pay",
                         data={"method": "upi", "outcome": "success"},
                         follow_redirects=True)
        db.session.refresh(b)
        self.assertEqual(b.status, "requested")
        # Second attempt on a non-pending booking is refused, no extra paid row.
        resp = self.client.post(f"/bookings/{b.id}/pay",
                                data={"method": "upi", "outcome": "success"},
                                follow_redirects=True)
        db.session.refresh(b)
        self.assertEqual(b.status, "requested")
        self.assertEqual(Payment.query.filter_by(booking_id=b.id, status="paid").count(), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

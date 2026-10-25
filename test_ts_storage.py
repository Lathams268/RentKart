"""STAGE 1 – TrustShield private evidence storage tests."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import io
import unittest, tempfile, shutil
from datetime import date, timedelta
from werkzeug.datastructures import FileStorage
from PIL import Image

from app import create_app
from models import db, User, Item, Booking, EvidenceFile
import utils.ts_evidence as ts_ev
from seed import seed as run_seed


def _jpeg_bytes(with_exif=False, size=(200, 160)):
    img = Image.new("RGB", size, (120, 60, 200))
    buf = io.BytesIO()
    exif = None
    if with_exif:
        from PIL.ExifTags import Base as ExifBase
        exif = img.getexif()
        exif[ExifBase.Make] = "SECRET-CAMERA"
        exif[ExifBase.Model] = "GPS-LEAKER"
    img.save(buf, format="JPEG", exif=exif) if exif else img.save(buf, format="JPEG")
    return buf.getvalue()


class TestTsStorage(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "OTP_MODE": "demo",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "t.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
            "SERVER_NAME": "localhost",
        })
        self.ctx = self.app.app_context()
        self.ctx.push()
        run_seed()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _login(self, phone, name="T"):
        self.client.get("/logout")
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        return self.client.post("/login", data={"otp": "1234", "name": name,
                                                "village_or_city": "City"},
                                follow_redirects=True)

    # 1. stored outside static, random name, EXIF stripped
    def test_photo_stored_private_random_no_exif(self):
        fs = FileStorage(io.BytesIO(_jpeg_bytes(with_exif=True)), filename="my_photo.jpg")
        stored_name, nbytes = ts_ev.save_image(self.app, fs, max_mb=6)
        path = ts_ev.abs_path(self.app, stored_name)
        self.assertNotIn("static", path.replace("\\", "/").split("/evidence")[0])
        self.assertIn(os.path.join("instance", "evidence"), path)
        # random uuid-ish name, nothing to do with original filename
        self.assertTrue(stored_name.startswith("photo_"))
        self.assertNotIn("my_photo", stored_name)
        self.assertGreater(nbytes, 0)
        # no EXIF survives re-encode
        with Image.open(path) as img:
            self.assertEqual(dict(img.getexif()), {})

    # 2. a text file renamed .jpg is rejected
    def test_text_as_jpg_rejected(self):
        fs = FileStorage(io.BytesIO(b"this is definitely not an image"), filename="evil.jpg")
        with self.assertRaises(ValueError):
            ts_ev.save_image(self.app, fs, max_mb=6)

    # 3. oversize rejected
    def test_oversize_rejected(self):
        payload = _jpeg_bytes() + b"\x00" * (2 * 1024 * 1024)
        fs = FileStorage(io.BytesIO(payload), filename="big.jpg")
        with self.assertRaises(ValueError):
            ts_ev.save_image(self.app, fs, max_mb=1)

    # 4. a third user gets 403; renter/owner/admin can view
    def test_evidence_access_control(self):
        owner = User.query.filter_by(phone="9000000001").first()
        renter = User.query.filter_by(phone="9000000003").first()
        outsider = User(name="Outsider", phone="9111119999", village_or_city="X",
                        lat=12.9, lng=77.5)
        db.session.add(outsider)
        item = Item.query.filter_by(owner_id=owner.id).first()
        b = Booking(item_id=item.id, renter_id=renter.id,
                    start_date=date.today() + timedelta(days=1),
                    end_date=date.today() + timedelta(days=2), days=2,
                    total_rent=100.0, deposit=100.0, total_payable=200.0,
                    status="approved", trustshield=True)
        db.session.add(b)
        db.session.commit()

        fs = FileStorage(io.BytesIO(_jpeg_bytes()), filename="cond.jpg")
        stored_name, nbytes = ts_ev.save_image(self.app, fs)
        ev = EvidenceFile(booking_id=b.id, item_id=item.id, kind="photo",
                          angle="front", stored_name=stored_name, size_bytes=nbytes)
        db.session.add(ev)
        db.session.commit()

        self._login("9111119999")
        self.assertEqual(self.client.get(f"/evidence/{ev.id}").status_code, 403)

        self._login("9000000003")
        self.assertEqual(self.client.get(f"/evidence/{ev.id}").status_code, 200)

        self._login("9000000001")
        self.assertEqual(self.client.get(f"/evidence/{ev.id}").status_code, 200)

        self._login("9999999999")
        self.assertEqual(self.client.get(f"/evidence/{ev.id}").status_code, 200)


if __name__ == "__main__":
    unittest.main()

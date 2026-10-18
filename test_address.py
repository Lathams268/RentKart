"""Stage 1 tests – Address model, validation and the /addresses CRUD page."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from app import create_app
from models import db, User, Address
from utils.address import validate_address


class AddressTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True, "OTP_MODE": "demo",
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
        self.client.post("/login", data={"otp": "1234", "name": name,
                                "village_or_city": "Bengaluru"}, follow_redirects=True)

    def _mk(self, phone, name="U"):
        u = User.query.filter_by(phone=phone).first()
        if not u:
            u = User(name=name, phone=phone, village_or_city="Bengaluru", lat=12.9, lng=77.5)
            db.session.add(u); db.session.commit()
        return u

    def _good(self):
        return {"label": "Home", "full_name": "Ravi", "phone": "9876543210",
                "house_no": "12", "street": "MG Road", "city": "Bengaluru",
                "state": "Karnataka", "pincode": "560001"}

    # ---- validate_address (pure) ----
    def test_01_validate_good(self):
        clean, errors = validate_address(self._good())
        self.assertEqual(errors, {})
        self.assertEqual(clean["pincode"], "560001")
        self.assertEqual(clean["state"], "Karnataka")

    def test_02_validate_bad_fields(self):
        d = self._good()
        d.update({"pincode": "012345", "phone": "12345", "house_no": "", "state": ""})
        clean, errors = validate_address(d)
        self.assertIn("pincode", errors)   # leading zero rejected
        self.assertIn("phone", errors)
        self.assertIn("house_no", errors)
        self.assertIn("state", errors)

    def test_03_validate_state_must_be_known(self):
        d = self._good(); d["state"] = "Atlantis"
        clean, errors = validate_address(d)
        self.assertIn("state", errors)

    def test_04_trims_to_120(self):
        d = self._good(); d["street"] = "X" * 200
        clean, errors = validate_address(d)
        self.assertEqual(len(clean["street"]), 120)

    # ---- routes ----
    def test_05_add_valid_saves_and_default(self):
        u = self._mk("9000003001", "Ravi"); self._login(u.phone)
        resp = self.client.post("/addresses", data=self._good(), follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        a = Address.query.filter_by(user_id=u.id).first()
        self.assertIsNotNone(a)
        self.assertTrue(a.is_default)  # first address becomes default

    def test_06_add_invalid_shows_field_errors(self):
        u = self._mk("9000003002", "Ravi"); self._login(u.phone)
        bad = self._good(); bad["pincode"] = "abc"; bad["phone"] = "99"
        resp = self.client.post("/addresses", data=bad)
        self.assertEqual(resp.status_code, 400)
        body = resp.data.decode("utf-8")
        self.assertIn("PIN code", body)
        self.assertEqual(Address.query.count(), 0)

    def test_07_other_user_cannot_change(self):
        owner = self._mk("9000003003", "Owner")
        other = self._mk("9000003004", "Other")
        a = Address(user_id=owner.id, **self._good())
        db.session.add(a); db.session.commit()
        self._login(other.phone)
        for path in (f"/addresses/{a.id}/edit", f"/addresses/{a.id}/delete",
                     f"/addresses/{a.id}/default"):
            r = self.client.post(path, data=self._good())
            self.assertEqual(r.status_code, 403, path)
        # owner can
        self._login(owner.phone)
        r = self.client.post(f"/addresses/{a.id}/default", data={})
        self.assertEqual(r.status_code, 302)

    def test_08_owner_edit_updates(self):
        u = self._mk("9000003005", "Owner")
        a = Address(user_id=u.id, **self._good())
        db.session.add(a); db.session.commit()
        self._login(u.phone)
        upd = self._good(); upd["city"] = "Mysuru"
        r = self.client.post(f"/addresses/{a.id}/edit", data=upd, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        db.session.refresh(a)
        self.assertEqual(a.city, "Mysuru")


if __name__ == "__main__":
    unittest.main(verbosity=2)

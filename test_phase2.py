"""Phase-2 tests – browse, filters, sorting, distances, seed."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil, json
from app import create_app
from models import db, User, Item
from seed import seed as run_seed
import config


class RentKartPhase2(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
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

    # --- helpers ---
    def _seed(self):
        run_seed()

    def _login(self, phone="9000000004"):
        """Log in as seeded user Priya (Bengaluru city)."""
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        self.client.post("/login", data={
            "otp": "1234",
            "name": "Priya",
            "village_or_city": "Bengaluru",
        }, follow_redirects=True)

    # --- tests ---
    def test_01_seed_creates_15_items(self):
        self._seed()
        self.assertEqual(Item.query.count(), 15)
        self.assertEqual(User.query.count(), 4)
        # Running again should skip
        run_seed()
        self.assertEqual(Item.query.count(), 15)

    def test_02_browse_shows_all_and_distance(self):
        """Browse with lat/lng shows all 15 items and distance badges."""
        self._seed()
        # Bengaluru centre coords
        resp = self.client.get("/browse?lat=12.9716&lng=77.5946")
        self.assertEqual(resp.status_code, 200)
        # All 15 available items should appear
        for item in Item.query.all():
            self.assertIn(item.title.encode(), resp.data)
        # At least one "km" badge should be present
        self.assertIn(b"km", resp.data)

    def test_03_filter_category(self):
        self._seed()
        resp = self.client.get("/browse?category=books")
        self.assertEqual(resp.status_code, 200)
        # Should contain book titles
        self.assertIn(b"Engineering Maths", resp.data)
        # Should NOT contain clothes titles
        self.assertNotIn(b"Silk Lehenga", resp.data)

    def test_04_filter_search(self):
        self._seed()
        resp = self.client.get("/browse?search=camera")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Canon DSLR Camera", resp.data)
        self.assertNotIn(b"Silk Lehenga", resp.data)

    def test_05_filter_max_distance(self):
        """Max distance=5 km from Bengaluru centre should exclude far-away items."""
        self._seed()
        resp = self.client.get("/browse?lat=12.9716&lng=77.5946&max_dist=5")
        self.assertEqual(resp.status_code, 200)
        # Priya's items (Bengaluru city, ~0km) should appear
        self.assertIn(b"Canon DSLR Camera", resp.data)
        # Ramesh's items in Hoskote (~30km) should not
        self.assertNotIn(b"Tractor Rotavator", resp.data)

    def test_06_filter_max_price(self):
        self._seed()
        resp = self.client.get("/browse?max_price=100")
        self.assertEqual(resp.status_code, 200)
        # Cheap items should appear
        self.assertIn(b"Engineering Maths", resp.data)   # ₹20/day
        # Expensive items should not
        self.assertNotIn(b"Shamiyana Tent", resp.data)   # ₹2000/day

    def test_07_combined_filters(self):
        """Combining category + max_price narrows results."""
        self._seed()
        resp = self.client.get("/browse?category=clothes&max_price=500")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Silk Lehenga", resp.data)        # ₹500 clothes
        self.assertIn(b"Pattu Saree", resp.data)          # ₹400 clothes
        self.assertNotIn(b"Designer Sherwani", resp.data) # ₹800 clothes
        self.assertNotIn(b"Engineering Maths", resp.data) # wrong category

    def test_08_sort_nearest(self):
        """Sort nearest: items closer to given location come first."""
        self._seed()
        resp = self.client.get("/browse?lat=12.9716&lng=77.5946&sort=nearest")
        data = resp.data.decode()
        # Priya (Bengaluru) items should appear before Ramesh (Hoskote) items
        pos_priya = data.index("Canon DSLR Camera")
        pos_ramesh = data.index("Tractor Rotavator")
        self.assertLess(pos_priya, pos_ramesh)

    def test_09_sort_cheapest(self):
        """Sort cheapest: lowest price first."""
        self._seed()
        resp = self.client.get("/browse?sort=cheapest")
        data = resp.data.decode()
        # ₹10/day NCERT should appear before ₹2000/day Shamiyana
        pos_cheap = data.index("NCERT Physics")
        pos_expensive = data.index("Shamiyana Tent")
        self.assertLess(pos_cheap, pos_expensive)

    def test_10_browse_no_location(self):
        """Browse without location doesn't crash and shows all items."""
        self._seed()
        resp = self.client.get("/browse")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Silk Lehenga", resp.data)


if __name__ == "__main__":
    unittest.main(verbosity=2)

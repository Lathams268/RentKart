"""Phase-5 tests – digital shop with QR & WhatsApp share, voice search, and Leaflet map view."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from app import create_app
from models import db, User, Item
from utils.shop import generate_shop_slug


class RentKartPhase5(unittest.TestCase):

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
    def _login(self, phone="9999999999", name="Test User", village="TestCity"):
        self.client.get("/logout")
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        return self.client.post("/login", data={
            "otp": "1234",
            "name": name,
            "village_or_city": village,
        }, follow_redirects=True)

    def _create_user(self, name, phone, village="TestCity", lat=12.9716, lng=77.5946):
        user = User(name=name, phone=phone, village_or_city=village, lat=lat, lng=lng)
        db.session.add(user)
        db.session.commit()
        return user

    def _create_item(self, owner, title="Heavy Tractor Rotavator", category="farm_tools",
                     price_per_day=1500.0, deposit=5000.0, lat=12.9716, lng=77.5946):
        item = Item(
            owner_id=owner.id,
            category=category,
            title=title,
            description="High power farm equipment",
            price_per_day=price_per_day,
            deposit=deposit,
            lat=lat,
            lng=lng,
            is_available=True,
        )
        db.session.add(item)
        db.session.commit()
        return item

    # 1. creating a shop generates a unique slug, and a duplicate name gets a different slug
    def test_01_create_shop_generates_unique_slug_and_handles_duplicates(self):
        # User 1 creates shop
        self._login(phone="9000000001", name="Ramesh", village="Hoskote")
        res1 = self.client.post("/shop/create", data={
            "shop_name": "Ramesh Rental Hub",
            "shop_description": "Top quality machinery and tools for rent.",
        }, follow_redirects=True)
        self.assertEqual(res1.status_code, 200)

        user1 = User.query.filter_by(phone="9000000001").first()
        self.assertIsNotNone(user1.shop_slug)
        self.assertEqual(user1.shop_slug, "ramesh-rental-hub")
        self.assertEqual(user1.shop_name, "Ramesh Rental Hub")

        # User 2 creates shop with identical name -> duplicate gets different slug
        self._login(phone="9000000002", name="Ramesh Kumar", village="Devanahalli")
        res2 = self.client.post("/shop/create", data={
            "shop_name": "Ramesh Rental Hub",
            "shop_description": "Another branch of rentals.",
        }, follow_redirects=True)
        self.assertEqual(res2.status_code, 200)

        user2 = User.query.filter_by(phone="9000000002").first()
        self.assertIsNotNone(user2.shop_slug)
        self.assertNotEqual(user2.shop_slug, user1.shop_slug)
        self.assertEqual(user2.shop_slug, "ramesh-rental-hub-1")

        # Test slug generator directly
        slug3 = generate_shop_slug("Ramesh Rental Hub")
        self.assertEqual(slug3, "ramesh-rental-hub-2")

    # 2. /shop/<slug> opens without login and shows the owner's items
    def test_02_shop_page_opens_without_login_and_shows_items(self):
        owner = self._create_user(name="Priya", phone="9000000003", village="Bengaluru")
        owner.shop_name = "Priya Glamour Studio"
        owner.shop_slug = "priya-glamour-studio"
        owner.shop_description = "Designer dresses and bridal jewelry"
        db.session.commit()

        item = self._create_item(owner, title="Bridal Silk Lehenga", category="clothes")

        # Ensure logged out
        self.client.get("/logout")

        res = self.client.get(f"/shop/{owner.shop_slug}")
        self.assertEqual(res.status_code, 200)
        content = res.data.decode("utf-8")
        self.assertIn("Priya Glamour Studio", content)
        self.assertIn("Bridal Silk Lehenga", content)
        self.assertIn("Bengaluru", content)

    # 3. /shop/<slug>/qr returns an image (content type image/png)
    def test_03_shop_qr_returns_png_image(self):
        owner = self._create_user(name="Suresh", phone="9000000004", village="Anekal")
        owner.shop_name = "Suresh Sound Systems"
        owner.shop_slug = "suresh-sound-systems"
        db.session.commit()

        res = self.client.get(f"/shop/{owner.shop_slug}/qr")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.content_type.startswith("image/png") or res.mimetype == "image/png")
        # Validate PNG magic bytes
        self.assertTrue(res.data.startswith(b"\x89PNG\r\n\x1a\n"))

    # 4. /shop/<slug>/poster returns 200
    def test_04_shop_poster_returns_200(self):
        owner = self._create_user(name="Anil", phone="9000000005", village="Kolar")
        owner.shop_name = "Anil Agro Rentals"
        owner.shop_slug = "anil-agro-rentals"
        db.session.commit()

        res = self.client.get(f"/shop/{owner.shop_slug}/poster")
        self.assertEqual(res.status_code, 200)
        content = res.data.decode("utf-8")
        self.assertIn("Scan to rent from us", content)
        self.assertIn("Anil Agro Rentals", content)
        self.assertIn("window.print", content)

    # 5. the WhatsApp link on the shop page contains wa.me and the shop link
    def test_05_whatsapp_link_contains_wa_me_and_shop_link(self):
        owner = self._create_user(name="Kavita", phone="9000000006", village="Mysuru")
        owner.shop_name = "Kavita Events"
        owner.shop_slug = "kavita-events"
        db.session.commit()

        res = self.client.get(f"/shop/{owner.shop_slug}")
        self.assertEqual(res.status_code, 200)
        content = res.data.decode("utf-8")
        self.assertIn("wa.me", content)
        self.assertIn("kavita-events", content)

    # 6. /browse?q=tractor (and a Hindi word) applies the farm_tools category
    def test_06_voice_search_applies_category(self):
        owner = self._create_user(name="Owner", phone="9000000007")
        self._create_item(owner, title="45 HP Tractor", category="farm_tools")
        self._create_item(owner, title="Silk Saree", category="clothes")

        # English voice keyword
        res_en = self.client.get("/browse?q=tractor")
        self.assertEqual(res_en.status_code, 200)
        content_en = res_en.data.decode("utf-8")
        self.assertIn("45 HP Tractor", content_en)
        self.assertNotIn("Silk Saree", content_en)

        # Hindi voice keyword
        res_hi = self.client.get("/browse?q=ट्रैक्टर")
        self.assertEqual(res_hi.status_code, 200)
        content_hi = res_hi.data.decode("utf-8")
        self.assertIn("45 HP Tractor", content_hi)
        self.assertNotIn("Silk Saree", content_hi)

    # 7. /browse?view=map returns 200 and includes marker data
    def test_07_browse_map_view_returns_marker_data(self):
        owner = self._create_user(name="MapOwner", phone="9000000008", lat=12.9716, lng=77.5946)
        self._create_item(owner, title="JBL Party Speaker", category="electronics", lat=12.9716, lng=77.5946)

        res = self.client.get("/browse?view=map")
        self.assertEqual(res.status_code, 200)
        content = res.data.decode("utf-8")
        self.assertIn('id="map"', content)
        self.assertIn("JBL Party Speaker", content)
        self.assertIn("77.5946", content)


if __name__ == "__main__":
    unittest.main()

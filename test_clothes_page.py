"""Stage 2 (clothes redesign) – the mobile clothes marketplace page layout.

Covers: /browse?category=clothes and /clothes return 200 for every tab; the
HTML has one card per product (name, owner, rupee price, rating badge,
availability, link); the grid is 2 columns on mobile and more on larger
widths; discounted cards show the OFF text and the struck original; the page
never renders a single large image; filters + sort + tab combine; other
categories keep their current browse layout; card links still go to the item
page.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from datetime import date, timedelta, datetime

from app import create_app
from models import db, User, Item, Booking, Review
from utils.booking import generate_order_id


class ClothesPageTest(unittest.TestCase):

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

    # --- helpers ---
    def _owner(self, phone, name):
        u = User(name=name, phone=phone, village_or_city="City", lat=12.9, lng=77.5)
        db.session.add(u); db.session.commit()
        return u

    def _item(self, owner, gender, title, price=500.0, discount=None,
              available=True, color="Red", ctype="Saree"):
        it = Item(owner_id=owner.id, category="clothes", title=title,
                  price_per_day=price, deposit=1000.0, late_fee_per_day=0.0,
                  delivery_available=False, cod_available=True,
                  discount_percent=discount, is_available=available)
        it.set_attributes({"gender": gender, "clothing_type": ctype, "color": color})
        db.session.add(it); db.session.commit()
        return it

    def _rate(self, item, rating=5):
        """Attach a returned booking + review so review_stats shows an average."""
        renter = self._owner("92" + str(item.id) + "000000"[:4], "Renter")
        s = date.today() - timedelta(days=10)
        b = Booking(item_id=item.id, renter_id=renter.id, start_date=s,
                    end_date=s + timedelta(days=2), days=3, total_rent=100.0,
                    deposit=0.0, total_payable=100.0, status="returned",
                    payment_status="paid", order_id=generate_order_id())
        db.session.add(b); db.session.commit()
        r = Review(booking_id=b.id, reviewer_id=renter.id, owner_id=item.owner_id,
                   rating=rating, comment="Great")
        db.session.add(r); db.session.commit()

    def _book_today(self, item):
        """An approved booking covering today -> shows as Rented out."""
        renter = self._owner("93" + str(item.id) + "000000"[:4], "R2")
        s = date.today()
        b = Booking(item_id=item.id, renter_id=renter.id, start_date=s,
                    end_date=s + timedelta(days=3), days=4, total_rent=200.0,
                    deposit=0.0, total_payable=200.0, status="approved",
                    payment_status="paid", order_id=generate_order_id())
        db.session.add(b); db.session.commit()

    # --- routes reachable ---
    def test_01_all_tabs_return_200(self):
        o = self._owner("9111111101", "Aisha Creations")
        self._item(o, "Women", "Silk Saree")
        for tab in ("men", "women", "children"):
            self.assertEqual(self.client.get(f"/browse?category=clothes&tab={tab}").status_code, 200)
        self.assertEqual(self.client.get("/clothes").status_code, 200)
        self.assertEqual(self.client.get("/clothes?tab=men").status_code, 200)

    def test_02_card_has_all_parts(self):
        o = self._owner("9111111102", "Bella Wardrobe")
        it = self._item(o, "Women", "Designer Lehenga", price=1200.0)
        self._rate(it, 5)
        html = self.client.get("/browse?category=clothes&tab=women").data.decode("utf-8")
        self.assertIn("Designer Lehenga", html)
        self.assertIn("Bella Wardrobe", html)          # owner name
        self.assertIn("₹1,200", html)                  # rupee price
        self.assertIn("/items/%d" % it.id, html)      # link to item page
        self.assertIn("Available", html)              # availability pill
        self.assertIn("★", html.replace("&#9733;", "★"))  # rating badge (star)

    def test_03_new_badge_when_no_reviews(self):
        o = self._owner("9111111103", "Chic Corner")
        self._item(o, "Women", "Cotton Kurti", ctype="Kurti")
        html = self.client.get("/browse?category=clothes&tab=women").data.decode("utf-8")
        self.assertIn("New", html)

    def test_04_grid_columns(self):
        o = self._owner("9111111104", "Dress Line")
        self._item(o, "Women", "Party Gown", ctype="Gown")
        html = self.client.get("/browse?category=clothes&tab=women").data.decode("utf-8")
        self.assertIn("grid-cols-2", html)                 # mobile: 2 columns
        self.assertIn("md:grid-cols-3", html)              # tablet: 3 columns
        self.assertIn("min-[1200px]:grid-cols-4", html)    # desktop wide: 4 columns

    def test_05_never_single_large_image(self):
        o = self._owner("9111111105", "Ethnic Store")
        self._item(o, "Women", "Anarkali Suit", ctype="Anarkali")
        html = self.client.get("/browse?category=clothes&tab=women").data.decode("utf-8")
        self.assertNotIn("overflow-x-auto", html)          # no horizontal scroll row
        self.assertIn("aspect-ratio: 4 / 5;", html)        # card photo area is 4/5

    def test_06_discount_off_and_struck_original(self):
        o = self._owner("9111111106", "Festive Fab")
        self._item(o, "Women", "Bridal Lehenga", price=2000.0, discount=10, ctype="Lehenga")
        html = self.client.get("/browse?category=clothes&tab=women").data.decode("utf-8")
        self.assertIn("₹1,800", html)                      # effective price
        self.assertIn("10% OFF", html)
        self.assertIn("line-through", html)               # struck original
        self.assertIn("₹2,000", html)                     # original shown

    def test_07_rented_out_status(self):
        o = self._owner("9111111107", "Grace Gallery")
        off = self._item(o, "Women", "Unavailable Top", available=False, ctype="Top")
        booked = self._item(o, "Women", "Booked Today Dress", ctype="Dress")
        self._book_today(booked)
        html = self.client.get("/browse?category=clothes&tab=women").data.decode("utf-8")
        self.assertIn("Rented out", html)

    def test_08_tab_children_only_kids(self):
        o = self._owner("9111111108", "Happy Kids")
        self._item(o, "Kids", "Kids Frock", ctype="Frock")
        self._item(o, "Men", "Mens Sherwani", ctype="Sherwani")
        html = self.client.get("/browse?category=clothes&tab=children").data.decode("utf-8")
        self.assertIn("Kids Frock", html)
        self.assertNotIn("Mens Sherwani", html)

    def test_09_filters_sort_and_tab_combine(self):
        o = self._owner("9111111109", "Price Place")
        cheap = self._item(o, "Women", "Cheap Kurti", price=200.0, ctype="Kurti")
        pricey = self._item(o, "Women", "Pricey Gown", price=2000.0, ctype="Gown")
        html = self.client.get("/browse?category=clothes&tab=women&sort=cheapest&min_price=150&max_price=2500").data.decode("utf-8")
        self.assertEqual(html.index("Cheap Kurti"), min(html.index("Cheap Kurti"), html.index("Pricey Gown")))

    def test_10_other_categories_unchanged(self):
        o = self._owner("9111111110", "Book Nook")
        b = Item(owner_id=o.id, category="books", title="Some Novel",
                 price_per_day=100.0, deposit=0.0)
        b.set_attributes({"genre": "Fiction"})
        db.session.add(b); db.session.commit()
        html = self.client.get("/browse?category=books").data.decode("utf-8")
        self.assertNotIn("clothx-wrap", html)             # not the clothes layout
        self.assertNotIn(">Cloth<", html)
        cloth = self.client.get("/clothes").data.decode("utf-8")
        self.assertIn("clothx-wrap", cloth)

    def test_11_card_links_to_item_page(self):
        o = self._owner("9111111111", "Link Lab")
        it = self._item(o, "Women", "Linkable Saree")
        html = self.client.get("/clothes?tab=women").data.decode("utf-8")
        self.assertIn('href="/items/%d"' % it.id, html)


if __name__ == "__main__":
    unittest.main(verbosity=2)

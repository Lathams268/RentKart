"""Stage 3 (clothes redesign) – marketplace seed data.

Covers: running seed.py twice creates no duplicates, every tab (Men / Women /
Children) has at least 10 clothes items, and every clothes item has a whole-
rupee price (no odd decimals).
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from collections import Counter

from app import create_app
from models import db, Item
from seed import seed as run_seed
from utils.filters import cloth_tab_filter


class ClothesSeedTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.app = create_app({
            "TESTING": True, "OTP_MODE": "demo", "PAYMENT_MODE": "mock",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(cls.tmp, "test.db"),
            "UPLOAD_FOLDER": os.path.join(cls.tmp, "uploads"),
        })
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        db.create_all()

    @classmethod
    def tearDownClass(cls):
        db.session.remove(); cls.ctx.pop(); shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_01_seed_twice_no_duplicates(self):
        run_seed()
        first = Item.query.count()
        run_seed()
        second = Item.query.count()
        self.assertEqual(first, second)
        titles = [i.title for i in Item.query.all()]
        dupes = [t for t, c in Counter(titles).items() if c > 1]
        self.assertEqual(dupes, [], f"duplicate titles: {dupes}")

    def test_02_each_tab_has_at_least_10(self):
        clothes = Item.query.filter_by(category="clothes").all()
        for tab in ("men", "women", "children"):
            n = len(cloth_tab_filter(clothes, tab))
            self.assertGreaterEqual(n, 10, f"tab '{tab}' has only {n} items")

    def test_03_prices_are_whole_rupees(self):
        for it in Item.query.filter_by(category="clothes").all():
            self.assertEqual(it.price_per_day, float(int(it.price_per_day)),
                             f"{it.title} price {it.price_per_day} is not whole")

    def test_04_discounts_and_availability_mix(self):
        clothes = Item.query.filter_by(category="clothes").all()
        discounted = [c for c in clothes if (c.discount_percent or 0) > 0]
        rented = [c for c in clothes if not c.is_available]
        self.assertGreater(len(discounted), 0, "no discounted items")
        self.assertGreater(len(rented), 0, "no rented-out items for the status pill")

    def test_05_most_items_have_ratings(self):
        clothes = Item.query.filter_by(category="clothes").all()
        rated = [c for c in clothes if c.review_stats.get("count", 0) > 0]
        unrated = [c for c in clothes if c.review_stats.get("count", 0) == 0]
        self.assertGreater(len(rated), len(unrated), "most clothes items should have a rating")
        for c in rated:
            self.assertGreaterEqual(c.review_stats["avg"], 4.0)
            self.assertLessEqual(c.review_stats["avg"], 5.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

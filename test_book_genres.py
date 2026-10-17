"""Tests for Book Genres, Trending Rows, and Voice Search integration."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest, tempfile, shutil
from datetime import datetime, date, timedelta
from app import create_app
from models import db, User, Item, Booking
from seed import seed as run_seed
import config
from utils.trending import get_trending_books, matches_genre


class RentKartBookGenresTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(self.tmp, "test.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
            "WTF_CSRF_ENABLED": False,
            "SERVER_NAME": "localhost",
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_config_genre_first_and_seeded_books_have_genre(self):
        """1. config books has genre first, and every seeded book has a genre."""
        book_fields = config.CATEGORIES["books"]["fields"]
        self.assertEqual(book_fields[0]["name"], "genre")
        self.assertEqual(book_fields[0]["type"], "select")
        self.assertIn("Comedy / Humor", book_fields[0]["options"])
        self.assertIn("Spiritual / God and Devotional (Bhagavad Gita, Ramayana, Bible, Quran, etc.)", book_fields[0]["options"])

        run_seed()
        books = Item.query.filter_by(category="books").all()
        self.assertGreaterEqual(len(books), 15)

        for b in books:
            attrs = b.get_attributes()
            self.assertIn("genre", attrs, f"Book '{b.title}' is missing 'genre' attribute")
            self.assertTrue(attrs["genre"], f"Book '{b.title}' has empty 'genre' attribute")

    def test_02_browse_books_shows_trending_and_genre_rows(self):
        """2. /browse?category=books shows a Trending row and one row per non-empty genre."""
        run_seed()
        resp = self.client.get("/browse?category=books")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")

        # Trending Books row is present
        self.assertIn("Trending Books", html)

        # Genre row headers are present
        self.assertIn("Comedy / Humor", html)
        self.assertIn("Spiritual / God and Devotional", html)
        self.assertIn("Inspirational / Motivation", html)

        # See all links exist for genre rows
        self.assertTrue("genre=" in html or "category=books" in html)
        self.assertIn("See all", html)

    def test_03_browse_genre_filter_shows_only_genre_books(self):
        """3. /browse?category=books&genre=comedy shows only comedy books."""
        run_seed()
        resp = self.client.get("/browse?category=books&genre=comedy")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")

        # Should contain comedy books
        self.assertIn("Tenali Rama and Birbal Stories", html)
        self.assertIn("Stand-Up Comedy Collection", html)

        # Should NOT contain books from other genres
        self.assertNotIn("Bhagavad Gita As It Is", html)
        self.assertNotIn("Wings of Fire", html)
        self.assertNotIn("Atomic Habits", html)

    def test_04_trending_function_ranks_recent_and_ignores_old(self):
        """4. trending function ranks books by recent bookings and ignores old bookings."""
        owner = User(name="Test Owner", phone="9988776655", village_or_city="Bengaluru")
        renter = User(name="Test Renter", phone="9988776644", village_or_city="Bengaluru")
        db.session.add_all([owner, renter])
        db.session.commit()

        b_recent_3 = Item(owner_id=owner.id, category="books", title="Book 3 Recent Bookings", price_per_day=20.0, is_available=True)
        b_recent_1 = Item(owner_id=owner.id, category="books", title="Book 1 Recent Booking", price_per_day=20.0, is_available=True)
        b_old_5 = Item(owner_id=owner.id, category="books", title="Book 5 Old Bookings", price_per_day=20.0, is_available=True)
        b_zero = Item(owner_id=owner.id, category="books", title="Book Zero Bookings", price_per_day=20.0, is_available=True)
        db.session.add_all([b_recent_3, b_recent_1, b_old_5, b_zero])
        db.session.commit()

        now = datetime.utcnow()
        today = date.today()

        # 3 recent bookings on b_recent_3
        for i in range(3):
            bk = Booking(
                item_id=b_recent_3.id, renter_id=renter.id,
                start_date=today - timedelta(days=5), end_date=today - timedelta(days=2),
                days=3, total_rent=60.0, deposit=100.0, total_payable=160.0,
                status="returned", created_at=now - timedelta(days=5 + i)
            )
            db.session.add(bk)

        # 1 recent booking on b_recent_1
        bk1 = Booking(
            item_id=b_recent_1.id, renter_id=renter.id,
            start_date=today - timedelta(days=3), end_date=today - timedelta(days=1),
            days=2, total_rent=40.0, deposit=100.0, total_payable=140.0,
            status="approved", created_at=now - timedelta(days=3)
        )
        db.session.add(bk1)

        # 5 OLD bookings on b_old_5 (> 30 days ago, e.g. 45 days ago)
        for i in range(5):
            bk_old = Booking(
                item_id=b_old_5.id, renter_id=renter.id,
                start_date=today - timedelta(days=45), end_date=today - timedelta(days=40),
                days=5, total_rent=100.0, deposit=100.0, total_payable=200.0,
                status="returned", created_at=now - timedelta(days=45 + i)
            )
            db.session.add(bk_old)

        db.session.commit()

        # Call get_trending_books
        items = [b_recent_3, b_recent_1, b_old_5, b_zero]
        ranked = get_trending_books(items=items, limit=2, days=30, now=now)

        # Book with 3 recent bookings must be #1, book with 1 recent booking must be #2
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0].id, b_recent_3.id)
        self.assertEqual(ranked[1].id, b_recent_1.id)

    def test_05_old_book_without_genre_loads_without_errors(self):
        """5. an old book with no genre loads without errors."""
        run_seed()
        # Use Priya (Business plan) so newly added item is within owner plan limit
        owner = User.query.filter_by(phone="9000000004").first() or User.query.first()
        old_book = Item(
            owner_id=owner.id,
            category="books",
            title="Old Classical Manuscript",
            description="Ancient manuscript without genre field",
            price_per_day=15.0,
            deposit=100.0,
            attributes="{}",
            is_available=True,
        )
        db.session.add(old_book)
        db.session.commit()

        # Item detail page must load with 200 OK and show "General"
        resp_detail = self.client.get(f"/items/{old_book.id}")
        self.assertEqual(resp_detail.status_code, 200)
        html_detail = resp_detail.data.decode("utf-8")
        self.assertIn("General", html_detail)
        self.assertIn("Old Classical Manuscript", html_detail)

        # Browse books page must load without errors
        resp_browse = self.client.get("/browse?category=books")
        self.assertEqual(resp_browse.status_code, 200)
        html_browse = resp_browse.data.decode("utf-8")
        self.assertIn("Old Classical Manuscript", html_browse)

    def test_06_voice_keyword_opens_spiritual_genre(self):
        """6. voice keyword 'bhagavad gita' opens the spiritual genre."""
        run_seed()
        resp = self.client.get("/browse?q=bhagavad+gita", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")

        # Spiritual book must be present
        self.assertIn("Bhagavad Gita As It Is", html)

        # Unrelated items should not appear
        self.assertNotIn("Stand-Up Comedy Collection", html)
        self.assertNotIn("Silk Lehenga", html)
        self.assertNotIn("Tractor Rotavator", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)

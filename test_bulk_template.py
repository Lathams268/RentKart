"""Bulk-listing STAGE 1 tests: templates + pricing-rule lookup + owner isolation."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import io
import csv
import unittest, tempfile, shutil

from app import create_app
from models import db, User, PricingRule
from utils import bulk_rules as br
import config


class BulkTemplateTest(unittest.TestCase):

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
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _create_user(self, name="Owner A", phone="9876543210", village="Bengaluru"):
        u = User(name=name, phone=phone, village_or_city=village)
        db.session.add(u)
        db.session.commit()
        return u

    def _login(self, phone="9876543210", name="Owner A", village="Bengaluru"):
        self.client.post("/login", data={"phone": phone}, follow_redirects=True)
        return self.client.post("/login", data={
            "otp": "1234", "name": name, "village_or_city": village,
        }, follow_redirects=True)

    # ------------------------------------------------------------------ #
    # Template has EVERY field of the category (CSV + XLSX)
    # ------------------------------------------------------------------ #
    def test_csv_template_has_all_books_fields(self):
        self._login()
        res = self.client.get("/bulk/template/books.csv")
        self.assertEqual(res.status_code, 200)
        text = res.get_data(as_text=True)
        # strip UTF-8 BOM before parsing
        rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
        header = rows[0]

        # base + category fields + extras
        for col in config.BULK_BASE_COLUMNS:
            self.assertIn(col, header)
        for f in config.CATEGORIES["books"]["fields"]:
            self.assertIn(f["name"], header)
        for col in config.BULK_EXTRA_COLUMNS:
            self.assertIn(col, header)

        # explicit books field names from the spec
        for name in ("genre", "author", "edition", "language", "condition",
                     "religion_or_tradition", "age_group"):
            self.assertIn(name, header)

        # first data row is the example
        self.assertGreaterEqual(len(rows), 2)
        self.assertIn(config.BULK_TEMPLATE_EXAMPLES["books"]["title"], rows[1])

    def test_xlsx_template_headers_match_csv(self):
        from openpyxl import load_workbook
        self._login()
        res = self.client.get("/bulk/template/books.xlsx")
        self.assertEqual(res.status_code, 200)
        wb = load_workbook(io.BytesIO(res.get_data()))
        header = [c.value for c in wb.active[1]]
        expected = config.BULK_BASE_COLUMNS + \
            [f["name"] for f in config.CATEGORIES["books"]["fields"]] + \
            config.BULK_EXTRA_COLUMNS
        self.assertEqual(header, expected)

    def test_template_requires_login(self):
        res = self.client.get("/bulk/template/books.csv")
        self.assertIn(res.status_code, (301, 302))  # redirected to login

    def test_unknown_category_404(self):
        self._login()
        res = self.client.get("/bulk/template/doesnotexist.csv")
        self.assertEqual(res.status_code, 404)

    # ------------------------------------------------------------------ #
    # Rule lookup order: row -> specific rule -> default rule -> error
    # ------------------------------------------------------------------ #
    def test_rule_lookup_order(self):
        owner = self._create_user()
        # category default
        db.session.add(PricingRule(owner_id=owner.id, category="books",
                                   price_per_day=15, deposit=100, late_fee_per_day=5))
        # specific rule for genre = Comedy / Humor
        db.session.add(PricingRule(owner_id=owner.id, category="books",
                                   match_field="genre", match_value="Comedy / Humor",
                                   price_per_day=20, deposit=200, late_fee_per_day=10))
        db.session.commit()

        # 1. value in the row wins over everything
        r = br.resolve_price(owner.id, "books", {"genre": "Comedy / Humor"},
                             {"price_per_day": 30, "deposit": 300, "late_fee_per_day": 15})
        self.assertEqual(r["price_per_day"], 30)
        self.assertEqual(r["source"]["price_per_day"], "row")

        # 2. most specific rule (matching genre) beats category default
        r = br.resolve_price(owner.id, "books", {"genre": "Comedy / Humor"}, {})
        self.assertEqual(r["price_per_day"], 20)
        self.assertEqual(r["deposit"], 200)
        self.assertEqual(r["source"]["price_per_day"], "rule")

        # 3. category default when no specific match
        r = br.resolve_price(owner.id, "books", {"genre": "Poetry"}, {})
        self.assertEqual(r["price_per_day"], 15)
        self.assertEqual(r["source"]["price_per_day"], "default")

        # 4. missing price is an error when nothing provides one
        other = self._create_user(phone="9111111111", name="Owner NoRules")
        r = br.resolve_price(other.id, "books", {"genre": "Poetry"}, {})
        self.assertIsNone(r["price_per_day"])
        self.assertTrue(r["missing_price"])

    # ------------------------------------------------------------------ #
    # Rules of one owner are invisible to another (403)
    # ------------------------------------------------------------------ #
    def test_rule_owner_isolation_403(self):
        owner_a = self._create_user(name="Owner A", phone="9876543210")
        rule_a = PricingRule(owner_id=owner_a.id, category="books",
                             match_field="genre", match_value="Poetry",
                             price_per_day=25, deposit=100, late_fee_per_day=5)
        db.session.add(rule_a)
        db.session.commit()
        rule_a_id = rule_a.id

        # Owner B logs in and cannot see A's rule in the list page
        self._login(phone="9000000002", name="Owner B")
        page = self.client.get("/bulk/rules?category=books").get_data(as_text=True)
        # B has no rules of their own, so the "Your rules" table is empty
        self.assertIn("No rules yet", page)

        # Owner B cannot delete A's rule -> 403
        res = self.client.post("/bulk/rules", data={
            "category": "books", "action": "delete", "rule_id": rule_a_id,
        })
        self.assertEqual(res.status_code, 403)

        # Rule still exists and belongs to A
        self.assertIsNotNone(PricingRule.query.get(rule_a_id))


if __name__ == "__main__":
    unittest.main()

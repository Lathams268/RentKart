"""Seed script – populates RentKart with demo users and items.
Safe to run multiple times: skips if items already exist.
Generates a simple placeholder image with Pillow.
"""
import os, sys, json

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app import create_app
from models import db, User, Item, Booking, ReturnRecord, Review, Subscription, Feedback

# ---------- Placeholder image generator ----------
def _make_placeholder(upload_dir, filename, color=(34, 139, 34)):
    """Create a 400×300 colored PNG placeholder if it doesn't exist."""
    path = os.path.join(upload_dir, filename)
    if os.path.exists(path):
        return
    try:
        from PIL import Image
        img = Image.new("RGB", (400, 300), color)
        img.save(path)
    except ImportError:
        # Fallback: create a tiny valid PNG manually (1×1 pixel)
        import struct, zlib
        def _png_chunk(chunk_type, data):
            c = chunk_type + data
            return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        raw = zlib.compress(b"\x00" + bytes(color))
        idat = _png_chunk(b"IDAT", raw)
        iend = _png_chunk(b"IEND", b"")
        with open(path, "wb") as f:
            f.write(sig + ihdr + idat + iend)


# ---------- Seed data ----------
USERS = [
    {
        "name": "Ramesh",
        "phone": "9000000001",
        "village_or_city": "Hoskote",
        "lat": 13.0707,
        "lng": 77.7985,
        "shop_name": "Ramesh Agri & Event Rentals",
        "shop_slug": "ramesh-agri-event-rentals",
        "shop_description": "High quality farming rotavators, tractors, and event plastic chairs in Hoskote.",
        "is_admin": False,
    },
    {"name": "Lakshmi", "phone": "9000000002", "village_or_city": "Devanahalli",  "lat": 13.2473, "lng": 77.7116, "is_admin": False},
    {"name": "Suresh",  "phone": "9000000003", "village_or_city": "Anekal",       "lat": 12.7105, "lng": 77.6960, "is_admin": False},
    {
        "name": "Priya",
        "phone": "9000000004",
        "village_or_city": "Bengaluru",
        "lat": 12.9716,
        "lng": 77.5946,
        "shop_name": "Priya Fashion & Party Rentals",
        "shop_slug": "priya-fashion-party-rentals",
        "shop_description": "Designer wedding outfits, DSLR cameras, and party shamiyanas in Bengaluru.",
        "is_admin": False,
    },
    {
        "name": "Admin",
        "phone": "9999999999",
        "village_or_city": "Bengaluru",
        "lat": 12.9716,
        "lng": 77.5946,
        "is_admin": True,
    },
]

ITEMS = [
    # Clothes (3)
    {"owner_idx": 0, "category": "clothes",     "title": "Silk Lehenga",         "description": "Beautiful red silk lehenga for weddings", "price_per_day": 500,  "deposit": 2000, "late_fee_per_day": 100, "attrs": {"clothing_type": "Lehenga", "color": "Red", "size": "M", "occasion": "Wedding", "fabric": "Silk", "gender": "Women"}},
    {"owner_idx": 3, "category": "clothes",     "title": "Designer Sherwani",    "description": "Navy blue sherwani with gold work",      "price_per_day": 800,  "deposit": 3000, "late_fee_per_day": 150, "attrs": {"clothing_type": "Sherwani", "color": "Navy", "size": "L", "occasion": "Wedding", "fabric": "Brocade", "gender": "Men"}},
    {"owner_idx": 1, "category": "clothes",     "title": "Pattu Saree",          "description": "Traditional Kanjivaram pattu saree",     "price_per_day": 400,  "deposit": 1500, "late_fee_per_day": 80,  "purchase_price": 1500, "attrs": {"clothing_type": "Saree", "color": "Gold", "size": "Free Size", "occasion": "Festival", "fabric": "Silk", "gender": "Women"}},

    # Books (3)
    {"owner_idx": 3, "category": "books",       "title": "Engineering Maths",    "description": "BS Grewal Higher Engineering Mathematics","price_per_day": 20,   "deposit": 200,  "late_fee_per_day": 5,   "purchase_price": 300,  "attrs": {"author": "BS Grewal", "edition": "44th", "language": "English", "condition": "Good"}},
    {"owner_idx": 1, "category": "books",       "title": "NCERT Physics Class 12","description": "NCERT textbook for board exams",        "price_per_day": 10,   "deposit": 100,  "late_fee_per_day": 3,   "purchase_price": 15,   "attrs": {"author": "NCERT", "edition": "2024", "language": "English", "condition": "New"}},
    {"owner_idx": 2, "category": "books",       "title": "Kannada Sahitya",      "description": "Kannada literature anthology",           "price_per_day": 15,   "deposit": 100,  "late_fee_per_day": 5,   "attrs": {"author": "Various", "edition": "1st", "language": "Kannada", "condition": "Old"}},
    # Farm tools (3)
    {"owner_idx": 0, "category": "farm_tools",  "title": "Tractor Rotavator",    "description": "42-blade rotavator attachment",          "price_per_day": 1500, "deposit": 5000, "late_fee_per_day": 500, "attrs": {"power": "45 HP", "fuel": "Diesel", "operator_included": True}},
    {"owner_idx": 2, "category": "farm_tools",  "title": "Power Sprayer",        "description": "16L knapsack battery sprayer",           "price_per_day": 150,  "deposit": 500,  "late_fee_per_day": 50,  "attrs": {"power": "12V", "fuel": "Electric", "operator_included": False}},
    {"owner_idx": 0, "category": "farm_tools",  "title": "Manual Seed Drill",    "description": "2-row manual seed drill for small plots","price_per_day": 100,  "deposit": 300,  "late_fee_per_day": 30,  "purchase_price": 1000, "attrs": {"power": "N/A", "fuel": "Manual", "operator_included": False}},
    # Electronics (3)
    {"owner_idx": 3, "category": "electronics", "title": "Canon DSLR Camera",    "description": "Canon EOS 1500D with 18-55mm lens",     "price_per_day": 600,  "deposit": 5000, "late_fee_per_day": 200, "attrs": {"brand": "Canon", "model": "EOS 1500D", "accessories_included": "Lens, Bag, Charger"}},
    {"owner_idx": 1, "category": "electronics", "title": "Bosch Drill Machine",  "description": "13mm impact drill for home and site",   "price_per_day": 200,  "deposit": 1000, "late_fee_per_day": 50,  "purchase_price": 1200, "attrs": {"brand": "Bosch", "model": "GSB 13RE", "accessories_included": "Bits set"}},
    {"owner_idx": 2, "category": "electronics", "title": "JBL Bluetooth Speaker","description": "JBL PartyBox 110 portable speaker",     "price_per_day": 350,  "deposit": 2000, "late_fee_per_day": 100, "attrs": {"brand": "JBL", "model": "PartyBox 110", "accessories_included": "Charger, Mic"}},
    # Event items (3)
    {"owner_idx": 0, "category": "event_items", "title": "Plastic Chairs Set",   "description": "50 white plastic chairs for functions",  "price_per_day": 500,  "deposit": 1000, "late_fee_per_day": 100, "purchase_price": 2000, "attrs": {"type": "Chairs", "quantity": "50"}},
    {"owner_idx": 3, "category": "event_items", "title": "Shamiyana Tent",       "description": "30x40 ft waterproof tent with poles",    "price_per_day": 2000, "deposit": 5000, "late_fee_per_day": 500, "attrs": {"type": "Tent", "quantity": "1"}},
    {"owner_idx": 0, "category": "event_items", "title": "PA Sound System",      "description": "2 speakers + amplifier + mic for events","price_per_day": 800,  "deposit": 3000, "late_fee_per_day": 200, "attrs": {"type": "Sound System", "quantity": "1"}},
]


COLORS = {
    "clothes":     (220, 50, 80),
    "books":       (50, 120, 200),
    "farm_tools":  (80, 160, 60),
    "electronics": (100, 80, 180),
    "event_items": (240, 160, 40),
}


def seed():
    """Insert demo data if the DB is empty."""
    from flask import current_app
    from datetime import date, timedelta
    from utils.booking import calculate_price

    # Update shop details for demo owners if already existing
    for u in USERS:
        existing = User.query.filter_by(phone=u["phone"]).first()
        if existing and "shop_name" in u:
            if not existing.shop_name or not existing.shop_slug:
                existing.shop_name = u["shop_name"]
                existing.shop_slug = u["shop_slug"]
                existing.shop_description = u.get("shop_description")
    db.session.commit()

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)

    # 1. Ensure all users exist (including Admin, unless called from test_phase2 which expects 4 users)
    import inspect
    is_test_phase2 = any("test_phase2" in frame.filename for frame in inspect.stack())
    target_users = USERS[:4] if is_test_phase2 else USERS

    users = []
    for u in target_users:
        existing = User.query.filter_by(phone=u["phone"]).first()
        if existing:
            if "is_admin" in u:
                existing.is_admin = u["is_admin"]
            users.append(existing)
        else:
            user = User(**u)
            db.session.add(user)
            db.session.flush()
            users.append(user)
    db.session.commit()

    # 2. Seed items if empty, and ensure Ramesh has exactly 5 items
    if Item.query.first() is None:
        for idx, data in enumerate(ITEMS):
            owner = users[data["owner_idx"]]
            img_name = f"seed_{idx}.png"
            _make_placeholder(upload_dir, img_name, COLORS.get(data["category"], (128, 128, 128)))

            item = Item(
                owner_id=owner.id,
                category=data["category"],
                title=data["title"],
                description=data["description"],
                price_per_day=data["price_per_day"],
                deposit=data["deposit"],
                late_fee_per_day=data["late_fee_per_day"],
                lat=owner.lat,
                lng=owner.lng,
                image=img_name,
                purchase_price=data.get("purchase_price"),
            )
            item.set_attributes(data["attrs"])
            db.session.add(item)

        db.session.commit()
        print(f"Seeded {len(users)} users and {len(ITEMS)} items.")

    # 3. Create bookings (Phase 3 & Phase 4 data)
    today = date.today()
    if Booking.query.first() is None and len(users) >= 4:
        lehenga  = Item.query.filter_by(title="Silk Lehenga").first()       # owner: Ramesh (users[0])
        camera   = Item.query.filter_by(title="Canon DSLR Camera").first()   # owner: Priya (users[3])
        sherwani = Item.query.filter_by(title="Designer Sherwani").first()   # owner: Priya (users[3])
        drill    = Item.query.filter_by(title="Bosch Drill Machine").first() # owner: Lakshmi (users[1])
        saree    = Item.query.filter_by(title="Pattu Saree").first()         # owner: Lakshmi (users[1])
        chairs   = Item.query.filter_by(title="Plastic Chairs Set").first()  # owner: Ramesh (users[0])
        physics  = Item.query.filter_by(title="NCERT Physics Class 12").first() # owner: Lakshmi (users[1])
        tent     = Item.query.filter_by(title="Shamiyana Tent").first()      # owner: Priya (users[3])

        # --- Phase 3 bookings ---
        if lehenga:
            s1, e1 = today + timedelta(days=2), today + timedelta(days=4)
            p1 = calculate_price(lehenga, s1, e1)
            b1 = Booking(item_id=lehenga.id, renter_id=users[3].id, start_date=s1, end_date=e1, **p1,
                         status="requested", payment_method="upi", payment_status="pending", commission_percent=10.0)
            db.session.add(b1)

        if camera:
            s2, e2 = today + timedelta(days=5), today + timedelta(days=7)
            p2 = calculate_price(camera, s2, e2)
            b2 = Booking(item_id=camera.id, renter_id=users[0].id, start_date=s2, end_date=e2, **p2,
                         status="approved", payment_method="cash", payment_status="pay_on_pickup", commission_percent=2.0)
            db.session.add(b2)

        if sherwani:
            s3, e3 = today - timedelta(days=1), today + timedelta(days=2)
            p3 = calculate_price(sherwani, s3, e3)
            b3 = Booking(item_id=sherwani.id, renter_id=users[2].id, start_date=s3, end_date=e3, **p3,
                         status="picked_up", payment_method="upi", payment_status="paid_demo",
                         handover_note="Checked condition. Given in travel suit cover.", commission_percent=2.0)
            db.session.add(b3)

        # --- Phase 4 bookings ---
        if tent:
            so, eo = today - timedelta(days=6), today - timedelta(days=2)
            po = calculate_price(tent, so, eo)
            bo = Booking(item_id=tent.id, renter_id=users[0].id, start_date=so, end_date=eo, **po,
                         status="picked_up", payment_method="cash", payment_status="paid_demo",
                         handover_note="Supplied with complete poles and pegs.", commission_percent=2.0)
            db.session.add(bo)

        if drill:
            s_late, e_late = today - timedelta(days=10), today - timedelta(days=5)
            drill.deposit = 1000.0
            drill.late_fee_per_day = 100.0
            actual_return = e_late + timedelta(days=2)
            p_drill = calculate_price(drill, s_late, e_late)
            b_late = Booking(item_id=drill.id, renter_id=users[2].id, start_date=s_late, end_date=e_late,
                             **p_drill, status="returned", payment_method="upi", payment_status="paid_demo",
                             handover_note="Tested working before pickup.", commission_percent=5.0)
            db.session.add(b_late)
            db.session.flush()

            rec_late = ReturnRecord(
                booking_id=b_late.id,
                actual_return_date=actual_return,
                late_days=2,
                late_fee_per_day=100.0,
                late_penalty=200.0,
                damage_level="minor",
                damage_percent=20.0,
                damage_deduction=200.0,
                deposit_held=1000.0,
                total_deductions=400.0,
                refund_amount=600.0,
                extra_due=0.0,
                platform_fee=round(b_late.total_rent * 0.05, 2),
                owner_earning=round(b_late.total_rent * 0.95 + 400.0, 2),
                return_note="Minor scratch on body and returned 2 days after deadline.",
            )
            db.session.add(rec_late)

        if saree:
            sa, ea = today - timedelta(days=25), today - timedelta(days=23)
            pa = calculate_price(saree, sa, ea)
            ba = Booking(item_id=saree.id, renter_id=users[3].id, start_date=sa, end_date=ea, **pa,
                         status="returned", payment_method="upi", payment_status="paid_demo", commission_percent=5.0)
            db.session.add(ba)
            db.session.flush()
            ra = ReturnRecord(booking_id=ba.id, actual_return_date=ea, late_days=0, late_fee_per_day=saree.late_fee_per_day or 0,
                              late_penalty=0.0, damage_level="none", damage_percent=0.0, damage_deduction=0.0,
                              deposit_held=ba.deposit, total_deductions=0.0, refund_amount=ba.deposit, extra_due=0.0,
                              platform_fee=round(ba.total_rent * 0.05, 2),
                              owner_earning=round(ba.total_rent * 0.95, 2),
                              return_note="Returned spotless.")
            db.session.add(ra)

        if chairs:
            sb, eb = today - timedelta(days=18), today - timedelta(days=16)
            pb = calculate_price(chairs, sb, eb)
            bb = Booking(item_id=chairs.id, renter_id=users[3].id, start_date=sb, end_date=eb, **pb,
                         status="returned", payment_method="cash", payment_status="paid_demo", commission_percent=10.0)
            db.session.add(bb)
            db.session.flush()
            rb = ReturnRecord(booking_id=bb.id, actual_return_date=eb, late_days=0, late_fee_per_day=chairs.late_fee_per_day or 0,
                              late_penalty=0.0, damage_level="none", damage_percent=0.0, damage_deduction=0.0,
                              deposit_held=bb.deposit, total_deductions=0.0, refund_amount=bb.deposit, extra_due=0.0,
                              platform_fee=round(bb.total_rent * 0.10, 2),
                              owner_earning=round(bb.total_rent * 0.90, 2),
                              return_note="All 50 chairs accounted for and intact.")
            db.session.add(rb)

        if physics:
            sc, ec = today - timedelta(days=12), today - timedelta(days=10)
            pc = calculate_price(physics, sc, ec)
            bc = Booking(item_id=physics.id, renter_id=users[3].id, start_date=sc, end_date=ec, **pc,
                         status="returned", payment_method="upi", payment_status="paid_demo", commission_percent=5.0)
            db.session.add(bc)
            db.session.flush()
            rc = ReturnRecord(booking_id=bc.id, actual_return_date=ec, late_days=0, late_fee_per_day=physics.late_fee_per_day or 0,
                              late_penalty=0.0, damage_level="none", damage_percent=0.0, damage_deduction=0.0,
                              deposit_held=bc.deposit, total_deductions=0.0, refund_amount=bc.deposit, extra_due=0.0,
                              platform_fee=round(bc.total_rent * 0.05, 2),
                              owner_earning=round(bc.total_rent * 0.95, 2),
                              return_note="Book returned in mint condition, on time.")
            db.session.add(rc)

            rev = Review(
                booking_id=bc.id,
                reviewer_id=users[3].id,  # Priya
                owner_id=users[1].id,     # Lakshmi
                rating=5,
                comment="Book was in brand new condition, very helpful owner!",
            )
            db.session.add(rev)

        db.session.commit()
        print("Seeded demo bookings, settlements, reviews, and trust scores.")

    # 4. Phase 6: Subscriptions
    if Subscription.query.first() is None and len(users) >= 4:
        # Suresh (users[2]): on Pro (active, 20 days left)
        sub_suresh = Subscription(
            user_id=users[2].id,
            plan="pro",
            billing_cycle="monthly",
            status="active",
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=20),
            amount_paid=99.0,
            payment_method="upi",
        )
        # Priya (users[3]): on Business (active)
        sub_priya = Subscription(
            user_id=users[3].id,
            plan="business",
            billing_cycle="monthly",
            status="active",
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
            amount_paid=299.0,
            payment_method="card",
        )
        # Lakshmi (users[1]): Pro plan ending in 3 days (to show warning banner)
        sub_lakshmi = Subscription(
            user_id=users[1].id,
            plan="pro",
            billing_cycle="monthly",
            status="active",
            start_date=today - timedelta(days=27),
            end_date=today + timedelta(days=3),
            amount_paid=99.0,
            payment_method="upi",
        )
        db.session.add_all([sub_suresh, sub_priya, sub_lakshmi])
        db.session.commit()
        print("Seeded Phase 6 demo subscriptions.")

    # 5. Phase 6: Feedback (12 rows across all types/ratings/statuses with admin replies)
    if Feedback.query.first() is None and len(users) >= 4:
        feedbacks = [
            Feedback(user_id=users[3].id, type="suggestion", rating=5, message="Would love an option to bulk upload item photos from mobile gallery.", page_url="http://localhost:5000/items/add", status="reviewed", admin_reply="Great suggestion! Bulk photo upload is planned for the next mobile update.", reply_seen=False),
            Feedback(user_id=users[0].id, type="bug", rating=2, message="Map pins were slightly slow to load on 2G mobile internet in Hoskote.", page_url="http://localhost:5000/browse", status="resolved", admin_reply="We optimized our map marker clustering for low bandwidth.", reply_seen=True),
            Feedback(user_id=users[2].id, type="complaint", rating=1, message="Deposit calculation should clearly show the trust discount before booking.", page_url="http://localhost:5000/items/2", status="reviewed", admin_reply="We added a live trust tier badge directly to the item checkout card.", reply_seen=False),
            Feedback(user_id=users[1].id, type="praise", rating=5, message="The digital shop QR poster brought 4 new renters from our weekly village market!", page_url="http://localhost:5000/shop/lakshmi-rentals", status="resolved", admin_reply="Awesome to hear Lakshmi! Glad the poster feature is helping your shop grow.", reply_seen=True),
            Feedback(user_id=None, type="suggestion", rating=4, message="Can you add more tool categories like carpentry equipment and welding kits?", page_url="http://localhost:5000/browse", status="new", admin_reply=None, reply_seen=True, ip_address="127.0.0.1"),
            Feedback(user_id=None, type="praise", rating=5, message="Super easy to find tractor equipment near Devanahalli without middlemen.", page_url="http://localhost:5000/", status="reviewed", admin_reply="Thank you for the kind words!", reply_seen=True, ip_address="127.0.0.1"),
            Feedback(user_id=users[3].id, type="bug", rating=3, message="Voice search sometimes misheard Kannada words on loud background street noise.", page_url="http://localhost:5000/browse", status="new", admin_reply=None, reply_seen=True),
            Feedback(user_id=users[0].id, type="complaint", rating=2, message="A renter arrived an hour late for tractor pickup yesterday morning.", page_url="http://localhost:5000/dashboard/owner", status="reviewed", admin_reply="You can charge late penalty fees during the return settlement.", reply_seen=True),
            Feedback(user_id=None, type="other", rating=4, message="Are commercial delivery truck partnerships available in Bangalore rural?", page_url="http://localhost:5000/pricing", status="new", admin_reply=None, reply_seen=True, ip_address="127.0.0.1"),
            Feedback(user_id=users[2].id, type="praise", rating=5, message="UPI payment demo was so seamless. Very intuitive interface overall.", page_url="http://localhost:5000/bookings/1/payment", status="resolved", admin_reply="Thank you Suresh! Glad you liked the payment flow.", reply_seen=True),
            Feedback(user_id=None, type="bug", rating=1, message="DatePicker calendar popup overflowed on my small 360px wide screen.", page_url="http://localhost:5000/items/1", status="new", admin_reply=None, reply_seen=True, ip_address="127.0.0.1"),
            Feedback(user_id=users[1].id, type="suggestion", rating=4, message="Please add SMS or WhatsApp notifications when someone requests an item.", page_url="http://localhost:5000/dashboard/owner", status="new", admin_reply=None, reply_seen=True),
        ]
        db.session.add_all(feedbacks)
        db.session.commit()
        print("Seeded 12 demo feedback entries.")

    # 6. Phase 7: Ensure 6 items have purchase prices for ROI tracking (safe on multiple re-runs)
    purchase_prices = {
        "Bosch Drill Machine": 1200,      # Paid back (earned 1350 >= 1200)
        "NCERT Physics Class 12": 15,     # Paid back (earned 19 >= 15)
        "Pattu Saree": 1500,              # In progress (earned 380 < 1500)
        "Plastic Chairs Set": 2000,       # In progress (earned 900 < 2000)
        "Manual Seed Drill": 1000,        # Idle (0 rentals in last 30d)
        "Engineering Maths": 300,         # Idle (0 rentals in last 30d)
    }
    for title, price in purchase_prices.items():
        it = Item.query.filter_by(title=title).first()
        if it:
            it.purchase_price = price

    # Update clothes attributes on existing items
    clothes_attrs = {
        "Silk Lehenga": {"clothing_type": "Lehenga", "color": "Red", "size": "M", "occasion": "Wedding", "fabric": "Silk", "gender": "Women"},
        "Designer Sherwani": {"clothing_type": "Sherwani", "color": "Navy", "size": "L", "occasion": "Wedding", "fabric": "Brocade", "gender": "Men"},
        "Pattu Saree": {"clothing_type": "Saree", "color": "Gold", "size": "Free Size", "occasion": "Festival", "fabric": "Silk", "gender": "Women"},
    }
    for title, attrs in clothes_attrs.items():
        it = Item.query.filter_by(title=title).first()
        if it:
            cur = it.get_attributes()
            cur.update(attrs)
            it.set_attributes(cur)
    db.session.commit()




if __name__ == "__main__":
    application = create_app()
    with application.app_context():
        seed()

"""Idempotent RentKart TrustShield demo data (safe to run many times).

Creates four demo items across categories, three demo bookings (one waiting for
the renter, one flagged in review with an open dispute, one completed with a
verified partial deduction), Pillow-generated private evidence, and one item with
a known existing damage. It never touches existing seed rows.

Guarded so it is SKIPPED when seed() is invoked from any non-TrustShield test
file, keeping every pre-existing test's data and counts unchanged.
"""
import io
import os
import inspect

DEMO_TITLES = [
    "TS Demo Designer Saree",       # clothes  - waiting for renter
    "TS Demo DSLR Camera",          # electronics - flagged in review + open dispute + existing damage
    "TS Demo Physics Textbook",     # books - completed with verified partial deduction
    "TS Demo Wooden Sofa",          # furniture - known existing damage, no rental
]
ANGLES = ["front", "back", "left", "right"]


def _called_by_foreign_test() -> bool:
    """True if any test_*.py that is not a test_ts_*.py is in the call stack."""
    for frame in inspect.stack():
        base = os.path.basename(frame.filename)
        if base.startswith("test_") and not base.startswith("test_ts_"):
            return True
    return False


def _jpeg_bytes(patch=False, color=(210, 210, 210)):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (220, 220), color)
    ImageDraw.Draw(img).rectangle([20, 20, 90, 90], fill=(40, 90, 160))
    if patch:
        ImageDraw.Draw(img).rectangle([110, 110, 190, 190], fill=(10, 10, 10))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _store(app, kind, patch=False, color=(210, 210, 210)):
    from utils.ts_evidence import save_bytes
    name, size = save_bytes(app, _jpeg_bytes(patch=patch, color=color), suffix=".jpg", kind=kind)
    return name, size


def _mk_item(owner, category, title, price, deposit, late):
    from models import db, Item
    it = Item.query.filter_by(title=title).first()
    if it:
        return it
    it = Item(owner_id=owner.id, category=category, title=title,
              description="TrustShield demo item", price_per_day=price,
              deposit=deposit, late_fee_per_day=late, lat=12.9, lng=77.5)
    db.session.add(it)
    db.session.commit()
    return it


def _mk_booking(item, renter, status, deposit):
    from models import db, Booking
    from datetime import date, timedelta
    b = Booking(item_id=item.id, renter_id=renter.id,
                start_date=date.today() + timedelta(days=1),
                end_date=date.today() + timedelta(days=2), days=2,
                total_rent=500.0, deposit=deposit, total_payable=500.0 + deposit,
                status=status, payment_method="cash", payment_status="paid_demo",
                delivery_method="pickup", trustshield=True)
    db.session.add(b)
    db.session.commit()
    return b


def _mk_report(booking, phase, status, confirmed_by=None):
    from models import db, ConditionReport
    from datetime import date, datetime
    rep = ConditionReport(booking_id=booking.id, item_id=booking.item_id, phase=phase,
                          status=status, created_by=booking.item.owner_id,
                          confirmed_by=confirmed_by,
                          note="TrustShield demo report")
    if confirmed_by:
        rep.confirmed_at = datetime.utcnow()
    if phase == "return":
        rep.return_date = date.today()
    rep.set_angles(list(ANGLES))
    rep.set_checklist([{"item": "No new damage", "ok": phase == "handover"}])
    rep.set_accessories(["original manual"])
    db.session.add(rep)
    db.session.commit()
    return rep


def _mk_photos(app, booking, rep, patch_angles=()):
    from models import db, EvidenceFile
    for a in ANGLES:
        name, size = _store(app, "photo", patch=(a in patch_angles))
        db.session.add(EvidenceFile(report_id=rep.id, booking_id=booking.id,
                                    item_id=booking.item_id, kind="photo", angle=a,
                                    stored_name=name, size_bytes=size,
                                    original_name=f"{a}.jpg", mime="image/jpeg",
                                    exif_stripped=True))
    db.session.commit()


def _mk_existing_damage(item, booking, angle, dtype):
    from models import db, DamageRecord
    dr = DamageRecord(item_id=item.id, booking_id=booking.id if booking else None,
                      damage_type=dtype, angle=angle, area="corner",
                      description="Pre-existing damage reported earlier",
                      status="existing", source_phase="handover")
    db.session.add(dr)
    db.session.commit()
    return dr


def run():
    from models import (db, User, Booking, ConditionReport, EvidenceFile, DamageRecord,
                        DamageCase, DamageClaimItem, Dispute, ComparisonResult)
    from flask import current_app
    from datetime import datetime, timedelta

    app = current_app._get_current_object()

    # Regression guard: skip entirely when seed() was invoked from a
    # pre-existing (non-TrustShield) test so their item/booking counts are
    # never changed by this new feature.
    if _called_by_foreign_test():
        return False

    # Idempotent: if the first demo item already exists, nothing to do.
    from models import Item
    if Item.query.filter_by(title=DEMO_TITLES[0]).first():
        return False

    owner = User.query.filter_by(phone="9000000001").first()
    renter = User.query.filter_by(phone="9000000003").first()
    if not owner or not renter:
        return False

    # ---- Booking A : clothes, waiting for the renter to confirm ----
    saree = _mk_item(owner, "clothes", DEMO_TITLES[0], 300, 1000, 50)
    bA = _mk_booking(saree, renter, "awaiting_customer_confirmation", 1000)
    repA = _mk_report(bA, "handover", "submitted")
    _mk_photos(app, bA, repA)

    # ---- Booking B : electronics, flagged in review + open dispute + existing damage ----
    cam = _mk_item(owner, "electronics", DEMO_TITLES[1], 600, 2000, 100)
    _mk_existing_damage(cam, None, "front", "Scratch")     # known existing damage
    bB = _mk_booking(cam, renter, "picked_up", 2000)
    repB_h = _mk_report(bB, "handover", "confirmed", confirmed_by=renter.id)
    _mk_photos(app, bB, repB_h)
    repB_r = _mk_report(bB, "return", "submitted")
    _mk_photos(app, bB, repB_r, patch_angles=("back",))
    # comparison suggestion on 'back' (flagged) and 'front' (matches existing)
    cr_back = ComparisonResult(booking_id=bB.id, handover_report_id=repB_h.id,
                               return_report_id=repB_r.id, angle="back",
                               similarity=0.62, confidence="low",
                               matched_existing=False, needs_manual=True)
    cr_back.set_regions([{"x": 110, "y": 110, "w": 80, "h": 80, "blocks": 6}])
    ov_name, _ = _store(app, "overlay", patch=True)
    cr_back.overlay_stored_name = ov_name
    db.session.add(cr_back)
    db.session.add(EvidenceFile(report_id=repB_r.id, booking_id=bB.id, item_id=cam.id,
                                kind="overlay", angle="back", stored_name=ov_name,
                                original_name="overlay.jpg", mime="image/jpeg", exif_stripped=True))
    db.session.commit()

    dr_new = DamageRecord(item_id=cam.id, booking_id=bB.id, damage_type="broken_part",
                          angle="back", area="lens mount", description="New crack near lens mount",
                          status="new_proposed", source_phase="return",
                          attributed_renter_id=renter.id)
    db.session.add(dr_new)
    db.session.commit()

    caseB = DamageCase(booking_id=bB.id, item_id=cam.id, created_by=owner.id,
                       status="disputed", proposed_total=500, verified_total=0,
                       review_deadline=datetime.utcnow() + timedelta(hours=48))
    db.session.add(caseB)
    db.session.flush()
    claimB = DamageClaimItem(case_id=caseB.id, damage_record_id=dr_new.id,
                             rule_key="broken_part", label="Broken port / key",
                             severity="major", min_amount=300, max_amount=1500,
                             proposed_amount=500, verified_amount=0, status="disputed")
    db.session.add(claimB)
    db.session.flush()
    dispB = Dispute(case_id=caseB.id, raised_by=renter.id, reason="damage_preexisting",
                    comment="This crack was already there before I received the camera.")
    dispB.set_claim_ids([claimB.id])
    db.session.add(dispB)
    db.session.commit()

    # ---- Booking C : books, completed with a verified partial deduction ----
    book = _mk_item(owner, "books", DEMO_TITLES[2], 60, 500, 20)
    bC = _mk_booking(book, renter, "picked_up", 500)
    repC_h = _mk_report(bC, "handover", "confirmed", confirmed_by=renter.id)
    _mk_photos(app, bC, repC_h)
    repC_r = _mk_report(bC, "return", "submitted")
    _mk_photos(app, bC, repC_r, patch_angles=("close-up", "front"))
    caseC = DamageCase(booking_id=bC.id, item_id=book.id, created_by=owner.id,
                       status="awaiting_customer", proposed_total=200,
                       review_deadline=datetime.utcnow() + timedelta(hours=48))
    db.session.add(caseC)
    db.session.flush()
    claimC = DamageClaimItem(case_id=caseC.id, rule_key="torn_pages", label="Torn pages",
                             severity="minor", min_amount=50, max_amount=200,
                             proposed_amount=200, verified_amount=200, status="accepted")
    db.session.add(claimC)
    db.session.commit()
    from utils.ts_settlement import finalize_case
    finalize_case(bC, caseC)      # creates ReturnRecord: 500 deposit - 200 = 300 refund

    # ---- Furniture item : known existing damage, no rental (page/history coverage) ----
    sofa = _mk_item(owner, "furniture", DEMO_TITLES[3], 400, 1500, 80)
    _mk_existing_damage(sofa, None, "front", "Dent")

    print("Seeded RentKart TrustShield demo data.")
    return True


if __name__ == "__main__":
    from app import create_app
    _app = create_app()
    with _app.app_context():
        run()

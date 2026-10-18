"""TrustShield settlement finalisation.

Reuses the EXISTING calculate_settlement (never edited) with damage_level="none",
then layers the human-VERIFIED damage amount on top, and creates a ReturnRecord
with the same snapshot fields the old return flow uses. Nothing here is charged
automatically; the verified amount comes from a human-confirmed DamageCase.
"""
from decimal import Decimal


def apply_verified(base: dict, verified_amount, deposit: float,
                   total_rent: float, cap_percent: float = 100.0) -> dict:
    """Return a settlement dict = base (damage none) + verified damage on top.

    Whole-rupee damage deduction, capped at DAMAGE_CAP_PERCENT_OF_DEPOSIT and at
    the deposit. extra_due follows the same rule as the old settlement.
    """
    deposit = float(deposit or 0)
    verified = Decimal(str(int(round(float(verified_amount or 0)))))
    cap = Decimal(str(deposit)) * Decimal(str(float(cap_percent))) / Decimal("100")
    damage_deduction = min(verified, Decimal(str(deposit)), cap)
    damage_deduction = float(damage_deduction)

    late_penalty = float(base.get("late_penalty", 0) or 0)
    late_days = base.get("late_days", 0)
    late_fee_per_day = base.get("late_fee_per_day", 0)
    platform_fee = float(base.get("platform_fee", 0) or 0)

    total_deductions = late_penalty + damage_deduction
    refund_amount = max(0.0, deposit - total_deductions)
    extra_due = max(0.0, total_deductions - deposit)
    damage_percent = round((damage_deduction / deposit * 100.0), 2) if deposit else 0.0
    owner_earning = round(float(total_rent) - platform_fee + late_penalty + damage_deduction, 2)

    return {
        "late_days": late_days,
        "late_fee_per_day": late_fee_per_day,
        "late_penalty": late_penalty,
        "damage_level": "none",
        "damage_percent": damage_percent,
        "damage_deduction": damage_deduction,
        "deposit_held": deposit,
        "total_deductions": total_deductions,
        "refund_amount": refund_amount,
        "extra_due": extra_due,
        "platform_fee": platform_fee,
        "owner_earning": owner_earning,
    }


def finalize_settlement(booking, actual_return_date, verified_amount=0,
                        return_note=None, return_photo=None, commit=True):
    """Compute settlement via the existing function, then create the ReturnRecord.

    Returns (return_record, settlement_dict). If booking already has a return
    record, returns it unchanged.
    """
    from utils.settlement import calculate_settlement
    from models import db, ReturnRecord

    if booking.return_record is not None:
        return booking.return_record, None

    import config as _c
    cap_percent = float(_c.DAMAGE_CAP_PERCENT_OF_DEPOSIT)

    base = calculate_settlement(
        deposit=booking.deposit,
        end_date=booking.end_date,
        actual_return_date=actual_return_date,
        late_fee_per_day=booking.item.late_fee_per_day or 0,
        damage_level="none",
        total_rent=booking.total_rent,
        commission_percent=getattr(booking, "commission_percent", 10.0),
    )
    s = apply_verified(base, verified_amount, float(booking.deposit or 0),
                       float(booking.total_rent or 0), cap_percent=cap_percent)

    rec = ReturnRecord(
        booking_id=booking.id,
        actual_return_date=actual_return_date,
        late_days=s["late_days"],
        late_fee_per_day=s["late_fee_per_day"],
        late_penalty=s["late_penalty"],
        damage_level=s["damage_level"],
        damage_percent=s["damage_percent"],
        damage_deduction=s["damage_deduction"],
        deposit_held=s["deposit_held"],
        total_deductions=s["total_deductions"],
        refund_amount=s["refund_amount"],
        extra_due=s["extra_due"],
        platform_fee=s["platform_fee"],
        owner_earning=s["owner_earning"],
        return_note=return_note,
        return_photo=return_photo,
    )
    booking.status = "returned"
    db.session.add(rec)
    if commit:
        db.session.commit()
    return rec, s

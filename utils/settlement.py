"""Settlement calculations for returned bookings – all money math lives here."""
from datetime import date
from config import DAMAGE_LEVELS


def calculate_settlement(
    deposit: float,
    end_date: date,
    actual_return_date: date,
    late_fee_per_day: float,
    damage_level: str,
    total_rent: float = 0.0,
    commission_percent: float = 10.0,
) -> dict:
    """Calculate late fees, damage deductions, refund amount, extra due, platform fee, and owner earning."""
    deposit = float(deposit or 0)
    late_fee_per_day = float(late_fee_per_day or 0)
    total_rent = float(total_rent or 0)
    commission_percent = float(commission_percent or 0)

    # Late days and penalty
    late_days = max(0, (actual_return_date - end_date).days)
    late_penalty = late_days * late_fee_per_day

    # Damage percentage and deduction
    damage_info = DAMAGE_LEVELS.get(damage_level, {"percent": 0})
    damage_percent = float(damage_info.get("percent", 0))
    damage_deduction = deposit * (damage_percent / 100.0)

    # Deductions, refund, extra due
    total_deductions = late_penalty + damage_deduction
    refund_amount = max(0.0, deposit - total_deductions)
    extra_due = max(0.0, total_deductions - deposit)

    # Phase 6: Platform fee and net owner earning
    platform_fee = round(total_rent * (commission_percent / 100.0), 2)
    owner_earning = round(total_rent - platform_fee + late_penalty + damage_deduction, 2)

    return {
        "late_days": late_days,
        "late_fee_per_day": late_fee_per_day,
        "late_penalty": late_penalty,
        "damage_level": damage_level,
        "damage_percent": damage_percent,
        "damage_deduction": damage_deduction,
        "deposit_held": deposit,
        "total_deductions": total_deductions,
        "refund_amount": refund_amount,
        "extra_due": extra_due,
        "platform_fee": platform_fee,
        "owner_earning": owner_earning,
    }

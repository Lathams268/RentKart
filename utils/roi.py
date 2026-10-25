"""ROI tracker pure functions – item earnings, payback days, and utilization."""
from datetime import date, timedelta


class ROIProgress(tuple):
    """Custom tuple-dict hybrid for ROI progress unpacking and attribute access."""
    def __new__(cls, percent, to_recover):
        return super().__new__(cls, (percent, to_recover))

    @property
    def percent(self):
        return self[0]

    @property
    def to_recover(self):
        return self[1]

    def __getitem__(self, key):
        if isinstance(key, str):
            if key in ("percent", "progress_percent"):
                return self[0]
            if key in ("to_recover", "remaining", "amount_to_recover", "still_to_recover"):
                return self[1]
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key in ("percent", "progress_percent"):
            return self[0]
        if key in ("to_recover", "remaining", "amount_to_recover", "still_to_recover"):
            return self[1]
        return default


def item_earnings(item) -> float:
    """Sum of owner_earning from all returned bookings for an item."""
    total = 0.0
    for b in getattr(item, "bookings", []):
        if getattr(b, "status", None) == "returned":
            rec = getattr(b, "return_record", None)
            if rec and getattr(rec, "owner_earning", None) is not None:
                total += rec.owner_earning
            elif getattr(b, "owner_earning", None) is not None:
                total += b.owner_earning
            elif rec:
                total += (getattr(b, "total_rent", 0.0) or 0.0) + (getattr(rec, "total_deductions", 0.0) or 0.0)
            else:
                total += (getattr(b, "total_rent", 0.0) or 0.0)
    return round(total, 2)


def roi_progress(item) -> ROIProgress:
    """Return percent of purchase_price recovered (capped at 100) and amount still to recover."""
    pp = getattr(item, "purchase_price", None)
    if pp is None or pp <= 0:
        return ROIProgress(0.0, 0.0)

    earned = item_earnings(item)
    raw_pct = (earned / pp) * 100.0
    percent = min(100.0, round(raw_pct, 1))
    to_recover = max(0.0, round(pp - earned, 2))
    return ROIProgress(percent, to_recover)


def payback_days(item) -> int | None:
    """Days between the item's first booking start and the date earnings reached purchase_price, or None."""
    pp = getattr(item, "purchase_price", None)
    if pp is None or pp <= 0:
        return None

    bookings = getattr(item, "bookings", [])
    if not bookings:
        return None

    first_start = min(b.start_date for b in bookings)
    returned_bookings = [b for b in bookings if getattr(b, "status", None) == "returned"]
    if not returned_bookings:
        return None

    def get_ret_date(b):
        rec = getattr(b, "return_record", None)
        if rec and getattr(rec, "actual_return_date", None):
            return rec.actual_return_date
        return b.end_date

    returned_bookings.sort(key=get_ret_date)

    cum_earnings = 0.0
    for b in returned_bookings:
        rec = getattr(b, "return_record", None)
        if rec and getattr(rec, "owner_earning", None) is not None:
            cum_earnings += rec.owner_earning
        elif getattr(b, "owner_earning", None) is not None:
            cum_earnings += b.owner_earning
        elif rec:
            cum_earnings += (getattr(b, "total_rent", 0.0) or 0.0) + (getattr(rec, "total_deductions", 0.0) or 0.0)
        else:
            cum_earnings += (getattr(b, "total_rent", 0.0) or 0.0)

        if cum_earnings >= pp:
            finish_date = get_ret_date(b)
            return max(0, (finish_date - first_start).days)

    return None


def utilization_30d(item, today: date | None = None) -> float:
    """Days rented in the last 30 days divided by 30, as a percent.

    Counts only picked_up or returned bookings, clipped to the 30-day window.
    """
    if today is None:
        today = date.today()

    window_dates = {today - timedelta(days=i) for i in range(30)}
    rented_dates = set()

    for b in getattr(item, "bookings", []):
        if getattr(b, "status", None) in ("picked_up", "returned"):
            rec = getattr(b, "return_record", None)
            if b.status == "returned" and rec and getattr(rec, "actual_return_date", None):
                end_d = rec.actual_return_date
            else:
                end_d = b.end_date

            cur = b.start_date
            while cur <= end_d:
                if cur in window_dates:
                    rented_dates.add(cur)
                cur += timedelta(days=1)

    rented_count = len(rented_dates)
    return round((rented_count / 30.0) * 100.0, 1)


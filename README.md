# RentKart 🛒

Hyperlocal peer-to-peer rental marketplace for Indian communities, towns, and neighborhoods. Borrow what you need from verified locals, or turn idle household and farm equipment into daily income.

---

## Features

- **Hyperlocal Discovery**: Distance-based search with GPS geo-filtering and interactive Leaflet map view.
- **Dynamic Category Specifications**: Tailored fields for Clothes, Books, Farm Tools, Electronics, and Event Items.
- **Smart Deposits & Trust Score**: Renter trust tiers (New/Risky, Trusted, Highly Trusted) that reduce security deposits by up to 50% for reliable community members.
- **Visual Handover & Return Settlement**: Photographic proof and condition notes for handover and return, with automatic calculation of late penalties, damage deductions, and deposit refunds.
- **Multi-Language Support**: Seamless language toggle supporting English, Hindi (हिंदी), Telugu (తెలుగు), and Kannada (ಕನ್ನಡ) with native Google Fonts.
- **Multilingual Voice Search**: Web Speech API voice search supporting spoken English, Hindi, Telugu, and Kannada.
- **Smart Price Suggestions & Seasonal Boosts**: Automated pricing hints and 20% seasonal demand boosts (Wedding, Festival, and Harvest seasons).
- **Owner ROI Tracker & Insights**: Payback day calculation, 30-day utilization metrics, net earnings summaries, and idle item tips (Pro & Business tiers).
- **Digital Storefronts & QR Flyers**: Branded owner shop pages with downloadable QR codes and printable market posters.
- **Subscription Plans**: Free, Pro (₹99/mo), and Business (₹299/mo) plans with item listing limits, reduced commission, and featured search placement.
- **Community Feedback & Admin Moderation**: In-app feedback system with admin replies and badge notifications.

---

## Setup & Running

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Seed Demo Database
```bash
python seed.py
```
*(The seed script is idempotent and safe to run multiple times)*

### 3. Run Application
```bash
python app.py
```
Or with custom environment variables:
```bash
HOST=0.0.0.0 PORT=5000 DEBUG=True python app.py
```
Access the application at: `http://localhost:5000`

### 4. Run Production Server (Gunicorn)
```bash
gunicorn app:app
```

---

## Running Tests

Run all unit and integration tests across Phases 1 to 7:
```bash
python -m unittest discover -p "test_phase*.py"
```

Or run individual phase tests:
```bash
python test_phase1.py
python test_phase2.py
python test_phase3.py
python test_phase4.py
python test_phase5.py
python test_phase6.py
python test_phase7.py
```

---

## Demo Accounts

All demo accounts log in via phone number with the universal demo OTP: **`1234`**.

| Name | Phone Number | Role / Plan | Description |
| :--- | :--- | :--- | :--- |
| **Ramesh Patel** | `9876543210` | Owner (Free) | Rural equipment & event rentals (Hoskote) |
| **Lakshmi Devi** | `9876543211` | Owner (Pro) | Tools, textbooks & saree rentals (Devanahalli) |
| **Suresh Kumar** | `9876543212` | Owner (Pro) | Electronics & power tools (Whitefield) |
| **Priya Sharma** | `9876543213` | Owner (Business) | High-end cameras, sherwanis & tents (Indiranagar) |
| **Admin User** | `9999999999` | Platform Admin | Admin moderation & platform analytics |

## 🛡️ RentKart TrustShield (AI-assisted damage protection)

TrustShield adds a verified photo/video condition record to every rental so damage
is never wrongly attributed to the wrong customer. It is fully **additive** — old
bookings keep the original one-click handover/return flow.

**How it works**
1. **Before handover** the owner uploads clear photos by angle (front, back, left,
   right, top, close-up, accessories, serial), optional videos, a category checklist
   and any existing damage. The booking moves to `awaiting_customer_confirmation`.
2. **The renter reviews** the condition gallery and must actively confirm before the
   item is marked picked up (or report a mismatch / cancel with the existing refund).
3. **On return** the owner uploads a matching set. Pillow pairs the photos by angle,
   normalises them and flags changed regions as *suggestions only* — with a
   side-by-side overlay. Regions that overlap a known unrepaired damage are never
   attributed to this renter.
4. **Human verification** turns a suggestion into a proposed penalty from
   `TS_DAMAGE_RULES` (whole-rupee range; amounts above the range need a quote and
   admin approval; capped at `DAMAGE_CAP_PERCENT_OF_DEPOSIT`). Nothing is ever
   charged from the automatic comparison alone.
5. **The renter reviews** the evidence and may accept, partially accept, or dispute.
   Finalisation happens **only** when the renter accepts all items or an admin
   resolves a dispute; a passed deadline goes to admin review and charges nothing.

**Where it appears** — the renter dashboard shows four cards per TrustShield booking
(Original condition, Return condition, Damage report, Deposit refund status) plus a
pending-actions box; the owner dashboard lists pending handovers, returns awaiting
review and open disputes; `/items/<id>/condition-history` shows every rental with
both galleries and the full item damage history with a *Mark as repaired* action. It
works for every category (clothing, electronics, books, furniture and more) via
`config.py`.

**New page / command**
```bash
del rentkart.db
python seed.py     # also seeds TrustShield demo data (idempotent)
python app.py
```

**New environment variables** (all optional)
- `TRUSTSHIELD_ENABLED` – `True` (default) gives new bookings `trustshield=True`.
- `VISION_API_KEY` – if unset (default) no external AI is ever called; comparison is
  Pillow-only. The key is never logged.

Evidence is stored **privately** under `instance/evidence` with random UUID names,
EXIF/GPS stripped and photos resized, and is served only through `GET /evidence/<id>`
to the renter, the item owner and admins (403 otherwise).

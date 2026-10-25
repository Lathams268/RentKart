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
- **Accounts & verification**: Email + password signup with international (E.164) phone numbers, a 6-digit OTP for phone/email verification, phone+OTP login, forgot-password reset, and an editable profile with verification status.
- **Hardened payments**: Server-created Razorpay orders, server-side signature checks, idempotent webhooks, full/deposit refunds, receipts, and email/SMS confirmations.
- **Search that finds things**: Case-insensitive, partial and fuzzy search across title, description, category and tags, with price/location filters, sorting, and a helpful empty state.
- **Real listing photos**: up to 6 photos per listing (JPG/PNG/WebP, 5 MB each) validated and re-encoded into a thumbnail + large copy, cover photos on cards, a detail gallery with thumbnails and a zoom lightbox, and Pexels-licensed seed photos for every demo item.

---

## Setup & Running

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure the environment
```bash
cp .env.example .env        # Windows: copy .env.example .env
```
The development defaults work unchanged: OTP codes are printed to the server
console and payments use the built-in mock gateway. Fill in Razorpay / SMTP /
SMS values only when you want real delivery. See `.env.example` for every
variable.

### 3. Seed Demo Database
```bash
python seed.py
```
*(The seed script is idempotent and safe to run multiple times. It creates 94
items across clothes, bikes, cameras, tents, tools and electronics, with real
seed photos, prices, deposits, owners, locations and search tags.)*

On a **new, empty** database the app can also seed itself once at startup (see
[Deploy on Render](#deploy-on-render-free-postgresql--cloudinary)): seeding
runs only while there are no users and no listings, so a restart or redeploy
never re-seeds or overwrites existing users, bookings or listings.

### 4. Run Application
```bash
python app.py
```
Or with custom environment variables:
```bash
HOST=0.0.0.0 PORT=5000 DEBUG=True python app.py
```
Access the application at: `http://localhost:5000`

### 5. Run Production Server (Gunicorn)
```bash
gunicorn app:app
```

---

## Deploy on Render (free PostgreSQL + Cloudinary)

A free Render web service has an **ephemeral disk**: `rentkart.db` and anything
written to `static/uploads` (or `static/media`) is lost on every restart and
redeploy. Two free services fix that - Render PostgreSQL for the data and
Cloudinary for uploaded photos. Only environment variables change; no route,
template or feature is touched.

### 1. Create the free PostgreSQL database
1. Render dashboard → **New +** → **Postgres**.
2. Choose the **Free** plan, a region close to the web service, then
   **Create Database**.
3. When it is available, copy the **Internal Database URL**
   (`postgresql://rentkart:...@dpg-..../rentkart_...`).

> Render's free PostgreSQL plan is capped at 1 GB and the database **expires
> 30 days after creation** (Render reduced this from 90 days in May 2024).
> When it expires, create a new free database and update `DATABASE_URL` on the
> web service - the app rebuilds the schema on the empty database and seeds the
> demo catalogue once. Data does not survive the expiry itself, so export a
> dump first if you need it.

### 2. Set `DATABASE_URL` on the web service
1. Open the web service → **Environment** → **Add Environment Variable**.
2. `DATABASE_URL` = the *Internal Database URL* copied above. Both the internal
   and external URL work; a legacy `postgres://` prefix is rewritten to
   `postgresql://` and the psycopg2 driver (installed from `requirements.txt`) is
   pinned explicitly, so the URL works on any SQLAlchemy 2.x.
3. Save - Render restarts the service once. `db.create_all()` builds the whole
   schema on the empty database and, because Render sets `RENDER=true`,
   `AUTO_SEED` is on: the demo catalogue (users, listings, bookings, seed
   photos) is inserted **once**. Every later boot finds existing rows and skips
   seeding, so nothing is overwritten.
4. Prefer to control seeding yourself? Set `AUTO_SEED=False` and run
   `python seed.py` from the Render **Shell** once. Without `DATABASE_URL` the
   app keeps using the local `rentkart.db` file, exactly as before.

### 3. Create the free Cloudinary storage
1. Sign up at [cloudinary.com](https://cloudinary.com) (free tier).
2. Dashboard → **Product Environment Credentials** → copy the
   **API Environment variable**:
   `CLOUDINARY_URL=cloudinary://<api_key>:<api_secret>@<cloud_name>`.
3. Render → the web service → **Environment** → add `CLOUDINARY_URL` with that
   value and save. Redeploy to be sure.
4. New listing photos (cover + gallery, thumbnail + large copy) are now uploaded
   to Cloudinary and served from its CDN - they survive restarts. Without
   `CLOUDINARY_URL` the app keeps writing to the local media folder (local dev).
   The separate `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` /
   `CLOUDINARY_API_SECRET` variables still work too.

### 4. Production environment variables

Minimum to set on Render:

| Variable | Value on Render |
| :--- | :--- |
| `DATABASE_URL` | PostgreSQL *Internal Database URL* |
| `SECRET_KEY` | a long random string (default is a dev placeholder) |
| `CLOUDINARY_URL` | Cloudinary API environment variable (cloud photo storage) |
| `OTP_MODE` | `console` (demo, code in the service log), `demo` (fixed 1234) or `sms` |
| `EMAIL_PROVIDER` | `console` (log) or `smtp` |
| `PAYMENT_MODE` | `mock` (no money moves) or `razorpay` with live/test keys |
| `AUTO_SEED` | optional; defaults to on for Render, off elsewhere |

`config.py` loads a local `.env` file when `python-dotenv` is installed (local
development only). On Render the values come from the dashboard and a blank
value always falls back to the default listed below.

#### Complete environment variable reference

The running app reads the 104 variables below (101 in `config.py`, plus
`HOST`/`PORT`/`DEBUG` in `app.py` when started with `python app.py`);
`tools/fetch_stock_photos.py` additionally reads `PEXELS_API_KEY`, which no
runtime code uses.

**Core / deployment**

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `DATABASE_URL` | unset - `rentkart.db` SQLite file | PostgreSQL URL; `postgres://` is rewritten and the psycopg2 driver pinned |
| `SECRET_KEY` | `rentkart-dev-secret-key-change-me` | Flask session/CSRF signing key - change in production |
| `AUTO_SEED` | off; on when `RENDER=true` | Seed demo data once, only on an empty database |
| `RENDER` | unset | Set to `true` by Render; only used as the `AUTO_SEED` default |
| `HOST` | `0.0.0.0` | `python app.py` only (gunicorn ignores it) |
| `PORT` | `5000` | `python app.py` only |
| `DEBUG` | `False` | `python app.py` only |

**Media storage**

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `CLOUDINARY_URL` | unset | `cloudinary://<api_key>:<api_secret>@<cloud_name>`; switches uploads to Cloudinary |
| `MEDIA_BACKEND` | `local`, or `cloudinary` when `CLOUDINARY_URL` is set | Force `local`, `s3` or `cloudinary` |
| `MEDIA_FOLDER` | `static/media` | Local media folder |
| `CLOUDINARY_CLOUD_NAME` | taken from `CLOUDINARY_URL` | Individual credential (optional) |
| `CLOUDINARY_API_KEY` | taken from `CLOUDINARY_URL` | Individual credential (optional) |
| `CLOUDINARY_API_SECRET` | taken from `CLOUDINARY_URL` | Individual credential (optional) |
| `S3_BUCKET` | empty | Only for `MEDIA_BACKEND=s3` |
| `S3_REGION` | empty | Only for `MEDIA_BACKEND=s3` |
| `S3_ACCESS_KEY_ID` | empty | Only for `MEDIA_BACKEND=s3` |
| `S3_SECRET_ACCESS_KEY` | empty | Only for `MEDIA_BACKEND=s3` |
| `S3_PUBLIC_BASE_URL` | empty | Only for `MEDIA_BACKEND=s3` |
| `PHOTO_MAX_MB` | `5` | Max size of one listing photo |
| `PHOTO_MAX_PER_ITEM` | `6` | Max photos per listing |
| `PHOTO_LARGE_PX` | `1600` | Large copy max dimension |
| `PHOTO_THUMB_PX` | `600` | Thumbnail max dimension |
| `PHOTO_JPEG_QUALITY` | `82` | Re-encode quality |

**Sessions and rate limits**

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `SESSION_COOKIE_SAMESITE` | `Lax` | Session/remember cookie SameSite |
| `SESSION_COOKIE_SECURE` | `False` | Set `True` when served over HTTPS |
| `SESSION_DAYS` | `14` | Session lifetime in days |
| `AUTH_RATE_LIMIT_WINDOW_MINUTES` | `15` | Sliding window for auth limits |
| `AUTH_RATE_LIMIT_LOGIN` | `20` | Login OTP requests per window |
| `AUTH_RATE_LIMIT_SIGNUP` | `10` | Signups per window |
| `AUTH_RATE_LIMIT_OTP` | `30` | OTP requests per window |

**OTP and phone verification**

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `OTP_MODE` | `console` | `console`, `demo` (fixed code) or `sms` |
| `DEMO_OTP` | `1234` | Fixed code used by `console`/`demo` |
| `OTP_LENGTH` | `6` | Digits in a generated code |
| `OTP_EXPIRY_MINUTES` | `5` | Code lifetime |
| `OTP_MAX_ATTEMPTS` | `5` | Wrong guesses per code |
| `OTP_RESEND_SECONDS` | `30` | Cooldown between sends |
| `OTP_MAX_SENDS` | `5` | Sends allowed per window |
| `OTP_SEND_WINDOW_MINUTES` | `60` | Send-limit window |
| `OTP_LOCK_MINUTES` | `15` | Lockout after too many sends |
| `DEFAULT_COUNTRY_CODE` | `IN` | Default phone region |
| `DEFAULT_COUNTRY_DIAL` | `+91` | Default dialling code |

**SMS providers** (only used when `OTP_MODE=sms`)

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `SMS_PROVIDER` | `msg91` | `msg91`, `twilio` or `fast2sms` |
| `SMS_SENDER_ID` | `RENTKT` | Sender id |
| `SMS_API_KEY` | empty | Generic SMS key |
| `FAST2SMS_ROUTE` | `otp` | Fast2SMS route |
| `FAST2SMS_API_KEY` | empty | Fast2SMS key |
| `TWILIO_ACCOUNT_SID` | empty | Twilio account |
| `TWILIO_AUTH_TOKEN` | empty | Twilio token |
| `TWILIO_PHONE_NUMBER` | empty | Twilio sender number |
| `TWILIO_MESSAGING_SERVICE_SID` | empty | Twilio messaging service |
| `MSG91_AUTH_KEY` | empty | MSG91 auth key |
| `MSG91_TEMPLATE_ID` | empty | MSG91 DLT template |
| `MSG91_SENDER_ID` | empty | MSG91 DLT sender id |
| `MSG91_OTP_VARIABLE` | `OTP` | Template variable name |

**Email**

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `EMAIL_PROVIDER` | `console` | `console` (log) or `smtp` |
| `MAIL_FROM` | `no-reply@rentkart.local` | From address |
| `SMTP_HOST` | empty | SMTP server |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USERNAME` | empty | SMTP user |
| `SMTP_PASSWORD` | empty | SMTP password |
| `SMTP_USE_TLS` | `True` | STARTTLS |
| `APP_BASE_URL` | `http://localhost:5000` | Base URL used in emails |

**Checkout fees and payments**

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `RENTER_FEE_PERCENT` | `0` | Legacy renter fee percent |
| `RENTER_FEE_MIN` | `0` | Legacy minimum fee |
| `RENTER_FEE_MAX` | `50` | Legacy maximum fee |
| `TAX_PERCENT` | `0` | Tax percent |
| `PAYMENT_MODE` | `mock` | `mock` or `razorpay` |
| `RAZORPAY_KEY_ID` | empty | Razorpay key id |
| `RAZORPAY_KEY_SECRET` | empty | Razorpay key secret |
| `RAZORPAY_WEBHOOK_SECRET` | empty | Webhook signature secret |
| `UPI_ID` | empty | Payee UPI id (demo id when empty) |
| `UPI_PAYEE_NAME` | `RentKart` | UPI payee name |

**TrustShield**

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `TRUSTSHIELD_ENABLED` | `True` | Feature toggle |
| `VISION_API_KEY` | empty | Enables AI vision when set |
| `MAX_PHOTO_MB` | `6` | Evidence photo cap |
| `MAX_VIDEO_MB` | `40` | Evidence video cap |

**Revenue features**

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `REVENUE_ENABLED` | `True` | Master switch for every revenue feature |
| `REVENUE_RENTER_FEE_ENABLED` | `True` | Renter platform fee |
| `REVENUE_RENTER_FEE_PERCENT` | `8` | Fee percent |
| `REVENUE_RENTER_FEE_MIN_PAISE` | `2900` | Minimum fee (paise) |
| `REVENUE_RENTER_FEE_MAX_PAISE` | `99900` | Maximum fee (paise) |
| `REVENUE_OWNER_COMMISSION_ENABLED` | `True` | Owner commission |
| `REVENUE_OWNER_COMMISSION_PERCENT` | `5` | Commission percent |
| `REVENUE_COMMISSION_WAIVER_BOOKINGS` | `3` | First bookings without commission |
| `REVENUE_FEATURED_ENABLED` | `True` | Paid featured listings |
| `REVENUE_OWNER_PRO_ENABLED` | `True` | Owner Pro subscription |
| `REVENUE_OWNER_PRO_PRICE_PAISE` | `39900` | Owner Pro monthly price |
| `REVENUE_OWNER_PRO_YEARLY_DISCOUNT_PERCENT` | `20` | Yearly discount |
| `REVENUE_OWNER_PRO_COMMISSION_PERCENT` | `2` | Pro commission percent |
| `REVENUE_OWNER_PRO_PHOTOS` | `12` | Photo limit for Pro owners |
| `REVENUE_OWNER_PRO_FREE_FEATURED_DAYS` | `7` | Free featured days |
| `REVENUE_PROTECTION_ENABLED` | `True` | Rental protection add-on |
| `REVENUE_PROTECTION_PERCENT` | `5` | Protection price percent |
| `REVENUE_PROTECTION_COVER_PAISE` | `500000` | Cover amount (paise) |
| `REVENUE_PENALTY_SHARE_ENABLED` | `True` | Platform penalty share |
| `REVENUE_PENALTY_SHARE_PERCENT` | `15` | Platform share percent |
| `REVENUE_SERVICES_ENABLED` | `True` | Delivery/cleaning services |
| `REVENUE_SERVICE_DELIVERY_PAISE` | `9900` | Delivery service price |
| `REVENUE_SERVICE_CLEANING_PAISE` | `19900` | Cleaning service price |
| `REVENUE_SERVICE_MARGIN_PERCENT` | `30` | Service margin |
| `REVENUE_ADS_ENABLED` | `True` | Sponsored banners |
| `REVENUE_LEDGER_ENABLED` | `True` | Revenue ledger |
| `REVENUE_GST_PERCENT` | `18` | GST percent |
| `REVENUE_GATEWAY_PERCENT` | `2` | Gateway fee percent |

The seed photos live in the repository (`static/seed_images/`, 216 photos plus
`CREDITS.md`), so demo listings keep their pictures after any restart or
redeploy - on SQLite and on PostgreSQL alike. Every template and static asset
is committed as well: 59 templates, 286 static files (including 62
illustration SVGs and the `static/uploads` / `static/media` placeholders), and
all 6,416 tracked paths match their on-disk names exactly, so Render's
case-sensitive Linux filesystem serves each one.

> Note: handover/return proof photos and shop logos still use the instance's
> `static/uploads` folder (the existing templates read them from there); listing
> photos are the ones stored on Cloudinary.

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

New regression suites for auth, OTP, search and payments:
```bash
python -m unittest test_auth_signup test_otp_flows test_search test_payment_flows
```

| Suite | Covers |
| :--- | :--- |
| `test_auth_signup.py` | Signup validation, E.164 phones, duplicate email/phone, email login, profile edit, forgot password |
| `test_otp_flows.py` | Hash-only storage, 5 min expiry, 5 wrong attempts → 15 min lock, resend cooldown, resend invalidation, 5 sends/hour, change/alternate number |
| `test_search.py` | "dress" / "Dress" / "dres" / "party dress", description/tag/category hits, filters, sorting, empty state |
| `test_payment_flows.py` | Tax line, signature verification, retries, idempotent webhooks (captured / failed / refund), cancellation audit, deposit refund, per-user events |

Run everything (a couple of minutes):
```bash
python -m unittest discover -s . -p "test_*.py"
```

---

## Accounts, OTP and profiles

- **Sign up** at `/signup` (alias `/register`): full name, email, phone with a
  country-code selector (any of 60+ countries, validated with libphonenumber to
  E.164), password + confirm, address (line 1, line 2, city, state, postal code,
  country), role (Renter / Owner / Both) and the terms checkbox. Validation runs
  on the client and again on the server: required fields, email format, password
  strength (8+ chars, 3 of lowercase/uppercase/digit/symbol or 12+ chars), unique
  email and unique phone.
- **Login** at `/login`: phone → OTP for existing users, or the email + password
  form (`/login?mode=email`). Passwords are bcrypt hashes (Werkzeug scrypt is the
  fallback if bcrypt is not installed); sessions are HttpOnly + SameSite with a
  14-day lifetime, and auth endpoints are rate limited per IP.
- **Forgot password** at `/forgot-password`: enter an email or phone, receive a
  code (logged in console mode), then set a new password at `/reset-password`.
- **Profile** at `/profile`: edit name, email, phone and default address, change
  the password, and see verification status for Email, Phone, Address and ID.
- **Verification** at `/verify-phone` and `/verify-email`. The phone screen
  supports resend, **change number** (the account only changes after the new
  number is verified) and an **alternate number** verified the same way. Codes
  auto-focus / auto-advance, support paste and use a numeric keypad on mobile.

### Testing OTP without paying for SMS

With the default `OTP_MODE=console`, the 6-digit code is printed in the server
console (`[RentKart dev OTP] ...`) and shown in the amber dev box / flash message
on the verification page. Nothing is sent by SMS or email. The legacy demo
accounts still accept `DEMO_OTP` (`1234`) on the phone login screen.

Policy (all configurable in `.env`): 5-minute expiry, 5 wrong attempts then a
15-minute lock, 30-second resend countdown, max 5 sends per hour per target, and
every resend invalidates the previous code. Only an HMAC hash is stored — never
the code itself. A verified phone sets `phone_verified`, which feeds the trust
score's identity factor.

The login and verification screens say **"Dev mode: OTP is printed in the
server terminal."** whenever `OTP_MODE=console`, so nobody waits for an SMS
that will never arrive. "Resend OTP" (30-second timer) and "Change number" work
in both console and SMS mode.

### Switching from console to real SMS

1. Pick a provider and put its credentials in `.env` (never commit this file).
2. Set `OTP_MODE=sms` and `SMS_PROVIDER` to that provider.
3. Restart the app. `python -c "from utils.sms import provider_status; print(provider_status())"`
   inside the app context prints the active provider and any missing key.

**MSG91 (India, DLT template):**
```dotenv
OTP_MODE=sms
SMS_PROVIDER=msg91
MSG91_AUTH_KEY=<your MSG91 authkey>
MSG91_TEMPLATE_ID=<DLT-approved Flow template id>
MSG91_SENDER_ID=<6-char DLT sender id, optional for Flow>
MSG91_OTP_VARIABLE=OTP
```
The template must contain one variable (default name `OTP`); the 6-digit code is
sent in that variable to `91XXXXXXXXXX`. Create the template in MSG91 → Flow and
have it DLT-approved before switching.

**Twilio:**
```dotenv
OTP_MODE=sms
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=<your auth token>
TWILIO_PHONE_NUMBER=+91XXXXXXXXXX
# or, instead of a sender number:
TWILIO_MESSAGING_SERVICE_SID=MGxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
Indian numbers are normalised to E.164 (`+91...`). Twilio still requires the
sender/DLT registration on your Twilio account; use a Messaging Service if your
number is pooled.

Provider failures never crash the flow: the user sees a specific message (missing
key, rejected credentials, rate limit, provider text such as "Insufficient
balance", or "SMS service is unreachable") and can retry, resend after the
30-second timer, or change the number.

## Search and listings

- `/browse?q=...` is case-insensitive and matches partial words and tags across
title, description, category label, sub-category, tags, attributes and the
owner's shop: `dress`, `Dress`, `dres` and `party dress` all find the dress.
- Filters: category, min/max price, location (owner city or shop address),
  max distance and category-specific attributes. Sorting: `cheapest`,
  `price_high`, `newest`, or nearest by default.
- When nothing matches, the page shows `No items match “... ”` with the search
  term, removable filter chips and category shortcuts instead of a bare
  "not found".
- Seed data: `python seed.py` creates 94 items (dresses, bikes, cameras, tents,
  tools, electronics, books, event items, farm tools) with real photos, price per
  day, deposit, owner, availability, city and tags. It is idempotent and also
  backfills photos onto databases seeded before `static/seed_images` existed.
  Demo owners are upgraded to plans that fit their catalogue so the listing cap
  never hides seeded items.
- Owners can create (`/items/add`), edit (Edit link on the owner dashboard, with
  every category field prefilled) and pause/resume listings (`/items/<id>/toggle`),
  and manage up to 6 photos per listing (see below). The detail page shows the
  gallery with thumbnails and a zoom lightbox, price / deposit, owner info,
  availability calendar and a **Rent now** button.

## Listing photos

- **Uploading:** the create/edit listing form takes up to **6 photos** in one
  input (JPG, PNG or WebP, max **5 MB** each). Every file is checked by Pillow
  (real image bytes, not just the extension), rotated by EXIF, flattened onto
  white when transparent, and re-encoded twice with LANCZOS resizing:
  - `<uuid>.jpg` — large copy, max 1600 px (detail page + lightbox)
  - `<uuid>_thumb.jpg` — thumbnail, max 600 px (cards, thumbnail strip)
  Files that fail validation (wrong type, too big, corrupt, empty) reject the form
  with a message naming the file and the limit.
- **Storage:** `MEDIA_BACKEND` picks the backend. `local` (default) writes to
  `MEDIA_FOLDER` (`static/media/`, ignored by git, served from `/static/media`).
  `s3` uses boto3 with `S3_BUCKET` / `S3_REGION` / `S3_ACCESS_KEY_ID` /
  `S3_SECRET_ACCESS_KEY` and an optional `S3_PUBLIC_BASE_URL`. `cloudinary` uses
  `CLOUDINARY_URL` (or `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` /
  `CLOUDINARY_API_SECRET`) and is selected automatically whenever
  `CLOUDINARY_URL` is set, which is what keeps photos alive on Render.
  Missing settings or SDKs raise a clear `MediaError` instead of silently
  dropping the photo. Tunables: `PHOTO_MAX_MB`, `PHOTO_MAX_PER_ITEM`,
  `PHOTO_LARGE_PX`, `PHOTO_THUMB_PX`, `PHOTO_JPEG_QUALITY`.
- **Display:** cards show the first photo with `object-fit: cover` and
  `loading="lazy"`; the detail page shows the large copy, a thumbnail strip and a
  full-screen lightbox (click the photo or **Zoom**; Esc/←/→ navigate).
- **Placeholder:** only listings without any usable photo fall back to the clean
  category illustration / initials placeholder.
- **Demo seed photos:** `static/seed_images/<category>/<subcategory>-<n>.jpg`
  (216 Pexels photos, Pexels License). `seed.py` gives every demo item a cover
  plus up to 3 gallery photos chosen deterministically by title, so each
  sub-category shows different pictures. "Dress" listings use the western/party
  dress set. Every category has at least five listings with real photos
  (clothes 45, electronics 10 including 5 cameras, tents/events 7, farm tools 5,
  bikes 5, books 21).
  `static/seed_images/CREDITS.md` lists every file with its Pexels page.
  Re-download with `python tools/fetch_seed_photos.py` (no API key needed);
  `--force` re-fetches, `--only clothes` limits the category.

## Booking and payments

**Flow:** checkout (dates, address, delivery) → `pending_payment` (auto-cancels
after 15 minutes) → payment → `requested` → owner approves → `picked_up` →
`returned` → `completed`; `cancelled` / `rejected` from any pre-pickup state.
Already-booked dates are blocked on the item page and re-checked server-side
before payment.

**Price breakdown** (all computed server-side and snapshotted on the booking):
rent + security deposit + delivery + platform fee (`RENTER_FEE_PERCENT`) +
taxes (`TAX_PERCENT`, shown as its own "Taxes" line when non-zero). The receipt
and confirmation pages read the snapshot, never the browser.

**Mock mode** (`PAYMENT_MODE=mock`, the default): the pay page shows a demo UPI
QR plus "Simulate: I have paid / timed out / declined" buttons. No money moves.

**Razorpay test mode:**
1. Put your **test** keys in `.env`: `PAYMENT_MODE=razorpay`,
   `RAZORPAY_KEY_ID=rzp_test_...`, `RAZORPAY_KEY_SECRET=...` and a
   `RAZORPAY_WEBHOOK_SECRET` of your choice.
2. The server creates the order (amount in paise from the booking snapshot),
   Razorpay Checkout collects the payment, and the callback is accepted only
   when the HMAC-SHA256 `order|payment` signature verifies server-side. A bad
   signature or a mismatched order is recorded as a failed attempt and never
   marks the booking paid.
3. Point a Razorpay webhook at `https://<your-host>/webhooks/razorpay` with the
   same secret. `payment.captured`, `payment.failed` and `refund.processed` are
   verified over the raw body and applied idempotently (`WebhookEvent` dedupes by
   event id). Locally, expose the app with a tunnel (e.g. `ngrok http 5000`).

**Refunds:** a cancellation refunds the captured amount in full; a successful
return refunds the security deposit minus late/damage deductions and records a
`deposit_refund` Payment row. Razorpay refunds are attempted automatically;
if the gateway call fails the row stays for manual follow-up and the user sees
a clear warning. **Notifications:** booking confirmed, cancellation and refund
messages go out by email/SMS (`EMAIL_PROVIDER=console` logs them in dev).

**Cancellations** record who cancelled, when and why (`plans_changed`,
`found_elsewhere`, `wrong_dates`, ... plus an optional note) — ready for fair
trust scoring.

**Trust Score readiness:** every signup, login, verification, listing,
booking, approval/rejection, payment, refund, cancellation, handover, return and
completion writes an append-only `UserEvent` row. Query a user's history with
`utils.events.events_for_user(user)` or `count_events(user, kind)`.

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

---

## Revenue features

Everything in this section is additive. Set `REVENUE_ENABLED=False` (environment
variable or `config.py`) to restore the previous checkout and commission behaviour
exactly; every individual stream also has its own switch. In development all
switches default to ON, while the legacy unit-test suite keeps them OFF unless a
test opts in with `REVENUE_ENABLED=True`.

### Where to configure

- **Admin UI:** `/admin/revenue/settings` (login + `is_admin` required). Changes are
  stored in the new `revenue_setting` table and apply to **new** bookings only.
- **Config / environment:** the `REVENUE_*` block at the bottom of `config.py`.

| Setting | Default | Meaning |
| --- | --- | --- |
| `REVENUE_ENABLED` | `True` | Master switch for all streams |
| `REVENUE_RENTER_FEE_ENABLED` / `_PERCENT` | `True` / `8` | Renter platform fee, % of rent |
| `REVENUE_RENTER_FEE_MIN_PAISE` / `_MAX_PAISE` | `2900` / `99900` | Fee floor (Rs 29) and cap (Rs 999) |
| `REVENUE_RENTER_FEE_CATEGORY_OVERRIDES` | `{}` | Optional per-category percent, e.g. `{"clothes": 6}` |
| `REVENUE_OWNER_COMMISSION_ENABLED` / `_PERCENT` | `True` / `5` | Commission deducted from owner payouts |
| `REVENUE_COMMISSION_WAIVER_BOOKINGS` | `3` | First N paid bookings pay 0% commission |
| `REVENUE_FEATURED_ENABLED` / `_PRICES_PAISE` | `True` / `1:9900, 2:19900, 3:29900` | Featured packages per week |
| `REVENUE_OWNER_PRO_ENABLED` | `True` | Owner Pro plan sold from `/pricing` |
| `REVENUE_OWNER_PRO_PRICE_PAISE` | `39900` | Owner Pro monthly price (Rs 399) |
| `REVENUE_OWNER_PRO_YEARLY_DISCOUNT_PERCENT` | `20` | Yearly Owner Pro discount |
| `REVENUE_OWNER_PRO_COMMISSION_PERCENT` | `2` | Commission while Owner Pro is active |
| `REVENUE_OWNER_PRO_PHOTOS` | `12` | Photo limit for Owner Pro listings |
| `REVENUE_OWNER_PRO_FREE_FEATURED_DAYS` | `7` | One free featured week per month |
| `REVENUE_PROTECTION_ENABLED` / `_PERCENT` | `True` / `5` | Damage protection add-on, % of rent |
| `REVENUE_PROTECTION_COVER_PAISE` | `500000` | Maximum protection claim (Rs 5,000) |
| `REVENUE_PENALTY_SHARE_ENABLED` / `_PERCENT` | `True` / `15` | Platform share of late/damage fees |
| `REVENUE_SERVICES_ENABLED` | `True` | Delivery/pickup and cleaning add-ons |
| `REVENUE_SERVICE_DELIVERY_PAISE` / `_CLEANING_PAISE` | `9900` / `19900` | Service prices (Rs 99 / Rs 199) |
| `REVENUE_SERVICE_MARGIN_PERCENT` | `30` | Platform margin kept per service |
| `REVENUE_ADS_ENABLED` | `True` | Sponsored banners on home/browse |
| `REVENUE_LEDGER_ENABLED` | `True` | Write entries to the revenue ledger |
| `REVENUE_GST_PERCENT` / `REVENUE_GATEWAY_PERCENT` | `18` / `2` | GST (inclusive) and gateway-cost estimate |

### Money rules

- New money columns are **integer paise**; existing booking columns stay in rupees.
- The renter fee is computed from rent only. **Security deposits are never revenue**
  and never appear in the ledger.
- The fee and commission are snapshotted on the booking (`platform_fee`,
  `commission_percent`), so later setting changes cannot rewrite old bookings.
- GST is treated as included in the gross platform amount:
  `gst = gross * 18 / 118`; gateway cost is `2%` of gross; `net = gross - gst - gateway`.
- Payments stay in mock/demo mode. No real money is charged.

### Revenue streams

1. **Renter platform fee** - separate checkout line with a "Why this fee?" tooltip.
   Refunded in full when the booking is cancelled or refunded, including owner
   cancellations and owner rejections.
2. **Owner commission** - deducted from payout; waived for the first N paid bookings
   as a launch offer. Snapshot per booking.
3. **Featured listings** - `/owner/featured`; Rs 99/199/299 per week, top placement
   in search and category rows, reuses the existing Featured badge, auto-expires.
4. **Owner Pro** - an extra card on `/pricing` (Rs 399/month or yearly with 20% off).
   Gives 2% commission, 12 photos, listing analytics and one free featured week per
   month. Existing Free/Pro/Business plans are untouched.
5. **Damage protection add-on** - optional 5% checkout checkbox covering claims up
   to Rs 5,000. Admin records claims on `/admin/revenue`; add-on income vs claims
   paid shows the net margin.
6. **Late/damage fee share** - when the existing return flow records a late or
   damage deduction, 15% is booked as platform revenue and the owner keeps the rest.
7. **Extra services** - optional delivery/pickup (Rs 99) and cleaning (Rs 199)
   checkboxes at checkout; the platform keeps a margin, the owner gets the rest.
8. **Sponsored banners** - `/admin/revenue/ads` creates image/link/date/price ads.
   They appear on home and browse labelled **Sponsored**, with impressions, clicks
   and CTR recorded in `banner_event`.
9. **Revenue ledger + dashboard** - `/admin/revenue` (admin only) shows cards for
   earned, pending, refunded, GST, net after costs and deposits held; filters for
   today/7/30 days or a custom range; revenue-per-day and revenue-by-source charts;
   recent transactions; CSV export. `/admin/revenue/export.csv` exports the raw
   ledger, `/owner/earnings.csv` exports an owner payout history.

### Ledger lifecycle

New `revenue_entries` (model `RevenueEntry`) rows are **pending** when payment is
captured and become **earned** when the rental completes. Cancellations and refunds
mark the originals **refunded** and add negative mirror entries, so the ledger always
nets to zero for refunded bookings. Security deposits are never part of the ledger.

### New tables (no existing column is altered)

`revenue_setting`, `revenue_entry`, `booking_addon`, `featured_listing`,
`protection_claim`, `banner_ad`, `banner_event`. They are created by the existing
`db.create_all()` call. On SQLite the app writes a one-time backup named
`<database>.pre_revenue_<timestamp>.bak` before the revenue tables exist.

### Demo data

`python seed.py` adds about 40 ledger rows over the last 30 days, a live sponsored
banner, one featured listing and a protection claim, so the dashboard charts are
populated in development. Seeding is idempotent and skipped in tests.


# RentKart — Debug Report (reproduced 2026-10-25)

Scope: three reported failures (auth, payments, listings/search) reproduced against a
clean checkout (`git clone` of `12d2675`, no `.env`, no `rentkart.db`) plus a seeded DB.
Commands used are listed per issue. Every root cause below was confirmed in code and/or by
running the app with Flask's test client.

---

## 1. "There is only a login page. No registration/profile flow exists."

### Reproduction
```
$ python -c "... create_app() ...; c.get('/register')"
/register -> 404
/signup   -> 404
/profile  -> 302 (login required; page exists but is read-only)

$ POST /login {"phone": "9876543210"}  (default config, no .env)
200 OK, flash: "SMS service is not configured"   # login itself is impossible
```

### Root cause
1. `routes/auth.py` only implements **phone → OTP** login. There is no `/signup`,
   no email/password, no password reset.
2. `models.User` has **no `email`, no `password_hash`, no role, no verification flags**
   (`models.py:10-70`). The only identity is `phone` (unique) plus `village_or_city`.
3. `config.OTP_MODE` defaults to `"sms"` and `SMS_API_KEY` defaults to `""`
   (`config.py:17-20`). With no `.env`, `_issue_otp()` returns
   `"SMS service is not configured"` (`routes/auth.py:68-72`), so **nobody can log in at
   all** on a fresh checkout.
4. `templates/profile.html` only *displays* the trust score; it has no form and there is
   no POST handler. `main.profile` (`routes/main.py:14-24`) is GET-only.
5. No rate limiting on `/login`, `/resend-otp`; sessions use Flask defaults
   (`HttpOnly` is on by default, but no `SameSite`, no lifetime, no secure-cookie switch).

### Fix
- Extended `User` (email/password/role/verification), bcrypt-hashed passwords,
  E.164 phone storage via `phonenumbers`, full `/signup`, `/forgot-password`,
  `/reset-password`, editable `/profile`, and auth endpoint rate limiting.
- Kept the legacy phone-OTP flow working (existing tests and existing users rely on it).

---

## 2. "Payment does not work."

### Reproduction
```
$ POST /items/1/checkout  (brand-new OTP user, no address)
flash: "Please choose a valid delivery address to continue."   # dead end

$ POST /items/1/checkout  (user with address) -> 302 /bookings/60/pay
$ GET  /bookings/60/pay   -> 200, mock gateway
$ POST /bookings/60/pay {"method":"upi","outcome":"success"} -> 302 confirmation
booking.status = requested, payment_status = paid, Payment(provider=mock)
```
The **mock** gateway works. The real path is broken:

### Root cause
1. **No provider is actually configured.** `PAYMENT_MODE` defaults to `"mock"`
   (`config.py:41`). There is no `.env`/`.env.example`, so a deployed instance silently
   runs a demo gateway. When `PAYMENT_MODE=razorpay` but keys are missing, the app
   silently **falls back to mock** (`routes/bookings.py:297-305`) — the user thinks they
   paid but no money moved.
2. **No webhook endpoint at all.** Payment success depends entirely on the browser
   callback (`pay.html` `handler` → form POST). If the payer closes the tab after paying,
   the booking stays `pending_payment` forever while money was captured — no
   reconciliation path exists.
3. **No gateway refund.** `_refund()` (`routes/bookings.py:65-79`) only flips DB flags;
   `utils/gateway.py` has `create_order` and `verify_signature` but no refund call.
4. **No idempotency store** for webhooks/callbacks; only the booking status check stops
   double payments. A retried webhook has nothing to dedupe against.
5. **No confirmation email/SMS** after payment; `utils/` has no notification module.
6. **A brand-new user has no `Address`**, and `checkout_submit` requires one
   (`routes/bookings.py:220-226`). The checkout page can create one inline, but the
   signup-created user is routed to a read-only profile, so there is no address in the
   normal flow.
7. **Cancellation records no actor/reason** (`routes/bookings.py:534-549`): `cancel()` only
   sets `status="cancelled"`. Trust scoring later cannot tell who cancelled or why.
8. Two parallel payment implementations (`/bookings/<id>/payment` demo page and
   `/bookings/<id>/pay`) create inconsistent states (`paid_demo` vs real `Payment` rows).

### Fix
- Env-driven Razorpay in TEST mode, server-created order, server-side signature
  verification, signed + idempotent webhook, refund helper, no silent mock fallback.
- Single payment path retained (`/pay`); deposit hold/refund recorded on each `Payment`.
- Cancellation now stores actor/reason/time and emits a trust-ready event.

---

## 3. "Rental items are not showing. Searching for 'dress' returns not found."

### Reproduction
```
$ ls *.db            -> nothing (rentkart.db is gitignored)  => empty database on deploy
$ GET /browse        -> 200 but no products (empty state)
$ python seed.py     -> "Seeded 5 users and 42 items." (73 rows with demo shops)
$ python -c "Item.query.filter(Item.title.ilike('%dress%')).all()"
[]                    # zero items contain "dress"
$ GET /browse?q=dress -> keyword map "dress" -> category=clothes, search=""
                         15 product links (5 clothes), NOT dresses
$ GET /browse?q=dres  -> "No items match your selected filters" (generic copy)
$ GET /browse?q=camera -> 9 links
```

### Root cause
1. **No database ships with the repo.** `SQLALCHEMY_DATABASE_URI` points at
   `rentkart.db`, which is gitignored (`config.py:13`, `.gitignore`). `create_app()` calls
   `db.create_all()` but seeds nothing (`app.py:126-208`), so a fresh deploy lists zero
   items. The seed script exists but is manual and undocumented in the README.
2. **No item contains the word "dress".** Seed data has lehengas, sherwanis, sarees,
   gowns — no dresses (verified: 0/73). Cameras/tents exist; **bikes do not exist as a
   category at all**.
3. **Search is title/description only**:
   `Item.title.ilike(pattern) | Item.description.ilike(pattern)` with a single
   `%whole query%` pattern (`routes/main.py:209-214`). So:
   - category, tags, attributes, shop name are ignored;
   - multi-word queries ("party dress") require the exact phrase;
   - partial words only work from the left ("dres" works, "ress" does not).
   `ilike` itself is case-insensitive on SQLite, so case was not the failure.
4. **The keyword map hijacks real search terms.** `KEYWORD_MAP["dress"] = "clothes"`
   (`config.py:566`). When it matches, `search` is thrown away
   (`routes/main.py:174-179`), so "dress" shows *all* clothes instead of dresses.
5. **Listings are hidden by the plan cap.** Browse only keeps the first
   `max_items` items per owner (free = 5; `utils/plans.py`, `routes/main.py:251-265`).
   Seed owner Ramesh (free) has 11 items, Lakshmi (Pro, 25) has 30 → 11 seeded items never
   appear anywhere. There is no "hidden because of plan" message.
6. **The clothes page shows only the first 12 cards per tab** (`templates/clothes.html:112`)
   and defaults to the Women tab; the remainder is behind a client-side "show more".
7. **Owner tooling is incomplete:** there is no edit route (only `add` and
   `toggle_availability` in `routes/items.py`), no gallery, and the empty state is generic
   ("No items match your selected filters") without the searched term or category links.

### Fix
- Search across title/description/category label/tags/attributes/shop, tokenised with
  prefix + fuzzy matching; keyword map only pre-selects a category and keeps the text.
- Added `tags` + `images` to `Item`; seeded 36 new items (dresses, bikes, cameras,
  tents, tools, electronics) and upgraded demo owners so all listings are visible.
- Added `bikes` category, location filter, more sort modes, a search-aware empty state,
  gallery on item detail, and owner edit/pause with image upload.

---

## Cross-cutting gaps found while reproducing

- `templates/base.html` has **no "Sign up" link** and no `Country` context.
- `utils/otp.py` issues **4-digit** codes and `OTP_MAX_SENDS=3 / 10 minutes`; the target
  policy is 6 digits, 5 sends/hour, 5 attempts, 15-minute lock.
- OTP state lives only in the **session**: a new browser/device cannot finish a flow, and
  the "change number" flow cannot verify a different number before updating the account.
- There is no per-user event/audit table, so a later Trust Score system cannot query
  "logins, payments, cancellations, returns" per user.
- `PAYMENT_MODE`, `Razorpay` keys, `UPI_ID`, `SMS_*` are read from env but no
  `.env.example` documents them.

All of the above are addressed by the changes in this branch; see `README.md` for setup and
`test_auth_signup.py`, `test_otp_flows.py`, `test_search.py` and `test_payment_flows.py`
for regression coverage.

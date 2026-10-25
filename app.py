"""Flask application factory for RentKart."""
import os
from flask import Flask
from flask_login import LoginManager
from models import db, User
import models_revenue  # noqa: F401  (registers additive revenue tables)
import config


def _seed_demo_if_empty(app):
    """Seed the demo catalogue once, and only when the database has no rows.

    Called on startup (Render sets ``RENDER=true``, so ``AUTO_SEED`` defaults on
    there). A populated database - the normal case after the first boot - is
    never touched, so restarts and redeploys cannot overwrite existing users,
    listings or bookings. The test suite always skips this.
    """
    if not app.config.get("AUTO_SEED") or app.config.get("TESTING"):
        return
    try:
        from models import Item, User
        if User.query.first() is not None or Item.query.first() is not None:
            app.logger.info("Database already has data - demo seeding skipped.")
            return
        try:
            from seed import seed as run_seed
        except ImportError:
            # `python seed.py` is still importing this module; it seeds itself.
            return
        app.logger.info("Empty database detected - seeding demo data once.")
        run_seed(only_if_empty=True)
    except Exception:
        db.session.rollback()
        app.logger.warning("Demo seeding failed; starting without demo data.",
                           exc_info=True)


def create_app(test_config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Load default config
    app.config.from_object(config)

    # Override with test config if provided
    if test_config:
        app.config.update(test_config)

    # Revenue features stay off for the legacy test suite unless a test opts in
    # explicitly (the development/production default remains ON).
    if test_config and test_config.get("TESTING") and "REVENUE_ENABLED" not in test_config:
        app.config["REVENUE_ENABLED"] = False

    # Ensure upload dir exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Tests keep media files beside their temporary upload folder so they never
    # write into the repository's static/media directory.
    if test_config and "UPLOAD_FOLDER" in test_config and "MEDIA_FOLDER" not in test_config:
        app.config["MEDIA_FOLDER"] = os.path.join(
            os.path.dirname(app.config["UPLOAD_FOLDER"]), "media")
    os.makedirs(app.config["MEDIA_FOLDER"], exist_ok=True)

    # Init extensions
    db.init_app(app)
    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from routes.auth import auth_bp
    from routes.items import items_bp
    from routes.main import main_bp
    from routes.bookings import bookings_bp
    from routes.shop import shop_bp
    from routes.subscriptions import subscriptions_bp
    from routes.feedback import feedback_bp
    from routes.admin import admin_bp
    from routes.addresses import addresses_bp
    from routes.trustshield import ts_bp
    from routes.bulk import bulk_bp
    from routes.art import art_bp
    from routes.revenue import revenue_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(subscriptions_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(addresses_bp)
    app.register_blueprint(ts_bp)
    app.register_blueprint(bulk_bp)
    app.register_blueprint(art_bp)
    app.register_blueprint(revenue_bp)

    from translations import t, SUPPORTED_LANGUAGES
    from utils.trending import get_book_genre_info, is_book_trending
    from utils.logo import shop_logo_url, shop_initials, item_image_static_path
    from utils.illustrations import (
        item_picture, ensure_illustrations, clothes_tinted_svg, tab_tile_svg,
    )
    from utils.booking import effective_price
    from utils.filters import rating_summary
    from flask import url_for

    illus_dir = os.path.join(app.root_path, "static", "illustrations")
    if not os.path.isdir(illus_dir) or not os.listdir(illus_dir):
        ensure_illustrations()

    def item_image_url(item):
        pic = item_picture(item)
        return pic.get("src") or None

    app.jinja_env.globals["t"] = t
    app.jinja_env.globals["SUPPORTED_LANGUAGES"] = SUPPORTED_LANGUAGES
    app.jinja_env.globals["get_book_genre_info"] = get_book_genre_info
    app.jinja_env.globals["is_book_trending"] = is_book_trending
    app.jinja_env.globals["shop_logo_url"] = shop_logo_url
    app.jinja_env.globals["shop_initials"] = shop_initials
    app.jinja_env.globals["item_image_url"] = item_image_url
    app.jinja_env.globals["item_picture"] = item_picture
    app.jinja_env.globals["effective_price"] = effective_price
    app.jinja_env.globals["rating_summary"] = rating_summary
    app.jinja_env.globals["clothes_tinted_svg"] = clothes_tinted_svg
    app.jinja_env.globals["tab_tile_svg"] = tab_tile_svg

    # Additive revenue helpers used by the small template hooks.
    from utils.revenue import (is_featured, featured_days_left, sponsored_banner,
                               owner_pro_active, paise_inr)
    app.jinja_env.globals["is_featured"] = is_featured
    app.jinja_env.globals["featured_days_left"] = featured_days_left
    app.jinja_env.globals["sponsored_banner"] = sponsored_banner
    app.jinja_env.globals["owner_pro_active"] = owner_pro_active
    app.jinja_env.filters["paise_inr"] = paise_inr

    @app.context_processor
    def inject_global_data():
        from flask_login import current_user
        from models import Feedback
        from flask import session
        from utils.revenue import features as revenue_features, get_settings as revenue_settings
        has_unseen = False
        if current_user.is_authenticated:
            has_unseen = Feedback.query.filter_by(user_id=current_user.id, reply_seen=False)\
                .filter(Feedback.admin_reply.isnot(None)).count() > 0
        return {
            "has_unseen_feedback": has_unseen,
            "PLANS": config.PLANS,
            "revenue_features": revenue_features(),
            "revenue_settings": revenue_settings(),
            "t": t,
            "current_lang": session.get("lang", "en"),
            "SUPPORTED_LANGUAGES": SUPPORTED_LANGUAGES,
        }

    # Register Jinja money-format filter
    from utils.money import inr as _inr_filter
    app.jinja_env.filters["inr"] = _inr_filter

    # Error handlers for 403, 404, 500
    from flask import render_template

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template("500.html"), 500

    # Create tables & safe SQLite column migration for Phase 5, Phase 6, Phase 7
    with app.app_context():
        # Copy the SQLite file before the additive revenue tables exist (once).
        from utils.revenue import backup_db_once
        backup_db_once(app)
        db.create_all()
        # Demo data only on a brand-new database, never on a redeploy.
        _seed_demo_if_empty(app)
        # The ALTER TABLE statements below are SQLite-only legacy upgrades
        # (unquoted `user`, partial unique indexes). Postgres/MySQL already got
        # the full schema from create_all, so they skip the rest of this block.
        if db.engine.dialect.name != "sqlite":
            return app
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            table_names = inspector.get_table_names()
            with db.engine.connect() as conn:
                if "user" in table_names:
                    u_cols = [c["name"] for c in inspector.get_columns("user")]
                    if "shop_description" not in u_cols:
                        conn.execute(text("ALTER TABLE user ADD COLUMN shop_description TEXT"))
                    if "shop_slug" not in u_cols:
                        conn.execute(text("ALTER TABLE user ADD COLUMN shop_slug VARCHAR(120)"))
                    if "is_admin" not in u_cols:
                        conn.execute(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
                    if "shop_logo" not in u_cols:
                        conn.execute(text("ALTER TABLE user ADD COLUMN shop_logo VARCHAR(300)"))
                    if "shop_theme_color" not in u_cols:
                        conn.execute(text("ALTER TABLE user ADD COLUMN shop_theme_color VARCHAR(50)"))
                    if "shop_address" not in u_cols:
                        conn.execute(text("ALTER TABLE user ADD COLUMN shop_address VARCHAR(300)"))
                    if "shop_hours" not in u_cols:
                        conn.execute(text("ALTER TABLE user ADD COLUMN shop_hours VARCHAR(120)"))
                    if "shop_phone" not in u_cols:
                        conn.execute(text("ALTER TABLE user ADD COLUMN shop_phone VARCHAR(20)"))
                    if "shop_category_tags" not in u_cols:
                        conn.execute(text("ALTER TABLE user ADD COLUMN shop_category_tags VARCHAR(300)"))
                    # Section A: email/password login, roles and verification flags
                    for col, typ in (
                        ("email", "VARCHAR(190)"), ("password_hash", "VARCHAR(255)"),
                        ("role", "VARCHAR(10) DEFAULT 'both'"),
                        ("phone_e164", "VARCHAR(20)"),
                        ("phone_verified", "BOOLEAN DEFAULT 0"),
                        ("alternate_phone", "VARCHAR(20)"),
                        ("alternate_phone_verified", "BOOLEAN DEFAULT 0"),
                        ("email_verified", "BOOLEAN DEFAULT 0"),
                        ("address_verified", "BOOLEAN DEFAULT 0"),
                        ("id_verified", "BOOLEAN DEFAULT 0"),
                        ("terms_accepted_at", "DATETIME"),
                        ("last_login_at", "DATETIME"),
                    ):
                        if col not in u_cols:
                            conn.execute(text(f"ALTER TABLE user ADD COLUMN {col} {typ}"))
                    # SQLite cannot add a UNIQUE column to an existing table, so
                    # enforce uniqueness with indexes instead.
                    conn.execute(text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_email_unique "
                        "ON user (email) WHERE email IS NOT NULL"))
                    conn.execute(text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_phone_e164_unique "
                        "ON user (phone_e164) WHERE phone_e164 IS NOT NULL"))
                if "address" in table_names:
                    a_cols = [c["name"] for c in inspector.get_columns("address")]
                    if "country" not in a_cols:
                        conn.execute(text("ALTER TABLE address ADD COLUMN country VARCHAR(80) DEFAULT 'India'"))
                if "item" in table_names:
                    i_cols = [c["name"] for c in inspector.get_columns("item")]
                    if "purchase_price" not in i_cols:
                        conn.execute(text("ALTER TABLE item ADD COLUMN purchase_price INTEGER"))
                    if "delivery_available" not in i_cols:
                        conn.execute(text("ALTER TABLE item ADD COLUMN delivery_available BOOLEAN"))
                    if "delivery_charge" not in i_cols:
                        conn.execute(text("ALTER TABLE item ADD COLUMN delivery_charge FLOAT DEFAULT 0"))
                    if "cod_available" not in i_cols:
                        conn.execute(text("ALTER TABLE item ADD COLUMN cod_available BOOLEAN DEFAULT 1"))
                    if "discount_percent" not in i_cols:
                        conn.execute(text("ALTER TABLE item ADD COLUMN discount_percent INTEGER DEFAULT 0"))
                    # Section C: gallery + searchable tags
                    if "images" not in i_cols:
                        conn.execute(text("ALTER TABLE item ADD COLUMN images TEXT"))
                    if "tags" not in i_cols:
                        conn.execute(text("ALTER TABLE item ADD COLUMN tags TEXT"))
                if "booking" in table_names:
                    b_cols = [c["name"] for c in inspector.get_columns("booking")]
                    if "commission_percent" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN commission_percent FLOAT DEFAULT 10.0"))
                    if "delivery_method" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN delivery_method VARCHAR(10) DEFAULT 'pickup'"))
                    if "delivery_charge" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN delivery_charge FLOAT DEFAULT 0"))
                    if "platform_fee" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN platform_fee FLOAT DEFAULT 0"))
                    if "tax_amount" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN tax_amount FLOAT DEFAULT 0"))
                    if "order_id" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN order_id VARCHAR(40)"))
                    if "payment_expires_at" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN payment_expires_at DATETIME"))
                    if "razorpay_order_id" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN razorpay_order_id VARCHAR(120)"))
                    if "price_per_day" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN price_per_day FLOAT"))
                    if "price_original" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN price_original FLOAT"))
                    # TrustShield: opt-in damage-protection flag (additive)
                    if "trustshield" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN trustshield BOOLEAN DEFAULT 0"))
                    # Section D: cancellation audit trail (who / why / when)
                    if "cancelled_by" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN cancelled_by INTEGER"))
                    if "cancel_reason" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN cancel_reason VARCHAR(300)"))
                    if "cancelled_at" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN cancelled_at DATETIME"))
                    if "completed_at" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN completed_at DATETIME"))
                    # Stage 2: shipping address snapshot columns
                    for col, typ in (
                        ("address_id", "INTEGER"), ("ship_full_name", "VARCHAR(120)"),
                        ("ship_phone", "VARCHAR(15)"), ("ship_house_no", "VARCHAR(120)"),
                        ("ship_building", "VARCHAR(120)"), ("ship_street", "VARCHAR(120)"),
                        ("ship_landmark", "VARCHAR(120)"), ("ship_city", "VARCHAR(120)"),
                        ("ship_district", "VARCHAR(120)"), ("ship_state", "VARCHAR(120)"),
                        ("ship_pincode", "VARCHAR(6)"),
                    ):
                        if col not in b_cols:
                            conn.execute(text(f"ALTER TABLE booking ADD COLUMN {col} {typ}"))
                if "return_record" in table_names:
                    r_cols = [c["name"] for c in inspector.get_columns("return_record")]
                    if "platform_fee" not in r_cols:
                        conn.execute(text("ALTER TABLE return_record ADD COLUMN platform_fee FLOAT DEFAULT 0.0"))
                    if "owner_earning" not in r_cols:
                        conn.execute(text("ALTER TABLE return_record ADD COLUMN owner_earning FLOAT DEFAULT 0.0"))
                if "payment" in table_names:
                    p_cols = [c["name"] for c in inspector.get_columns("payment")]
                    for col, typ in (
                        ("kind", "VARCHAR(20) DEFAULT 'payment'"),
                        ("gateway_order_id", "VARCHAR(120)"),
                        ("signature_verified", "BOOLEAN DEFAULT 0"),
                        ("failure_code", "VARCHAR(60)"),
                        ("refunded_amount", "FLOAT DEFAULT 0"),
                        ("refund_id", "VARCHAR(120)"),
                        ("refunded_at", "DATETIME"),
                    ):
                        if col not in p_cols:
                            conn.execute(text(f"ALTER TABLE payment ADD COLUMN {col} {typ}"))
                conn.commit()
        except Exception:
            pass

    return app


# Expose module-level app
app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")
    app.run(host=host, port=port, debug=debug)


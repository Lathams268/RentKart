"""Flask application factory for RentKart."""
import os
from flask import Flask
from flask_login import LoginManager
from models import db, User
import config


def create_app(test_config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Load default config
    app.config.from_object(config)

    # Override with test config if provided
    if test_config:
        app.config.update(test_config)

    # Ensure upload dir exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

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

    app.register_blueprint(auth_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(subscriptions_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(admin_bp)

    from translations import t, SUPPORTED_LANGUAGES
    from utils.trending import get_book_genre_info, is_book_trending
    app.jinja_env.globals["t"] = t
    app.jinja_env.globals["SUPPORTED_LANGUAGES"] = SUPPORTED_LANGUAGES
    app.jinja_env.globals["get_book_genre_info"] = get_book_genre_info
    app.jinja_env.globals["is_book_trending"] = is_book_trending

    @app.context_processor
    def inject_global_data():
        from flask_login import current_user
        from models import Feedback
        from flask import session
        has_unseen = False
        if current_user.is_authenticated:
            has_unseen = Feedback.query.filter_by(user_id=current_user.id, reply_seen=False)\
                .filter(Feedback.admin_reply.isnot(None)).count() > 0
        return {
            "has_unseen_feedback": has_unseen,
            "PLANS": config.PLANS,
            "t": t,
            "current_lang": session.get("lang", "en"),
            "SUPPORTED_LANGUAGES": SUPPORTED_LANGUAGES,
        }

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
        db.create_all()
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
                if "item" in table_names:
                    i_cols = [c["name"] for c in inspector.get_columns("item")]
                    if "purchase_price" not in i_cols:
                        conn.execute(text("ALTER TABLE item ADD COLUMN purchase_price INTEGER"))
                if "booking" in table_names:
                    b_cols = [c["name"] for c in inspector.get_columns("booking")]
                    if "commission_percent" not in b_cols:
                        conn.execute(text("ALTER TABLE booking ADD COLUMN commission_percent FLOAT DEFAULT 10.0"))
                if "return_record" in table_names:
                    r_cols = [c["name"] for c in inspector.get_columns("return_record")]
                    if "platform_fee" not in r_cols:
                        conn.execute(text("ALTER TABLE return_record ADD COLUMN platform_fee FLOAT DEFAULT 0.0"))
                    if "owner_earning" not in r_cols:
                        conn.execute(text("ALTER TABLE return_record ADD COLUMN owner_earning FLOAT DEFAULT 0.0"))
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


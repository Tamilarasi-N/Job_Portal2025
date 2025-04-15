# --- app/__init__.py ---

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime
import cloudinary
import cloudinary.utils
# --- V V V --- Import Werkzeug for password hashing --- V V V ---
from werkzeug.security import generate_password_hash
# --- ^ ^ ^ --- End Import --- ^ ^ ^ ---


# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
serializer = None

# Configure logging formatter
log_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')

def create_app(config_class=None):
    app = Flask(__name__, instance_relative_config=True)

    # Default Upload Folder Path (for local fallback if UPLOAD_FOLDER env var not set)
    default_upload_folder = os.path.join(app.instance_path, 'uploads', 'resumes')

    # Load Configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'change_this_dev_secret_key'),
        SECURITY_PASSWORD_SALT=os.environ.get('SECURITY_PASSWORD_SALT', 'change_this_dev_salt'),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', f"sqlite:///{os.path.join(app.instance_path, 'site.db')}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', default_upload_folder), # For Cloudinary, this isn't strictly used for saving but might be referenced
        MAX_CONTENT_LENGTH = 5 * 1024 * 1024,
        MAIL_SERVER=os.environ.get('MAIL_SERVER', 'smtp.example.com'),
        MAIL_PORT=int(os.environ.get('MAIL_PORT', 587)),
        MAIL_USE_TLS=os.environ.get('MAIL_USE_TLS', 'True').lower() in ['true', '1', 't'],
        MAIL_USE_SSL=os.environ.get('MAIL_USE_SSL', 'False').lower() in ['true', '1', 't'],
        MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
        MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@example.com'),
    )

    # Ensure Instance Folder Exists
    try: os.makedirs(app.instance_path, exist_ok=True)
    except OSError as e: app.logger.error(f"Error creating instance dir {app.instance_path}: {e}")

    # Configure Cloudinary SDK
    try: # Cloudinary Config Code (unchanged)
        cloudinary.config(cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'), api_key = os.environ.get('CLOUDINARY_API_KEY'), api_secret = os.environ.get('CLOUDINARY_API_SECRET'), secure=True)
        if not all([cloudinary.config().cloud_name, cloudinary.config().api_key, cloudinary.config().api_secret]): app.logger.warning("CLOUDINARY env vars not fully configured.")
        else: app.logger.info("Cloudinary SDK configured.")
    except Exception as e: app.logger.error(f"Cloudinary config error: {e}")

    # Initialize Flask Extensions
    try: db.init_app(app); login_manager.init_app(app); mail.init_app(app)
    except Exception as e: app.logger.error(f"Error initializing Flask extensions: {e}")

    # Initialize Serializer & Check Keys/Salts
    global serializer; serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    if app.config['SECRET_KEY'] == 'change_this_dev_secret_key': app.logger.warning("Insecure SECRET_KEY.")
    if app.config['SECURITY_PASSWORD_SALT'] == 'change_this_dev_salt': app.logger.warning("Insecure SALT.")

    # Configure Flask-Login
    login_manager.login_view = 'auth.login'; login_manager.login_message_category = 'info'; login_manager.login_message = "Please log in."
    @login_manager.user_loader
    def load_user(user_id): # Corrected multi-line version
        from .models import User
        try: return User.query.get(int(user_id))
        except ValueError: current_app.logger.error(f"Invalid user_id format: {user_id}"); return None
        except Exception as e: current_app.logger.error(f"Error loading user {user_id}: {e}"); return None

    # Context Processors
    @app.context_processor
    def inject_now(): return {'now': datetime.utcnow}
    @app.context_processor
    def utility_processor(): # Cloudinary URL helper (unchanged)
        def get_cloudinary_raw_url(public_id):
            if not public_id: return None
            try:
                if cloudinary.config().cloud_name: url_tuple = cloudinary.utils.cloudinary_url(public_id, resource_type="raw", secure=True); return url_tuple[0] if url_tuple else None
                else: current_app.logger.warning("Cloudinary not configured."); return None
            except Exception as e: current_app.logger.error(f"Error generating Cloudinary URL for {public_id}: {e}"); return None
        return dict(get_cloudinary_raw_url=get_cloudinary_raw_url)

    # Register Blueprints
    try:
        from .views import main_bp, auth_bp, jobs_bp, employers_bp, admin_bp
        app.register_blueprint(main_bp); app.register_blueprint(auth_bp, url_prefix='/auth'); app.register_blueprint(jobs_bp, url_prefix='/jobs'); app.register_blueprint(employers_bp, url_prefix='/employer'); app.register_blueprint(admin_bp, url_prefix='/admin')
        app.logger.info("Blueprints registered.")
    except Exception as e: app.logger.error(f"Error registering blueprints: {e}")

    # Setup Logging (Unchanged)
    log_dir = 'logs'; # ... (rest of logging setup) ...
    log_file_path = os.path.join(log_dir, 'job_portal.log'); log_level = os.environ.get('LOG_LEVEL', 'INFO').upper(); logging_level = getattr(logging, log_level, logging.INFO)
    if not app.debug and not app.testing:
        if not os.path.exists(log_dir):
            try: os.mkdir(log_dir)
            except OSError as e: app.logger.error(f"Error creating logs directory '{log_dir}': {e}")
        try:
            file_handler = RotatingFileHandler(log_file_path, maxBytes=10240, backupCount=10); file_handler.setFormatter(log_formatter); file_handler.setLevel(logging_level)
            app.logger.addHandler(file_handler); app.logger.setLevel(logging_level)
            app.logger.info(f'Logging configured: {log_file_path}')
        except Exception as e: app.logger.error(f"Failed file logging: {e}")
    else: app.logger.setLevel(logging_level); app.logger.info("Debug/Testing mode: File logging skipped.")


    # --- Create Database Tables & Default Admin ---
    with app.app_context():
        try:
            db.create_all() # Create tables if they don't exist
            app.logger.info("DB tables checked/created (if needed).")

            # --- V V V --- Add Default Admin Creation Logic --- V V V ---
            from .models import User # Import User model here
            # Check if an admin user already exists
            if not User.query.filter_by(role='admin').first():
                app.logger.info("No admin user found. Attempting to create default admin...")
                # Get default admin credentials from environment variables
                default_username = os.environ.get('DEFAULT_ADMIN_USERNAME', 'admin')
                default_email = os.environ.get('DEFAULT_ADMIN_EMAIL')
                default_password = os.environ.get('DEFAULT_ADMIN_PASSWORD')

                if not default_email:
                    app.logger.error("DEFAULT_ADMIN_EMAIL environment variable not set. Cannot create default admin.")
                elif not default_password:
                    app.logger.error("DEFAULT_ADMIN_PASSWORD environment variable not set. Cannot create default admin.")
                else:
                    try:
                        # Check if this specific email/username already exists (e.g., as non-admin)
                        existing = User.query.filter((User.username == default_username) | (User.email == default_email)).first()
                        if not existing:
                            admin_user = User(
                                username=default_username,
                                email=default_email,
                                role='admin',
                                is_verified=True # Assume default admin is verified
                            )
                            admin_user.set_password(default_password) # Hash password
                            db.session.add(admin_user)
                            db.session.commit()
                            app.logger.info(f"Default admin user '{default_username}' created successfully.")
                        else:
                            app.logger.warning(f"User with username '{default_username}' or email '{default_email}' already exists. Default admin not created.")
                    except Exception as admin_create_e:
                         db.session.rollback()
                         app.logger.error(f"Failed to create default admin user: {admin_create_e}")
            else:
                 app.logger.info("Admin user already exists.")
            # --- ^ ^ ^ --- End Default Admin Creation Logic --- ^ ^ ^ ---

        except Exception as e:
            app.logger.error(f"Error during initial DB setup (create_all/admin check): {e}")
            app.logger.error(f"Check Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

    # Final Checks
    if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'): app.logger.warning("MAIL config missing. Email disabled.")

    app.logger.info("Flask app creation finished.")
    return app

# --- End of __init__.py ---
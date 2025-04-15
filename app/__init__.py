# --- app/__init__.py ---

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
serializer = None

# Configure logging formatter (handler setup inside create_app)
log_formatter = logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
)

def create_app(config_class=None):
    """ Create and configure the Flask application. """
    app = Flask(__name__, instance_relative_config=True)

    # --- Determine Base Path for Instance/Uploads ---
    instance_base_path = os.environ.get('RENDER_DISK_MOUNT_PATH', app.instance_path)
    upload_folder_path = os.path.join(instance_base_path, 'uploads', 'resumes')

    # --- Load Configuration ---
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'change_this_dev_secret_key'),
        SECURITY_PASSWORD_SALT=os.environ.get('SECURITY_PASSWORD_SALT', 'change_this_dev_salt'),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'DATABASE_URL', # For Render PostgreSQL
            f"sqlite:///{os.path.join(app.instance_path, 'site.db')}" # Local SQLite
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER = upload_folder_path, # Use calculated path
        MAX_CONTENT_LENGTH = 5 * 1024 * 1024,  # 5 MB limit
        MAIL_SERVER=os.environ.get('MAIL_SERVER', 'smtp.example.com'),
        MAIL_PORT=int(os.environ.get('MAIL_PORT', 587)),
        MAIL_USE_TLS=os.environ.get('MAIL_USE_TLS', 'True').lower() in ['true', '1', 't'],
        MAIL_USE_SSL=os.environ.get('MAIL_USE_SSL', 'False').lower() in ['true', '1', 't'],
        MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
        MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@example.com'),
    )

    # --- Ensure Instance and Upload Folders Exist ---
    # Create default instance folder first if it doesn't exist (for local SQLite etc.)
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError as e:
        app.logger.error(f"Error creating instance directory {app.instance_path}: {e}")

    # Create the potentially nested UPLOAD_FOLDER path
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        app.logger.info(f"Ensured upload directory exists: {app.config['UPLOAD_FOLDER']}")
        # Optional: Check writability here if PermissionError persists after verifying Env Var
        # if not os.access(app.config['UPLOAD_FOLDER'], os.W_OK):
        #    app.logger.error(f"Upload directory {app.config['UPLOAD_FOLDER']} NOT WRITABLE.")
    except PermissionError as pe:
         app.logger.error(f"PERMISSION DENIED creating/accessing upload directory {app.config['UPLOAD_FOLDER']}. Check Render Disk Mount Path env var ('{os.environ.get('RENDER_DISK_MOUNT_PATH')}') and disk permissions. Error: {pe}")
    except OSError as e:
        app.logger.error(f"OS error creating upload directory {app.config['UPLOAD_FOLDER']}: {e}")
    except Exception as e:
         app.logger.error(f"Unexpected error checking/creating upload directory {app.config['UPLOAD_FOLDER']}: {e}")

    # --- Initialize Flask Extensions ---
    try:
        db.init_app(app)
        login_manager.init_app(app)
        mail.init_app(app)
    except Exception as e:
        app.logger.error(f"Error initializing Flask extensions: {e}")

    # --- Initialize Serializer ---
    global serializer
    # Add checks for insecure default keys/salts
    if not app.config.get('SECRET_KEY') or app.config['SECRET_KEY'] == 'change_this_dev_secret_key': app.logger.warning("WARNING: SECRET_KEY is insecure.")
    if not app.config.get('SECURITY_PASSWORD_SALT') or app.config['SECURITY_PASSWORD_SALT'] == 'change_this_dev_salt': app.logger.warning("WARNING: SECURITY_PASSWORD_SALT is insecure.")
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

    # --- Configure Flask-Login ---
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    login_manager.login_message = "Please log in to access this page."

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        try: return User.query.get(int(user_id))
        except Exception as e: app.logger.error(f"Error loading user {user_id}: {e}"); return None

    # --- Context Processor ---
    @app.context_processor
    def inject_now(): return {'now': datetime.utcnow}

    # --- Register Blueprints ---
    try:
        from .views import main_bp, auth_bp, jobs_bp, employers_bp, admin_bp
        app.register_blueprint(main_bp)
        app.register_blueprint(auth_bp, url_prefix='/auth')
        app.register_blueprint(jobs_bp, url_prefix='/jobs')
        app.register_blueprint(employers_bp, url_prefix='/employer')
        app.register_blueprint(admin_bp, url_prefix='/admin')
        app.logger.info("Blueprints registered.")
    except Exception as e: app.logger.error(f"Error registering blueprints: {e}")

    # --- Setup Logging ---
    log_dir = 'logs' # Log locally, Render handles production logging streams
    log_file_path = os.path.join(log_dir, 'job_portal.log')
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    logging_level = getattr(logging, log_level, logging.INFO)

    if not app.debug and not app.testing: # Only configure file logging if not in debug/testing
        if not os.path.exists(log_dir):
            try: os.mkdir(log_dir)
            except OSError as e: app.logger.error(f"Error creating logs directory '{log_dir}': {e}")

        try:
            file_handler = RotatingFileHandler(log_file_path, maxBytes=10240, backupCount=10)
            file_handler.setFormatter(log_formatter)
            file_handler.setLevel(logging_level)
            # app.logger.removeHandler(default_handler) # Optional: remove default handler
            app.logger.addHandler(file_handler)
            app.logger.setLevel(logging_level) # Set logger level too
            app.logger.info(f'Job Portal logging configured to file: {log_file_path}')
        except Exception as e: app.logger.error(f"Failed to configure file logging: {e}")
    else:
        # Configure basic stream logging for debug mode if needed
        # logging.basicConfig(level=logging_level, format='%(asctime)s %(levelname)s: %(message)s')
        app.logger.setLevel(logging_level)
        app.logger.info("Running in Debug/Testing mode, file logging skipped/basic logging used.")


    # --- Create Database Tables ---
    with app.app_context():
        try:
            # from . import models # Models should be loaded via views import usually
            db.create_all()
            app.logger.info("Database tables checked/created (if needed).")
        except Exception as e:
            app.logger.error(f"Error during db.create_all(): {e}")
            app.logger.error(f"Check Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

    # --- Final Checks ---
    if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
       app.logger.warning("MAIL_USERNAME or MAIL_PASSWORD not configured. Email functionality disabled.")

    app.logger.info("Flask app creation finished.")
    return app

# --- End of __init__.py ---
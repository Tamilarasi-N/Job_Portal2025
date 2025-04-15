# --- app/__init__.py ---

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime # For the 'now' context processor

# Initialize extensions (outside the factory function)
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
serializer = None # Will be initialized in create_app

# Configure logging (can be set up here or inside create_app)
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
# Log file setup improved later in create_app

def create_app(config_class=None):
    """
    Factory function to create and configure the Flask application.
    """
    app = Flask(__name__, instance_relative_config=True) # Use instance folder

    # --- Determine Base Path for Instance/Uploads ---
    # Use Render's disk mount path if available, otherwise use default instance path
    # Set RENDER_DISK_MOUNT_PATH env var on Render (e.g., /var/data/render/instance)
    instance_base_path = os.environ.get('RENDER_DISK_MOUNT_PATH', app.instance_path)
    upload_folder_path = os.path.join(instance_base_path, 'uploads', 'resumes')

    # --- Load Configuration ---
    app.config.from_mapping(
        # Secrets (Should be set via .env locally or Env Vars on Render)
        SECRET_KEY=os.environ.get('SECRET_KEY', 'change_this_dev_secret_key'),
        SECURITY_PASSWORD_SALT=os.environ.get('SECURITY_PASSWORD_SALT', 'change_this_dev_salt'),

        # --- V V V --- Modified Database and Upload Config --- V V V ---
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'DATABASE_URL', # Render provides this for PostgreSQL
            f"sqlite:///{os.path.join(app.instance_path, 'site.db')}" # Local SQLite fallback
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER = upload_folder_path, # Use calculated path
        MAX_CONTENT_LENGTH = 5 * 1024 * 1024,  # 5 MB global upload limit
        # --- ^ ^ ^ --- End Modified Config --- ^ ^ ^ ---

        # Email Configuration (Reads from .env / Env Vars)
        MAIL_SERVER=os.environ.get('MAIL_SERVER', 'smtp.example.com'),
        MAIL_PORT=int(os.environ.get('MAIL_PORT', 587)),
        MAIL_USE_TLS=os.environ.get('MAIL_USE_TLS', 'True').lower() in ['true', '1', 't'],
        MAIL_USE_SSL=os.environ.get('MAIL_USE_SSL', 'False').lower() in ['true', '1', 't'],
        MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
        MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@example.com'),
    )

    # Ensure instance folder exists (especially important if using default path locally)
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError as e:
        app.logger.error(f"Error creating instance directory {app.instance_path}: {e}")

    # --- Ensure UPLOAD_FOLDER exists ---
    # This now uses the potentially customized instance_base_path
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        try:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) # Create directory including intermediates
            app.logger.info(f"Created upload directory: {app.config['UPLOAD_FOLDER']}")
        except OSError as e:
            app.logger.error(f"Error creating upload directory {app.config['UPLOAD_FOLDER']}: {e}")

    # --- Initialize Flask Extensions with the App ---
    try:
        db.init_app(app)
        login_manager.init_app(app)
        mail.init_app(app)
    except Exception as e:
        app.logger.error(f"Error initializing Flask extensions: {e}")
        # Depending on severity, you might want to raise the exception
        # raise e

    # Initialize the serializer
    global serializer
    if not app.config.get('SECRET_KEY') or app.config['SECRET_KEY'] == 'change_this_dev_secret_key':
       app.logger.warning("WARNING: SECRET_KEY is insecure. Set via .env or environment variable.")
    if not app.config.get('SECURITY_PASSWORD_SALT') or app.config['SECURITY_PASSWORD_SALT'] == 'change_this_dev_salt':
        app.logger.warning("WARNING: SECURITY_PASSWORD_SALT is insecure. Set via .env or environment variable.")
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

    # --- Configure Flask-Login ---
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    login_manager.login_message = "Please log in to access this page."

    @login_manager.user_loader
    def load_user(user_id):
        # Import here to avoid potential circular dependencies
        from .models import User
        try:
            return User.query.get(int(user_id))
        except Exception as e:
            app.logger.error(f"Error loading user {user_id}: {e}")
            return None

    # --- Context Processor ---
    @app.context_processor
    def inject_now():
        # Provide datetime.utcnow to all templates as 'now'
        return {'now': datetime.utcnow}

    # --- Register Blueprints ---
    try:
        from .views import main_bp, auth_bp, jobs_bp, employers_bp, admin_bp
        app.register_blueprint(main_bp)
        app.register_blueprint(auth_bp, url_prefix='/auth')
        app.register_blueprint(jobs_bp, url_prefix='/jobs')
        app.register_blueprint(employers_bp, url_prefix='/employer')
        app.register_blueprint(admin_bp, url_prefix='/admin')
        app.logger.info("Blueprints registered successfully.")
    except Exception as e:
        app.logger.error(f"Error registering blueprints: {e}")

    # --- Setup Logging ---
    if not app.debug and not app.testing:
        log_dir = 'logs' # Define log directory name
        if not os.path.exists(log_dir):
           try: os.mkdir(log_dir)
           except OSError as e: app.logger.error(f"Error creating logs directory '{log_dir}': {e}")

        log_file_path = os.path.join(log_dir, 'job_portal.log')
        try:
            # Use RotatingFileHandler for better log management in production
            file_handler = RotatingFileHandler(log_file_path, maxBytes=10240, backupCount=10)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
            # Set level based on config or default to INFO
            log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
            file_handler.setLevel(getattr(logging, log_level, logging.INFO))
            # Remove default Flask handler before adding ours? Optional.
            # app.logger.removeHandler(default_handler)
            app.logger.addHandler(file_handler)
            app.logger.setLevel(getattr(logging, log_level, logging.INFO))
            app.logger.info('Job Portal logging configured.')
        except Exception as e:
            app.logger.error(f"Failed to configure file logging to {log_file_path}: {e}")


    # --- Create Database Tables ---
    # IMPORTANT: db.create_all() only creates *new* tables.
    # It DOES NOT update existing tables if models change.
    # For schema changes after initial creation, use migrations (e.g., Flask-Migrate).
    # Running this in the factory ensures it happens within app context.
    with app.app_context():
        try:
            # Import models here IF they aren't imported elsewhere before create_all
            # from . import models # Already imported via views import usually
            db.create_all()
            app.logger.info("Database tables checked/created (if they didn't exist).")
        except Exception as e:
            # Log error specific to database creation/connection
            app.logger.error(f"Error during db.create_all() - Check DB connection URI and permissions: {e}")
            app.logger.error(f"Database URI used: {app.config.get('SQLALCHEMY_DATABASE_URI')}")


    # --- Final Checks ---
    if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
       app.logger.warning("MAIL_USERNAME or MAIL_PASSWORD not configured. Email functionality will not work.")

    app.logger.info("Flask app creation finished.")
    return app

# --- End of __init__.py ---
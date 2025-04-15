# --- app/__init__.py ---
# (This file remains unchanged from the previous complete version provided)
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
serializer = None

log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
log_handler = RotatingFileHandler('job_portal.log', maxBytes=10240, backupCount=10)
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.INFO)

def create_app(config_class=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'a_very_default_unsafe_secret_key_change_me'),
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{os.path.join(app.instance_path, 'site.db')}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER = os.path.join(app.instance_path, 'uploads', 'resumes'),
        MAX_CONTENT_LENGTH = 5 * 1024 * 1024, # 5 MB
        MAIL_SERVER=os.environ.get('MAIL_SERVER', 'smtp.example.com'),
        MAIL_PORT=int(os.environ.get('MAIL_PORT', 587)),
        MAIL_USE_TLS=os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true',
        MAIL_USE_SSL=os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true',
        MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
        MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@example.com'),
        SECURITY_PASSWORD_SALT=os.environ.get('SECURITY_PASSWORD_SALT', 'default_salt_change_me_too')
    )
    try: os.makedirs(app.instance_path)
    except OSError: pass
    upload_path = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_path):
        try: os.makedirs(upload_path); app.logger.info(f"Created upload directory: {upload_path}")
        except OSError as e: app.logger.error(f"Error creating upload directory {upload_path}: {e}")

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    global serializer
    if not app.config.get('SECRET_KEY') or app.config['SECRET_KEY'] == 'a_very_default_unsafe_secret_key_change_me': app.logger.warning("Insecure SECRET_KEY detected.")
    if not app.config.get('SECURITY_PASSWORD_SALT') or app.config['SECURITY_PASSWORD_SALT'] == 'default_salt_change_me_too': app.logger.warning("Insecure SECURITY_PASSWORD_SALT detected.")
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    login_manager.login_message = "Please log in to access this page."

    @login_manager.user_loader
    def load_user(user_id): from .models import User; return User.query.get(int(user_id))

    @app.context_processor
    def inject_now(): return {'now': datetime.utcnow}

    from .views import main_bp, auth_bp, jobs_bp, employers_bp, admin_bp
    app.register_blueprint(main_bp); app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(jobs_bp, url_prefix='/jobs'); app.register_blueprint(employers_bp, url_prefix='/employer')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.logger.info("Blueprints registered.")

    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
           try: os.mkdir('logs')
           except OSError as e: app.logger.error(f"Error creating logs directory: {e}")
        log_file_path = os.path.join('logs', 'job_portal.log')
        try:
            file_handler = RotatingFileHandler(log_file_path, maxBytes=10240, backupCount=10)
            file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler); app.logger.setLevel(logging.INFO)
            app.logger.info('Job Portal logging configured.')
        except Exception as e: app.logger.error(f"Failed to configure logging: {e}")

    with app.app_context():
        from . import models
        try: db.create_all(); app.logger.info("Database tables checked/created.")
        except Exception as e: app.logger.error(f"Error during db.create_all(): {e}")

    if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'): app.logger.warning("MAIL config missing. Email functionality disabled.")
    return app

# --- End of __init__.py ---
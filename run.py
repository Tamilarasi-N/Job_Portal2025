# --- run.py ---
import os
from dotenv import load_dotenv
from whitenoise import WhiteNoise # Import WhiteNoise

# Load environment variables from .env file (primarily for local development)
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print("Loaded environment variables from .env file.") # Confirm loading locally
else:
    print("No .env file found, relying on system environment variables.")


from app import create_app # Import factory function

# Create the Flask app instance
app = create_app()

# --- V V V --- Wrap app with WhiteNoise for static file serving --- V V V ---
# This allows Gunicorn to serve static files efficiently in production.
# It uses the 'static' folder and '/static' URL prefix defined by Flask's defaults.
# It safely handles missing files and sets appropriate cache headers.
app.wsgi_app = WhiteNoise(app.wsgi_app, root=app.static_folder, prefix=app.static_url_path)
app.logger.info("WhiteNoise configured to serve static files.")
# --- ^ ^ ^ --- End WhiteNoise Wrap --- ^ ^ ^ ---


if __name__ == '__main__':
    # Get debug status from environment variable, default to False ('0')
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    # Run the Flask development server (used for local testing only)
    # Gunicorn runs the 'app' object directly when deployed
    app.run(debug=debug_mode, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

# --- End of run.py ---
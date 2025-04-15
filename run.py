# --- run.py ---
import os
from dotenv import load_dotenv
from whitenoise import WhiteNoise # Import WhiteNoise

# Load environment variables from .env file (primarily for local development)
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print("Loaded environment variables from .env file.")
else:
    print("No .env file found, relying on system environment variables.")


from app import create_app # Import factory function

# --- V V V --- Explicitly find static folder --- V V V ---
# Get the absolute path to the directory this script is in (project root)
project_root = os.path.dirname(os.path.abspath(__file__))
# Construct the absolute path to the static folder
static_folder_path = os.path.join(project_root, 'static')
# --- ^ ^ ^ --- End static folder path --- ^ ^ ^ ---


# Create the Flask app instance
app = create_app()

# --- V V V --- Wrap app with WhiteNoise using explicit path --- V V V ---
# Check if the calculated static folder actually exists before wrapping
if os.path.isdir(static_folder_path):
    app.wsgi_app = WhiteNoise(app.wsgi_app, root=static_folder_path, prefix='/static')
    app.logger.info(f"WhiteNoise configured to serve from: {static_folder_path}")
else:
    app.logger.warning(f"Static folder not found at {static_folder_path}. WhiteNoise disabled.")
# --- ^ ^ ^ --- End WhiteNoise Wrap --- ^ ^ ^ ---


if __name__ == '__main__':
    # Get debug status from environment variable, default to False ('0')
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    # Get port from environment variable, default to 5000 for local dev
    port = int(os.environ.get('PORT', 5000))
    # Run the Flask development server (used for local testing only)
    app.run(debug=debug_mode, host='0.0.0.0', port=port)

# --- End of run.py ---
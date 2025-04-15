# --- run.py ---
import os
from dotenv import load_dotenv

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

from app import create_app

# Create the Flask app instance using the factory function
# Pass environment='development' or 'production' if needed for config switching
app = create_app()

if __name__ == '__main__':
    # Run the Flask development server
    # Debug=True enables auto-reloading and detailed error pages
    # In production, use a proper WSGI server like Gunicorn or uWSGI
    app.run(debug=True)
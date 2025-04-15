# --- create_admin.py ---
import os
from getpass import getpass # For securely getting password input
from dotenv import load_dotenv

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

# Create the Flask app instance to access application context and db
app = create_app()

def create_admin():
    """Creates the initial administrator user."""
    with app.app_context():
        print("Creating administrator user...")
        username = input("Enter admin username: ")
        email = input("Enter admin email: ")

        # Basic check if user or email already exists
        if User.query.filter((User.username == username) | (User.email == email)).first():
            print(f"Error: User with username '{username}' or email '{email}' already exists.")
            return

        while True:
            password = getpass("Enter admin password: ")
            confirm_password = getpass("Confirm admin password: ")
            if password == confirm_password:
                # Add password complexity validation here if desired,
                # though it's primarily handled in the registration form
                break
            else:
                print("Passwords do not match. Please try again.")

        # Create the admin user
        admin_user = User(
            username=username,
            email=email,
            role='admin',
            is_verified=True # Admins created via script are verified by default
        )
        admin_user.set_password(password) # Hash the password

        try:
            db.session.add(admin_user)
            db.session.commit()
            print(f"Administrator user '{username}' created successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error creating admin user: {e}")

if __name__ == '__main__':
    create_admin()
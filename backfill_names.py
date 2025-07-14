import os
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker
from model import User


# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
DATABASE_URL = os.environ.get("DATABASE_URL")
CLERK_API_KEY = os.environ.get("CLERK_SECRET_KEY") # Make sure this is your Clerk B2B Secret Key
CLERK_API_URL = "https://api.clerk.com/v1"

if not DATABASE_URL or not CLERK_API_KEY:
    raise Exception("DATABASE_URL and CLERK_SECRET_KEY must be set in the .env file")

# --- Database Setup ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_clerk_user_name(user_id):
    """Fetches user details from the Clerk API and returns the full name."""
    headers = {
        "Authorization": f"Bearer {CLERK_API_KEY}",
        "Content-Type": "application/json"
    }
    url = f"{CLERK_API_URL}/users/{user_id}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        
        user_data = response.json()
        first_name = user_data.get("first_name", "")
        last_name = user_data.get("last_name", "")
        
        full_name = f"{first_name} {last_name}".strip()
        return full_name if full_name else "Unknown"
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user {user_id} from Clerk: {e}")
        return None

def backfill_user_names():
    """Finds users with 'Unknown' name and updates them with data from Clerk."""
    db = SessionLocal()
    try:
        # Find all users with the name 'Unknown'
        stmt = select(User).where(User.name == 'Unknown')
        users_to_update = db.execute(stmt).scalars().all()
        
        if not users_to_update:
            print("No users with 'Unknown' name found. Nothing to do.")
            return

        print(f"Found {len(users_to_update)} user(s) to update.")

        for user in users_to_update:
            print(f"Processing user ID: {user.id}...")
            
            # Get the correct name from Clerk
            correct_name = get_clerk_user_name(user.id)
            
            if correct_name and correct_name != 'Unknown':
                print(f"  -> Found name: '{correct_name}'. Updating database...")
                # Update the user's name in the database
                update_stmt = update(User).where(User.id == user.id).values(name=correct_name)
                db.execute(update_stmt)
                print(f"  -> Successfully updated user {user.id}.")
            else:
                print(f"  -> Could not retrieve a valid name for user {user.id}. Skipping.")
        
        # Commit all changes to the database
        db.commit()
        print("\nBackfill process completed successfully!")

    except Exception as e:
        print(f"An error occurred during the backfill process: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # Before running, ensure 'requests' is installed:
    # pip install requests
    backfill_user_names()
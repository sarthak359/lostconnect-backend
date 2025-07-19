from flask import Flask, request, jsonify
from flask_cors import CORS
from database import db, migrate
from model import User, Project
from dotenv import load_dotenv
import os
import hmac
import hashlib
import base64

load_dotenv()
CLERK_API_KEY = os.getenv("CLERK_SECRET_KEY")
CLERK_API_URL = "https://api.clerk.com/v1"

def get_clerk_user_name(user_id):
    headers = {
        "Authorization": f"Bearer {CLERK_API_KEY}",
        "Content-Type": "application/json"
    }
    url = f"{CLERK_API_URL}/users/{user_id}"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        username = data.get("username", "")
        full_name = f"{first_name} {last_name}".strip() or username or "Unknown"
        return full_name
    except Exception as e:
        print(f"Clerk fetch error: {e}")
        return "Unknown"


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

    # Enable CORS for frontend access
    CORS(app, resources={r"/*": {"origins": [
    "http://localhost:5173",  # ✅ local dev
    "https://lostconnect-frontend.vercel.app",  # ✅ your Vercel production domain
    "https://lostconnect-frontend-hkynh7yvh-sarthak359s-projects.vercel.app"  # ✅ optional preview link
]}},
         supports_credentials=True,
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         allow_headers=["Content-Type", "Authorization"])

    db.init_app(app)
    migrate.init_app(app, db)

    @app.route("/")
    def hello():
        return "LostConnect backend is running ✅"

    @app.route('/webhook', methods=['POST'])
    def clerk_webhook():
        webhook_secret = os.getenv("CLERK_WEBHOOK_SECRET")
        if not webhook_secret:
            return jsonify({'error': 'Webhook secret not configured'}), 200

        signature = request.headers.get("Clerk-Signature")
        payload = request.data  # raw body

        # Verify signature using HMAC-SHA256
        expected_signature = base64.b64encode(
            hmac.new(webhook_secret.encode(), payload, hashlib.sha256).digest()
        ).decode()

        if not hmac.compare_digest(signature, expected_signature):
            return jsonify({'error': 'Invalid webhook signature'}), 403

        event = request.get_json()
        event_type = event.get("type")

        if event_type in ["user.created", "user.updated"]:
            user_data = event.get("data")
            user_id = user_data.get("id")
            email_addresses = user_data.get("email_addresses", [])
            email = email_addresses[0]['email_address'] if email_addresses else None
            # Get first and last names from the webhook data
            first_name = user_data.get("first_name", "")
            last_name = user_data.get("last_name", "")
            full_name = f"{first_name} {last_name}".strip()

            user = User.query.filter_by(id=user_id).first()
            if not user:
                new_user = User(id=user_id, email=email, name=full_name)
                db.session.add(new_user)
            else:
                user.email = email
                user.name = full_name # <-- Update the name on updates too
            db.session.commit()


        elif event_type == "user.deleted":
            user_id = event.get("data", {}).get("id")
            user = User.query.filter_by(id=user_id).first()
            if user:
                db.session.delete(user)
                db.session.commit()

        return jsonify({'message': 'Webhook received'}), 200

    @app.route('/projects', methods=['GET', 'POST'])
    def projects():
        if request.method == 'GET':
            projects = Project.query.all()
            projects_list = []
            for project in projects:
                projects_list.append({
                    'id': project.id,
                    'title': project.title,
                    'description': project.description,
                    'category': project.category,
                    'status': project.status,
                    'lat': project.lat,
                    'lng': project.lng,
                    'user_id': project.user_id,
                    'created_at': project.date.isoformat() if project.date else None,
                    'creator': {
                    'id': project.user.id if project.user else None,
                    'name': project.user.name if project.user else "Unknown",
                    'email': project.user.email if project.user else "Unknown"
                }
                })
            return jsonify(projects_list)

        elif request.method == 'POST':
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Invalid JSON data'}), 400

            user_id = data.get('user_id')
            user_email = data.get('user_email')
            user_name = data.get('user_name') # <-- Get the name from the request

            # Check if user exists, create if not
            user = User.query.filter_by(id=user_id).first()
            full_name = user_name or get_clerk_user_name(user_id)

            if not user:
                user = User(id=user_id, email=user_email, name=full_name)
                db.session.add(user)
                db.session.commit()
            else:
                # Fix: update name if it's missing or incorrect
                if (not user.name or user.name == "Unknown") and full_name:
                    user.name = full_name
                    db.session.commit()

            if user and user_name and user.name != user_name:
                user.name = user_name
                db.session.commit()


            title = data.get('title')
            description = data.get('description')
            category = data.get('category')
            status = data.get('status')
            lat = data.get('lat')
            lng = data.get('lng')
            user_id = data.get('user_id')

            if not all([title, description, category, status, lat, lng, user_id]):
                return jsonify({'error': 'Missing required fields'}), 400

            new_project = Project(
                title=title,
                description=description,
                category=category,
                status=status,
                lat=lat,
                lng=lng,
                user_id=user_id
            )

            try:
                db.session.add(new_project)
                db.session.commit()
                return jsonify({'message': 'Project added successfully', 'id': new_project.id}), 201
            except Exception as e:
                db.session.rollback()
                return jsonify({'error': str(e)}), 500
    @app.route('/users', methods=['POST'])
    def create_user():
        import requests

        data = request.get_json()
        user_id = data.get("id")
        email = data.get("email")

        if not user_id or not email:
            return jsonify({'error': 'User ID and email are required'}), 400

        # Check if user already exists
        existing_user = User.query.get(user_id)
        if existing_user:
            return jsonify({'message': 'User already exists'}), 200

        # Fetch name from Clerk if not provided
        clerk_api_key = os.getenv("CLERK_SECRET_KEY")
        headers = {
            "Authorization": f"Bearer {clerk_api_key}",
            "Content-Type": "application/json"
        }
        url = f"https://api.clerk.com/v1/users/{user_id}"

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            clerk_data = response.json()
            first_name = clerk_data.get("first_name", "")
            last_name = clerk_data.get("last_name", "")
            full_name = f"{first_name} {last_name}".strip() or "Unknown"
        except Exception as e:
            full_name = "Unknown"

        try:
            full_name = get_clerk_user_name(user_id)
            new_user = User(id=user_id, email=email, name=full_name)
            db.session.add(new_user)
            db.session.commit()
            return jsonify({'message': 'User created successfully', 'id': new_user.id, 'name': new_user.name, 'email': new_user.email}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    @app.route('/projects/delete-all', methods=['POST'])
    def delete_all_projects():
        try:
            num_deleted = Project.query.delete()
            db.session.commit()
            return jsonify({'message': f'{num_deleted} projects deleted'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    @app.route("/run-backfill", methods=["GET"])
    def run_backfill():
        import os
        import requests
        from sqlalchemy import select, update
        from database import db
        from model import User
        from dotenv import load_dotenv

        load_dotenv()
        CLERK_API_KEY = os.getenv("CLERK_SECRET_KEY")
        CLERK_API_URL = "https://api.clerk.com/v1"

        def get_clerk_user_name(user_id):
            headers = {
                "Authorization": f"Bearer {CLERK_API_KEY}",
                "Content-Type": "application/json"
            }
            url = f"{CLERK_API_URL}/users/{user_id}"
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                return f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or "Unknown"
            except:
                return None

        try:
            users_to_update = db.session.execute(
                select(User).where(User.name == 'Unknown')
            ).scalars().all()

            for user in users_to_update:
                real_name = get_clerk_user_name(user.id)
                if real_name and real_name != "Unknown":
                    db.session.execute(
                        update(User).where(User.id == user.id).values(name=real_name)
                    )
            db.session.commit()
            return "Backfill complete ✅"
        except Exception as e:
            return f"Error: {str(e)}", 500


    return app



if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)

app = create_app()

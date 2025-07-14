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

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

    # Enable CORS for frontend access
    CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}},
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
            name = user_data.get("first_name", "") + " " + user_data.get("last_name", "")
            email_addresses = user_data.get("email_addresses", [])
            email = email_addresses[0]['email_address'] if email_addresses else None
            phone = user_data.get("primary_phone_number", {}).get("phone_number", "")

            user = User.query.filter_by(id=user_id).first()
            if not user:
                new_user = User(id=user_id, name=name, email=email, phone=phone)
                db.session.add(new_user)
            else:
                user.name = name
                user.email = email
                user.phone = phone
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
                    'name': project.user.name if project.user and project.user.name else "Unknown",
                    'email': project.user.email if project.user else "Unknown"
                }
                })
            return jsonify(projects_list)

        elif request.method == 'POST':
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Invalid JSON data'}), 400

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
        data = request.get_json()
        user_id = data.get("id")
        email = data.get("email")

        if not user_id or not email:
            return jsonify({'error': 'User ID and email are required'}), 400

        # Check if user already exists
        existing_user = User.query.get(user_id)
        if existing_user:
            return jsonify({'message': 'User already exists'}), 200

        try:
            new_user = User(id=user_id, email=email)
            db.session.add(new_user)
            db.session.commit()
            return jsonify({'message': 'User created successfully'}), 201
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
    return app



if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)

app = create_app()

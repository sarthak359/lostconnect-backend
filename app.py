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
            email_addresses = user_data.get("email_addresses", [])
            email = email_addresses[0]['email_address'] if email_addresses else None

            user = User.query.filter_by(id=user_id).first()
            if not user:
                new_user = User(id=user_id, email=email)
                db.session.add(new_user)
            else:
                user.email = email
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
                    'created_at': project.created_at.isoformat() if project.created_at else None
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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)

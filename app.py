import os
import logging
from flask import Flask
from flask_cors import CORS
from pymongo import MongoClient


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/release_notes")
    client = MongoClient(mongo_uri)
    db = client.get_database()
    app.logger.info("Successfully connected to MongoDB.")

    app.mongo_db = db  # type: ignore

    from modules.api import api_bp
    from modules.views import views_bp

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(views_bp)

    return app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    application = create_app()
    application.run(host='0.0.0.0', port=port, debug=True)
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
 
    db.init_app(app)
    CORS(app, resources={r"/*": {"origins": "*"}})

    from app.routes.analyzer import analyzer_bp
    app.register_blueprint(analyzer_bp)
 
    with app.app_context():
        db.create_all()
 
    return app
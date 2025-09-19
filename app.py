from __future__ import annotations
import os
from flask import Flask
from flask_cors import CORS
from apps.ev.app import ev_bp
from db import init_db

app = Flask(__name__, instance_relative_config=False)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'ev.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

init_db(app)
app.register_blueprint(ev_bp)
CORS(app)


if __name__ == "__main__":
    app.run(debug=True, port=5010)

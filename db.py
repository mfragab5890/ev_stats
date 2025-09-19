from apps.ev.models import db


def init_db(app):
    db.init_app(app)
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"Database Error: {e}")
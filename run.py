from app import create_app
from app.extensions import db

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Auto-create DB if not exists
        db.create_all()
    app.run(debug=True, port=5001)

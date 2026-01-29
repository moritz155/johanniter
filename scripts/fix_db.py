from app import app, db
import os

print(f"DB Path: {app.config['SQLALCHEMY_DATABASE_URI']}")
if os.path.exists('app.db'):
    print(f"Size: {os.path.getsize('app.db')}")

with app.app_context():
    try:
        print(f"CWD: {os.getcwd()}")
        db.create_all()
        print("db.create_all() executed.")
        # Force write
        from app import ShiftConfig
        import uuid
        if not ShiftConfig.query.first():
             print("Writing dummy config to force file creation...")
             c = ShiftConfig(session_id=str(uuid.uuid4()), location="INIT_TEST")
             db.session.add(c)
             db.session.commit()
             print("Committed.")
    except Exception as e:
        print(f"Error: {e}")

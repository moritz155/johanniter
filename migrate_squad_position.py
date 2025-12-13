from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        with db.engine.connect() as conn:
            # Add position column (Integer, default 0)
            try:
                conn.execute(text("ALTER TABLE squad ADD COLUMN position INTEGER DEFAULT 0"))
                print("Added position column.")
            except Exception as e:
                print(f"position column might already exist: {e}")
                
            conn.commit()
            print("Migration completed.")
            
    except Exception as e:
        print(f"Migration failed: {e}")

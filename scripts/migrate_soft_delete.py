from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        # Check if column exists first to avoid error
        with db.engine.connect() as conn:
            # Add is_deleted
            try:
                conn.execute(text("ALTER TABLE mission ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
                print("Added is_deleted column.")
            except Exception as e:
                print(f"is_deleted column might already exist: {e}")

            # Add deletion_reason
            try:
                conn.execute(text("ALTER TABLE mission ADD COLUMN deletion_reason VARCHAR(200)"))
                print("Added deletion_reason column.")
            except Exception as e:
                print(f"deletion_reason column might already exist: {e}")
                
            conn.commit()
            print("Migration completed.")
            
    except Exception as e:
        print(f"Migration failed: {e}")

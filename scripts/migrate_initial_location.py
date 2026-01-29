from app import app, db
from sqlalchemy import text

def migrate():
    with app.app_context():
        try:
            # Check if column exists
            with db.engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(mission)"))
                columns = [row[1] for row in result]
                
                if 'initial_location' not in columns:
                    print("Adding initial_location column to mission table...")
                    conn.execute(text("ALTER TABLE mission ADD COLUMN initial_location VARCHAR(200)"))
                    conn.commit()
                    print("Migration successful: initial_location added.")
                else:
                    print("Migration skipped: initial_location already exists.")
                    
        except Exception as e:
            print(f"Migration failed: {e}")

if __name__ == '__main__':
    migrate()

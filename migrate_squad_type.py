import sqlite3
import os

def migrate():
    # Use absolute path to ensure we hit the right DB
    # The DB is likely in the 'instance' folder based on list_tables.py
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'instance', 'app.db')
    
    # Verify it exists
    if not os.path.exists(db_path):
        print(f"Warning: Database not found at {db_path}")
        # Try root just in case
        db_path = os.path.join(base_dir, 'app.db')
        
    print(f"Connecting to database at: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(squad)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Existing columns: {columns}")
        
        if 'type' not in columns:
            print("Adding 'type' column to squad table...")
            cursor.execute("ALTER TABLE squad ADD COLUMN type TEXT DEFAULT 'Trupp'")
            print("Column added successfully.")
        else:
            print("'type' column already exists.")
            
        conn.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

import sqlite3

def migrate():
    conn = sqlite3.connect('instance/app.db')
    cursor = conn.cursor()
    
    try:
        # Check current columns
        cursor.execute("PRAGMA table_info(mission)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'arm_id' not in columns:
            print("Adding arm_id...")
            cursor.execute("ALTER TABLE mission ADD COLUMN arm_id VARCHAR(50)")
            
        if 'arm_type' not in columns:
            print("Adding arm_type...")
            cursor.execute("ALTER TABLE mission ADD COLUMN arm_type VARCHAR(50)")
            
        conn.commit()
        print("Migration successful.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()


import sqlite3

def migrate():
    try:
        conn = sqlite3.connect('instance/app.db')
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(shift_config)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'password_hash' not in columns:
            print("Migrating: Adding password_hash to shift_config...")
            cursor.execute("ALTER TABLE shift_config ADD COLUMN password_hash VARCHAR(128)")
            conn.commit()
            print("Migration successful.")
        else:
            print("Column password_hash already exists.")

        # Check for Squad access_token
        cursor.execute("PRAGMA table_info(squad)")
        squad_columns = [info[1] for info in cursor.fetchall()]

        if 'access_token' not in squad_columns:
            print("Migrating: Adding access_token to squad...")
            cursor.execute("ALTER TABLE squad ADD COLUMN access_token VARCHAR(36)")
            conn.commit()
            print("Migration of squad successful.")
        else:
            print("Column access_token already exists in squad.")
            
        conn.close()
    except Exception as e:
        print(f"Migration error: {e}")

if __name__ == '__main__':
    migrate()

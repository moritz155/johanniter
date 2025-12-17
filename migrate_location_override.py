import sqlite3

def migrate():
    try:
        conn = sqlite3.connect('instance/app.db')
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE squad ADD COLUMN custom_location VARCHAR(200)")
        conn.commit()
        conn.close()
        print("Migration successful: Added custom_location column.")
    except Exception as e:
        print(f"Migration failed or already applied: {e}")

if __name__ == '__main__':
    migrate()

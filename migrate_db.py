import sqlite3

def migrate():
    try:
        conn = sqlite3.connect('instance/app.db')
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE squad ADD COLUMN service_numbers VARCHAR(200)")
        conn.commit()
        conn.close()
        print("Migration successful: Added service_numbers column.")
    except Exception as e:
        print(f"Migration failed or already applied: {e}")

if __name__ == '__main__':
    migrate()

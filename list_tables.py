
import sqlite3

def list_tables():
    conn = sqlite3.connect('instance/app.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print(cursor.fetchall())
    conn.close()

if __name__ == '__main__':
    list_tables()

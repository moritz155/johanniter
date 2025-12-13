from app import app, db
from sqlalchemy import inspect
import sys

with app.app_context():
    try:
        inspector = inspect(db.engine)
        if not inspector.has_table('mission'):
            print("Table 'mission' does not exist.")
            sys.exit(0)
            
        columns = [c['name'] for c in inspector.get_columns('mission')]
        print(f"Columns in mission: {columns}")
        if 'session_id' in columns:
            print("session_id column FOUND.")
        else:
            print("session_id column MISSING.")
            
    except Exception as e:
        print(f"Error: {e}")

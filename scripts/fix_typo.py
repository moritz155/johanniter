
from app import app, db, PredefinedOption

with app.app_context():
    # Find all options with the typo
    typos = PredefinedOption.query.filter_by(value='Aktute Erkrankung').all()
    print(f"Found {len(typos)} entries to fix.")
    
    for opt in typos:
        opt.value = 'Akute Erkrankung'
    
    db.session.commit()
    print("Typo fixed in database.")

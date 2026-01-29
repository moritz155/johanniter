from app import app, db, PredefinedOption
import os

with app.app_context():
    # Delete all existing options
    PredefinedOption.query.delete()
    
    # Load from file
    default_file = 'default_options.txt'
    if os.path.exists(default_file):
        with open(default_file, 'r', encoding='utf-8') as f:
            current_category = None
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if line.startswith('[') and line.endswith(']'):
                    current_category = line[1:-1].lower()
                elif current_category in ['location', 'entity', 'reason']:
                    db.session.add(PredefinedOption(category=current_category, value=line))
    
    db.session.commit()
    print("Options updated successfully!")
    
    # Show what was loaded
    print("\nLoaded options:")
    for opt in PredefinedOption.query.all():
        print(f"  {opt.category}: {opt.value}")

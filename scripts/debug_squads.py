from app import app, db, Squad, Mission

with app.app_context():
    print("Checking squads...")
    squads = Squad.query.all()
    for s in squads:
        try:
            d = s.to_dict()
            print(f"Squad {s.id} OK: {d['name']}")
        except Exception as e:
            print(f"Squad {s.id} FAILED: {e}")
            import traceback
            traceback.print_exc()

    print("Checking missions created_at...")
    missions = Mission.query.all()
    for m in missions:
        if m.created_at is None:
            print(f"Mission {m.id} has None created_at!")

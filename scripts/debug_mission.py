from app import app, db, Mission, get_session_id
from flask import session

with app.app_context():
    print("Attempting to create mission...")
    # Simulate session
    with app.test_request_context():
        # Setup dummy session
        session['user_id'] = 'debug_session'
        
        try:
            new_mission = Mission(
                location="Debug Loc",
                reason="Debug Reason",
                session_id='debug_session'
            )
            db.session.add(new_mission)
            db.session.commit()
            print(f"Mission created OK: ID {new_mission.id}")
            
            # Cleanup
            db.session.delete(new_mission)
            db.session.commit()
            print("Mission deleted OK")
            
        except Exception as e:
            print(f"Mission Creation FAILED: {e}")
            import traceback
            traceback.print_exc()

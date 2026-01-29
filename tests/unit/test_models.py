from app.models import Squad, Mission
from app.extensions import db

def test_squad_creation(app):
    with app.app_context():
        s = Squad(name="Alpha", session_id="123")
        db.session.add(s)
        db.session.commit()
        assert s.name == "Alpha"
        assert s.type == "Trupp"

def test_squad_to_dict(app):
    with app.app_context():
        s = Squad(name="Alpha", session_id="123", current_status="2")
        db.session.add(s)
        db.session.commit()
        data = s.to_dict()
        assert data['name'] == "Alpha"
        assert data['current_status'] == "2"

def test_mission_creation(app):
    with app.app_context():
        m = Mission(location="Test Loc", reason="Sick", session_id="123")
        db.session.add(m)
        db.session.commit()
        assert m.status == "Laufend"

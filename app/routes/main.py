from flask import Blueprint, render_template, request, session
from datetime import datetime
from ..models import Squad, ShiftConfig
from ..utils import get_session_id

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # Use current timestamp to force reload of static assets during development
    return render_template('index.html', last_updated=datetime.now().timestamp())

@main_bp.route('/squad/mobile-view', methods=['GET'])
def mobile_squad_view():
    token = request.args.get('token')
    if not token:
        return "Kein Token angegeben", 403
    
    # Validation
    squad = Squad.query.filter_by(access_token=token).first()
    if not squad:
        return "Ungültiges Token", 403
        
    # Check if session is active (optional but good practice)
    config = ShiftConfig.query.filter_by(session_id=squad.session_id, is_active=True).first()
    if not config:
        return "Dienst ist nicht aktiv", 403

    # Authenticate the session
    session['user_id'] = squad.session_id
    session.modified = True

    return render_template('mobile_squad_view.html', squad=squad, token=token)

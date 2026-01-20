# Mission Control - Backend (Reload Triggered)
from flask import Flask, render_template, request, jsonify, send_file, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import io
import csv
import os
import uuid
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
from werkzeug.security import generate_password_hash, check_password_hash
from messages import LogMessages

app = Flask(__name__)
app.secret_key = 'dev-secret-key-change-in-prod' # Necessary for session
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Models ---

# Association Table for Many-to-Many between Mission and Squad
mission_squad = db.Table('mission_squad',
    db.Column('mission_id', db.Integer, db.ForeignKey('mission.id'), primary_key=True),
    db.Column('squad_id', db.Integer, db.ForeignKey('squad.id'), primary_key=True)
)

class ShiftConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(200))
    address = db.Column(db.String(200), nullable=True) # New field
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=True)

    def to_dict(self):
        return {
            'location': self.location,
            'address': self.address,
            'start_time': (self.start_time.isoformat() + 'Z') if self.start_time else None,
            'end_time': (self.end_time.isoformat() + 'Z') if self.end_time else None,
            'is_active': self.is_active,
            'session_id': self.session_id # Expose for client-side storage
        }

class Squad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(20), default='Trupp')  # New: 'Trupp' or 'Ambulanz'
    qualification = db.Column(db.String(20), default='San') # San, RS, NFS, NA
    current_status = db.Column(db.String(20), default='2') # 2 (EB), 3, 4, 7, 8
    position = db.Column(db.Integer, default=0)
    service_numbers = db.Column(db.String(200), nullable=True) # Comma-seperated list
    custom_location = db.Column(db.String(200), nullable=True) # Manual override
    session_id = db.Column(db.String(100), nullable=False)
    access_token = db.Column(db.String(36), nullable=True) # QR-Code Login Token

    __table_args__ = (db.UniqueConstraint('name', 'session_id', name='_name_session_uc'),)
    last_status_change = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    missions = db.relationship('Mission', secondary=mission_squad, back_populates='squads')
    
    def to_dict(self):
        # Helper to sort safely
        def safe_sort_key(m):
            return m.created_at or datetime.min

        # Find active mission for this squad
        # Prefer latest mission if multiple are active
        # Enforce session_id check on missions just in case of ghost links
        active_missions = [m for m in self.missions if m.status not in ['Abgeschlossen', 'Storniert', 'Intervention unterblieben'] and not m.outcome and not m.is_deleted and m.session_id == self.session_id]
        active_missions.sort(key=safe_sort_key, reverse=True)
        
        active_mission = None
        if active_missions:
            m = active_missions[0]
            active_mission = {
                'id': m.id,
                'mission_number': m.mission_number,
                'location': m.location,
                'reason': m.reason,
                'squad_ids': [s.id for s in m.squads]
            }

        # Find LAST mission (any status, sorted by time)
        all_missions = [m for m in self.missions if not m.is_deleted]
        all_missions.sort(key=safe_sort_key, reverse=True)
        last_mission = None
        if all_missions:
            m = all_missions[0]
            last_mission = {
                'id': m.id,
                'mission_number': m.mission_number,
                'location': m.location
            }


        # Determine display location
        current_location_display = None
        if self.custom_location:
            current_location_display = self.custom_location
        elif last_mission:
            current_location_display = last_mission['location']

        # Calculate patient count for Ambulanz (active missions assigned)
        patient_count = 0
        if self.type == 'Ambulanz':
            # Count active missions (assuming active means not deleted/cancelled/completed)
            # Active mission usually means status != 'Abgeschlossen'
            # Also self.missions contains ALL missions.
            patient_count = sum(1 for m in self.missions if not m.is_deleted and m.status != 'Abgeschlossen')

        return {
            'id': self.id,
            'name': self.name,
            'type': self.type, 
            'qualification': self.qualification,
            'service_numbers': self.service_numbers,
            'custom_location': self.custom_location,
            'current_location_display': current_location_display,
            'current_status': self.current_status,
            'position': self.position,
            'last_status_change': (self.last_status_change.isoformat() + 'Z') if self.last_status_change else None,
            'updated_at': (self.updated_at.isoformat() + 'Z') if self.updated_at else None,
            'active_mission': active_mission,
            'last_mission': last_mission,
            'access_token': self.access_token,
            'patient_count': patient_count 
        }

class Mission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mission_number = db.Column(db.String(50), nullable=True) # Manual Entry
    location = db.Column(db.String(200), nullable=False)
    initial_location = db.Column(db.String(200), nullable=True) # To track original location
    alarming_entity = db.Column(db.String(200), nullable=True)
    reason = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Laufend') # Laufend, Abgeschlossen
    outcome = db.Column(db.String(50), nullable=True) # Inter Unter, Belassen, ARM, PVW
    arm_id = db.Column(db.String(50), nullable=True)  # Kennung if ARM
    arm_type = db.Column(db.String(50), nullable=True) # Typ if ARM
    arm_notes = db.Column(db.String(500), nullable=True) # Zusätzliche Notiz für Übergabe
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    session_id = db.Column(db.String(100), nullable=False)
    
    # Soft Delete
    is_deleted = db.Column(db.Boolean, default=False)
    deletion_reason = db.Column(db.String(200))

    # Relationships
    squads = db.relationship('Squad', secondary=mission_squad, back_populates='missions')

    def to_dict(self):
        return {
            'id': self.id,
            'mission_number': self.mission_number,
            'location': self.location,
            'initial_location': self.initial_location,
            'alarming_entity': self.alarming_entity,
            'squads': [{'name': s.name, 'id': s.id, 'status': s.current_status} for s in self.squads],
            'squad_ids': [s.id for s in self.squads],
            'reason': self.reason,
            'description': self.description,
            'status': self.status,
            'outcome': self.outcome,
            'arm_id': self.arm_id,
            'arm_type': self.arm_type,
            'arm_notes': self.arm_notes,
            'notes': self.notes,
            'created_at': (self.created_at.isoformat() + 'Z') if self.created_at else None,
            'updated_at': (self.updated_at.isoformat() + 'Z') if self.updated_at else None
        }

class LogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(50)) # MISSION_CREATE, MISSION_UPDATE, STATUS_CHANGE, CONFIG
    details = db.Column(db.String(500))
    mission_id = db.Column(db.Integer, db.ForeignKey('mission.id'), nullable=True)
    squad_id = db.Column(db.Integer, db.ForeignKey('squad.id'), nullable=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': (self.timestamp.isoformat() + 'Z') if self.timestamp else None,
            'action': self.action,
            'details': self.details,
            'mission_id': self.mission_id,
            'squad_id': self.squad_id
        }

class PredefinedOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50)) # location, entity, reason
    value = db.Column(db.String(200))
    session_id = db.Column(db.String(36), nullable=False, index=True)

# --- Helper Functions ---

STATUS_MAP = {
    '2': 'EB',
    '3': 'zBO',
    '4': 'BO',
    '7': 'zAO',
    '8': 'AO',
    'Pause': 'Pause',
    'NEB': 'NEB',
    '1': 'Frei',
    'Integriert': 'Disponiert'
}

def get_session_id():
    # Priority: 1. Header (Robustness), 2. Cookie (Standard)
    header_sid = request.headers.get('X-Session-ID')
    if header_sid:
         # Optionally set it in cookie for sync
         if 'user_id' not in session or session['user_id'] != header_sid:
             session['user_id'] = header_sid
         return header_sid

    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return session['user_id']

def log_action(action, details, mission_id=None, squad_id=None):
    entry = LogEntry(
        action=action, 
        details=details, 
        mission_id=mission_id, 
        squad_id=squad_id,
        session_id=get_session_id()
    )
    db.session.add(entry)
    db.session.commit()

def update_ambulanz_occupancy(squad):
    """
    Checks if the squad is an Ambulanz and updates its status to '4' (Besetzt)
    if it has active missions.
    """
    if squad.type != 'Ambulanz':
        return

    # Count active missions
    active_count = sum(1 for m in squad.missions if not m.is_deleted and m.status != 'Abgeschlossen')
    
    if active_count > 0:
        if squad.current_status not in ['4', '3']: # If not already busy
            squad.current_status = '4'
            squad.last_status_change = datetime.utcnow()
            db.session.commit()
            log_action('STATUS', f"{squad.name}: {LogMessages.STATUS_AUTO_BUSY}", squad_id=squad.id)
    else:
        # Auto-Free if currently Besetzt (4)
        if squad.current_status == '4':
            squad.current_status = '2'
            squad.last_status_change = datetime.utcnow()
            db.session.commit()
            log_action('STATUS', f"{squad.name}: {LogMessages.STATUS_AUTO_FREE}", squad_id=squad.id)

# --- Error Handling ---
@app.errorhandler(Exception)
def handle_exception(e):
    # pass through HTTP errors
    if isinstance(e, int):
        return jsonify({'error': str(e)}), e
    
    # Check if it's an HTTP exception (like 404, 500 from abort)
    if hasattr(e, 'code'):
        return jsonify({'error': str(e)}), e.code
        
    # Generic 500
    print(f"Server Error: {e}")
    return jsonify({'error': f"Internal Server Error: {str(e)}"}), 500

# --- Routes ---

@app.route('/')
def index():
    # Use current timestamp to force reload of static assets during development
    return render_template('index.html', last_updated=datetime.now().timestamp())

@app.route('/api/init', methods=['GET'])
def get_init_data():
    sid = get_session_id()
    config = ShiftConfig.query.filter_by(is_active=True, session_id=sid).first()
    
    squads = Squad.query.filter_by(session_id=sid).order_by(Squad.position).all()
    
    # Self-Healing: Ensure all squads have access_token
    token_update_needed = False
    for s in squads:
        if not s.access_token:
            s.access_token = str(uuid.uuid4())
            token_update_needed = True
    
    if token_update_needed:
        db.session.commit()
    
    # Filter out deleted missions
    missions = Mission.query.filter_by(session_id=sid, is_deleted=False).order_by(Mission.created_at.desc()).all()
    
    # Predefined options
    opts = PredefinedOption.query.filter_by(session_id=sid).all()
    options_map = {}
    for o in opts:
        if o.category not in options_map:
            options_map[o.category] = []
        options_map[o.category].append(o.value)
    
    # Logs
    logs = LogEntry.query.filter_by(session_id=sid).order_by(LogEntry.timestamp.desc()).all()

    return jsonify({
        'config': config.to_dict() if config else None,
        'squads': [s.to_dict() for s in squads],
        'missions': [m.to_dict() for m in missions],
        'options': options_map,
        'logs': [l.to_dict() for l in logs]
    })
    
@app.route('/api/updates', methods=['GET'])
def get_updates():
    try:
        # Support Token (Mobile)
        token = request.args.get('token')
        sid = None
        
        if token:
            sq = Squad.query.filter_by(access_token=token).first()
            if sq:
                sid = sq.session_id
            else:
                 # Invalid token, but maybe just fall back to session?
                 pass 
        
        if not sid:
            sid = get_session_id()

        # simplified long polling check
        squad_query = Squad.query.filter_by(session_id=sid)
        mission_query = Mission.query.filter_by(session_id=sid, is_deleted=False)
        log_query = LogEntry.query.filter_by(session_id=sid)

        since = request.args.get('since')
        if since:
            try:
                # Handle JS toISOString Z suffix
                if since.endswith('Z'):
                    since = since[:-1]
                limit_dt = datetime.fromisoformat(since)
                
                squad_query = squad_query.filter(Squad.updated_at > limit_dt)
                mission_query = mission_query.filter(Mission.updated_at > limit_dt)
                log_query = log_query.filter(LogEntry.timestamp > limit_dt)
            except ValueError:
                pass # Ignore invalid timestamp

        squads = squad_query.order_by(Squad.position).all()
        missions = mission_query.order_by(Mission.created_at.desc()).all()
        logs = log_query.order_by(LogEntry.timestamp.desc()).limit(50).all()
        
        # Restore Config & Options (Critical for Frontend)
        config = ShiftConfig.query.filter_by(session_id=sid, is_active=True).first()
        
        opts = PredefinedOption.query.filter_by(session_id=sid).all()
        options_map = {}
        for o in opts:
            if o.category not in options_map:
                options_map[o.category] = []
            options_map[o.category].append(o.value)

        return jsonify({
            'config': config.to_dict() if config else None,
            'squads': [s.to_dict() for s in squads],
            'missions': [m.to_dict() for m in missions],
            'options': options_map, 
            'logs': [l.to_dict() for l in logs]
        })
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['POST'])
def save_config():
    data = request.json
    sid = get_session_id()
    
    # Deactivate old configs for this session
    ShiftConfig.query.filter_by(session_id=sid).update({ShiftConfig.is_active: False})
    
    # Create new config
    start_dt = datetime.utcnow()
    # If user provided start_time (optional in creation, usually now)
    if 'start_time' in data and data['start_time']:
        try:
            start_dt = datetime.fromisoformat(data['start_time'])
        except:
            pass

    pwd = data.get('password')
    p_hash = generate_password_hash(pwd) if pwd else None

    new_config = ShiftConfig(
        location=data.get('location', ''),
        address=data.get('address', ''),
        start_time=start_dt,
        session_id=sid,
        password_hash=p_hash
    )
    db.session.add(new_config)
    
    # Handle pre-defined options if provided
    if 'options' in data:
        PredefinedOption.query.filter_by(session_id=sid).delete()
        for cat, values in data['options'].items():
            for val in values:
                db.session.add(PredefinedOption(category=cat, value=val, session_id=sid))
    else:
        # Load default options from file if it exists
        PredefinedOption.query.filter_by(session_id=sid).delete()
        default_file = 'default_options.txt'
        if os.path.exists(default_file):
            try:
                with open(default_file, 'r', encoding='utf-8') as f:
                    current_category = None
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):  # Skip empty lines and comments
                            continue
                        
                        # Check if this is a category header
                        if line.startswith('[') and line.endswith(']'):
                            current_category = line[1:-1].lower()
                        elif current_category in ['location', 'entity', 'reason']:
                            db.session.add(PredefinedOption(category=current_category, value=line, session_id=sid))
            except Exception as e:
                print(f"Error loading default options: {e}")
    
    # Initial Squads - Only create if requested (Standard Setup)
    if 'squads' in data:
        # Clean up associations first to prevent orphans
        # Delete associations where the squad belongs to this session
        db.session.execute(db.text("""
            DELETE FROM mission_squad 
            WHERE squad_id IN (SELECT id FROM squad WHERE session_id = :sid)
        """), {'sid': sid})
        
        Squad.query.filter_by(session_id=sid).delete()
        Mission.query.filter_by(session_id=sid).delete()
        LogEntry.query.filter_by(session_id=sid).delete()
        # But for now, let's assume we are resetting everything for this user.
        # Since we just deleted all squads for this sid, the associations are invalid.
        # Ideally, we should clean them up, but SQLite might leave them.
        
        for s in data['squads']:
            new_squad = Squad(
                name=s['name'], 
                qualification=s.get('qualification', 'San'), 
                session_id=sid,
                access_token=str(uuid.uuid4())
            )
            db.session.add(new_squad)

    db.session.commit()
    log_action('KONFIGURATION', LogMessages.SHIFT_STARTED.format(location=new_config.location))
    return jsonify(new_config.to_dict())

@app.route('/api/join', methods=['POST'])
def join_session():
    data = request.json
    pwd = data.get('password')
    
    if not pwd:
        return jsonify({"success": False, "message": "Passwort fehlt"}), 400
        
    # Find active shifts
    try:
        active_configs = ShiftConfig.query.filter_by(is_active=True).all()
        found_config = None
        
        for conf in active_configs:
            if conf.password_hash and check_password_hash(conf.password_hash, pwd):
                found_config = conf
                break
                
        if found_config:
            # Link this user to the session
            session['user_id'] = found_config.session_id
            session.modified = True 
            return jsonify({
                "success": True, 
                "message": "Joined successfully",
                "session_id": found_config.session_id,
                "config": found_config.to_dict()
            })
        else:
            return jsonify({"success": False, "message": "Kein aktiver Dienst mit diesem Passwort gefunden"}), 404
    except Exception as e:
        print(f"Join error: {e}")
        return jsonify({"success": False, "message": "Interner Fehler"}), 500

@app.route('/api/config', methods=['PUT'])
def update_config():
    sid = get_session_id()
    config = ShiftConfig.query.filter_by(is_active=True, session_id=sid).first()
    if not config:
        return jsonify({'error': 'No active shift'}), 404
    
    data = request.json
    changes = []
    
    if 'location' in data and data['location'] != config.location:
        config.location = data['location']
        changes.append("Einsatzort aktualisiert")
    
    if 'address' in data and data['address'] != config.address:
        config.address = data['address']
        changes.append("Adresse aktualisiert")

    if 'start_time' in data and data['start_time']:
        try:
            # Assume ISO format from frontend datetime-local or similar
            # If string is '2025-12-11T12:00', fromisoformat works
            new_start = datetime.fromisoformat(data['start_time'])
            if new_start != config.start_time:
                config.start_time = new_start
                changes.append("Dienstbeginn geändert")
        except ValueError:
            pass
            
    if 'end_time' in data:
        try:
            if data['end_time']:
                new_end = datetime.fromisoformat(data['end_time'])
                config.end_time = new_end
            else:
                config.end_time = None
            changes.append("Dienstende geändert")
        except ValueError:
            pass
            
    if changes:
        db.session.commit()
        log_action('KONFIGURATION', LogMessages.CONFIG_CHANGED.format(changes=', '.join(changes)))
    
    # Handle locations import
    if 'locations' in data and data['locations']:
        # Add new locations to existing ones (don't delete existing)
        existing_locs = {opt.value for opt in PredefinedOption.query.filter_by(category='location', session_id=sid).all()}
        new_count = 0
        for loc in data['locations']:
            if loc and loc not in existing_locs:
                db.session.add(PredefinedOption(category='location', value=loc, session_id=sid))
                new_count += 1
        
        if new_count > 0:
            db.session.commit()
            log_action('KONFIGURATION', f"{new_count} neue Einsatzorte hinzugefügt")
    
    return jsonify(config.to_dict())



@app.route('/api/squads', methods=['POST'])
def create_squad():
    data = request.json
    sid = get_session_id()
    if Squad.query.filter_by(name=data['name'], session_id=sid).first():
        return jsonify({'error': 'Squad exists'}), 400
    
    squad = Squad(
        name=data['name'], 
        qualification=data.get('qualification', 'San'), 
        type=data.get('type', 'Trupp'),
        service_numbers=data.get('service_numbers'),
        session_id=sid,
        access_token=str(uuid.uuid4())
    )
    db.session.add(squad)
    db.session.commit()
    dn_text = f", DN: {squad.service_numbers}" if squad.service_numbers else ""
    log_action('TRUPP NEU', LogMessages.SQUAD_CREATED.format(name=squad.name, qualification=squad.qualification, numbers=squad.service_numbers or "keine"), squad_id=squad.id)
    return jsonify(squad.to_dict()), 201

@app.route('/api/squads/<int:id>', methods=['PUT'])
def update_squad(id):
    sid = get_session_id()
    squad = Squad.query.filter_by(id=id, session_id=sid).first_or_404()
    data = request.json
    
    changes = []
    if 'name' in data and data['name'] != squad.name:
        changes.append(f"Name: {data['name']}")
        squad.name = data['name']
        
    if 'qualification' in data and data['qualification'] != squad.qualification:
        changes.append(f"Qual: {data['qualification']}")
        squad.qualification = data.get('qualification')

    if 'service_numbers' in data and data['service_numbers'] != squad.service_numbers:
        new_val = data.get('service_numbers') or "keine"
        changes.append(f"DN: {new_val}")
        squad.service_numbers = data.get('service_numbers')

    if 'custom_location' in data:
         new_val = data['custom_location'].strip() if data['custom_location'] else None
         if squad.current_status in ['3', '4'] and new_val:
             active_mission = None
             for m in squad.missions:
                 if m.status != 'Abgeschlossen' and not m.is_deleted:
                     active_mission = m
                     break
             
             if active_mission:
                 old_mission_loc = active_mission.location
                 if active_mission.initial_location is None:
                     active_mission.initial_location = old_mission_loc
                 
                 active_mission.location = new_val
                 changes.append(f"Einsatzort: {new_val} (via Trupp)")
                 squad.custom_location = None
             else:
                 squad.custom_location = new_val
         else:
             if new_val != squad.custom_location:
                 new_loc = new_val or "(Automatisch)"
                 changes.append(f"Standort: {new_loc}")
                 squad.custom_location = new_val


    if changes:
        db.session.commit()
        log_action('TRUPP UPDATE', LogMessages.SQUAD_UPDATED.format(name=squad.name, changes='; '.join(changes)), squad_id=squad.id)
        
    return jsonify(squad.to_dict())

@app.route('/api/squads/reorder', methods=['POST'])
def reorder_squads():
    sid = get_session_id()
    data = request.json
    # Expects list of {id: X, position: Y} or just list of IDs in order
    
    if 'order' in data: # List of IDs
        for idx, squad_id in enumerate(data['order']):
            squad = Squad.query.filter_by(id=squad_id, session_id=sid).first()
            if squad:
                squad.position = idx
        db.session.commit()
    
    return jsonify({'status': 'ok'})

@app.route('/api/squads/<int:id>', methods=['DELETE'])
def delete_squad(id):
    sid = get_session_id()
    squad = Squad.query.filter_by(id=id, session_id=sid).first_or_404()
    name = squad.name
    
    # Check if used in active missions? 
    # User might want to force delete. Let's just log it.
    # But database FK constraints might be an issue if we don't cascade.
    # The LogEntry has nullable squad_id, MissionSquad triggers cascade?
    # Helper for cleanliness: Remove associations first if needed.
    
    # Delete association rows manually if not cascaded by model (default is usually no cascade for many-to-many unless specified)
    db.session.execute(db.text("DELETE FROM mission_squad WHERE squad_id = :id"), {'id': id})
    
    db.session.delete(squad)
    db.session.commit()
    
    log_action('TRUPP GELÖSCHT', LogMessages.SQUAD_REMOVED.format(name=name))
    return jsonify({'status': 'deleted'})

@app.route('/api/squads/<int:id>/status', methods=['POST'])
def update_squad_status(id):
    # Support Token-Based Auth for Mobile (Fallback)
    token = request.args.get('token')
    if token:
        squad = Squad.query.filter_by(id=id, access_token=token).first_or_404()
        # CRITICAL: Restore session context for log_action and other logic
        session['user_id'] = squad.session_id
        session.modified = True
    else:
        sid = get_session_id()
        squad = Squad.query.filter_by(id=id, session_id=sid).first_or_404()
    
    data = request.json
    new_status = data.get('status')
    
    if new_status and new_status != squad.current_status:
        # VALIDATION FOR AMBULANZ
        if squad.type == 'Ambulanz':
            allowed_ambulanz_statuses = ['2', 'NEB', '4', '3']
            if new_status not in allowed_ambulanz_statuses:
                pass 

        old_status = squad.current_status
        squad.current_status = new_status
        squad.last_status_change = datetime.utcnow()
        
        # Auto-Clear Custom Location Logic refined
        if new_status == '2':
            # Find active mission context
            target_mission = None
            for m in squad.missions:
                if m.status != 'Abgeschlossen' and not m.is_deleted:
                    target_mission = m
                    break
            
            if not target_mission:
                completed_missions = [m for m in squad.missions if m.status == 'Abgeschlossen' and not m.is_deleted]
                if completed_missions:
                    completed_missions.sort(key=lambda x: x.id, reverse=True)
                    target_mission = completed_missions[0]

            if target_mission:
                if old_status in ['3', '4']:
                    squad.custom_location = target_mission.location
                elif old_status in ['7', '8']:
                     if not squad.custom_location:
                         # Default to BHP, but try to find assigned Ambulanz name first
                         found_loc = "BHP"
                         if target_mission and target_mission.squads:
                             for s in target_mission.squads:
                                 if s.type == "Ambulanz" and s.id != squad.id:
                                     found_loc = s.name
                                     break
                         squad.custom_location = found_loc

        try:
            db.session.commit()
        except Exception as e:
            print(f"Db Commit Error: {e}")
            return jsonify({'error': 'Database error'}), 500
        
        # Log logic
        try:
            active_mission_id = None
            for m in squad.missions:
                if m.status != 'Abgeschlossen':
                    active_mission_id = m.id
                    break
            
            old_label = STATUS_MAP.get(old_status, old_status)
            new_label = STATUS_MAP.get(new_status, new_status)
            log_action('STATUS', LogMessages.STATUS_CHANGED.format(name=squad.name, status=new_label), 
                       squad_id=squad.id, mission_id=active_mission_id)
        except Exception as e:
             print(f"Log Logging Error: {e}")
             # Swallow logging error to prevent client crash
             pass

        return jsonify(squad.to_dict())
    
    return jsonify(squad.to_dict())

@app.route('/api/missions', methods=['POST'])
def create_mission():
    data = request.json
    required = ['location', 'reason'] # Description not required anymore
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400

    new_mission = Mission(
        mission_number=data.get('mission_number'),
        location=data['location'],
        alarming_entity=data.get('alarming_entity'),
        reason=data['reason'],
        description=data.get('description', ''),
        outcome=data.get('outcome'),
        arm_notes=data.get('arm_notes', ''),
        notes=data.get('notes', ''),
        session_id=get_session_id()
    )
    
    # Handle Squads
    if 'squad_ids' in data:
        # Deduplicate IDs to prevent accidental double assignment
        unique_ids = set(data['squad_ids'])
        for sid in unique_ids:
            squad = Squad.query.filter_by(id=sid, session_id=get_session_id()).first()
            if squad:
                new_mission.squads.append(squad)
                # Auto-set status to Integriert (Alarmiert)
                if squad.current_status != 'Integriert' and squad.type != 'Ambulanz':
                    squad.current_status = 'Integriert'
                    squad.last_status_change = datetime.utcnow()
                    # Clear custom location so Mission Location takes precedence
                    squad.custom_location = None
                    
                    # Log status change explicitly
                    log_action('STATUS', f"{squad.name}: {LogMessages.DISPATCHED_AUTO.format(number=new_mission.mission_number or new_mission.id)}", 
                               squad_id=squad.id, mission_id=new_mission.id)

                elif squad.type == 'Ambulanz':
                    # For Ambulanz, just log assignment, don't change status to 'Integriert'
                    log_action('INFO', f"{squad.name}: {LogMessages.PATIENT_ASSIGNED}", 
                               squad_id=squad.id, mission_id=new_mission.id)
    
    db.session.add(new_mission)
    db.session.commit()
    
    log_action('EINSATZ ERSTELLT', LogMessages.MISSION_CREATED.format(number=new_mission.mission_number or new_mission.id, reason=new_mission.reason, location=new_mission.location), mission_id=new_mission.id)
    
    # Auto-update Ambulanz status
    for s in new_mission.squads:
        update_ambulanz_occupancy(s)
        
    return jsonify(new_mission.to_dict()), 201

@app.route('/api/missions/<int:id>', methods=['PUT'])
def update_mission(id):
    sid_val = get_session_id()
    mission = Mission.query.filter_by(id=id, session_id=sid_val, is_deleted=False).first_or_404()
    data = request.json
    
    changes = []
    
    if 'status' in data and data['status'] != mission.status:
        changes.append(f"Status geändert: {data['status']}")
        mission.status = data['status']
    
    if 'outcome' in data and data['outcome'] != mission.outcome:
        new_val = data['outcome'] or ""
        mission.outcome = data['outcome']
        
        current_arm_id = data.get('arm_id', mission.arm_id)
        if (mission.outcome in ['ARM', 'ARM (Anderes Rettungsmittel)']) and current_arm_id:
             changes.append(f"Ausgang: ARM ({current_arm_id})")
        else:
             changes.append(f"Ausgang: {new_val}")
        
    if 'arm_id' in data and data['arm_id'] != mission.arm_id:
        new_val = data['arm_id'] or ""
        if mission.outcome not in ['ARM', 'ARM (Anderes Rettungsmittel)']: # Only log if not covered by outcome log
             changes.append(f"ARM-ID: {new_val}")
        mission.arm_id = data['arm_id']

    if 'arm_type' in data and data['arm_type'] != mission.arm_type:
        new_val = data['arm_type'] or ""
        changes.append(f"ARM-Typ: {new_val}")
        mission.arm_type = data['arm_type']

    if 'arm_notes' in data and data['arm_notes'] != mission.arm_notes:
        changes.append("Übergabe-Notiz aktualisiert")
        mission.arm_notes = data['arm_notes']
    
    # Prepare Deferred Squad Updates
    squads_to_update_status = []
    
    if 'squad_ids' in data:
        # Update roster
        current_ids = {s.id for s in mission.squads}
        new_ids = set(data['squad_ids'])
        if current_ids != new_ids:
            # Calculate diff
            added_ids = new_ids - current_ids
            removed_ids = current_ids - new_ids
            
            added_names = []
            for sid in added_ids:
                sq = Squad.query.filter_by(id=sid, session_id=sid_val).first()
                if sq: added_names.append(sq.name)

            removed_names = []
            for sid in removed_ids:
                sq = Squad.query.filter_by(id=sid, session_id=sid_val).first()
                if sq: removed_names.append(sq.name)
            
            diff_parts = []
            if added_names:
                diff_parts.append(f"+ {', '.join(added_names)}")
            if removed_names:
                diff_parts.append(f"- {', '.join(removed_names)}")
            
            changes.append(f"Trupps: {'; '.join(diff_parts)}")

            # Update Relationship
            mission.squads = []
            for sid in new_ids:
                s = Squad.query.filter_by(id=sid, session_id=sid_val).first()
                if s: 
                    mission.squads.append(s)
                    # Defer status change to ensure log order
                    if sid not in current_ids:
                         s.custom_location = None
                         squads_to_update_status.append(s)

    # Handle description separately to include content in log
    if 'description' in data and mission.description != data['description']:
        changes.append("Lage aktualisiert")
        mission.description = data['description']
    
    if 'notes' in data and mission.notes != data['notes']:
        if data['notes'] and not mission.notes:
             changes.append(LogMessages.NOTE_ADDED) # Less spam
        mission.notes = data['notes']

    # Handle other fields
    field_map = {
        'location': 'Ort',
        'reason': 'Stichwort',
        'mission_number': 'Nr.',
        'alarming_entity': 'Alarmierung'
    }
    
    # Handle Location Change specifically to save initial_location
    if 'location' in data and data['location'] != mission.location:
         if not mission.initial_location:
             mission.initial_location = mission.location
    
    for f, label in field_map.items():
        if f in data and getattr(mission, f) != data[f]:
            new_val = data[f] or "(leer)"
            changes.append(f"{label}: {new_val}")
            setattr(mission, f, data[f])
            
    if 'notes' in data and mission.notes != data['notes']:
        old_val = mission.notes
        new_val = data['notes'] or "(leer)"
        if not old_val:
            changes.append(f"{LogMessages.NOTE_ADDED}: {new_val}")
        else:
            changes.append(f"Notiz geändert: {old_val} zu {new_val}")
        mission.notes = data['notes']

    # Commit Mission Updates First
    if changes:
        db.session.commit()
        m_num = mission.mission_number or mission.id
        # Log Mission Update
        log_action('EINSATZ UPDATE', LogMessages.MISSION_UPDATED.format(number=m_num, changes='; '.join(changes)), mission_id=mission.id)
    
    # Process Deferred Squad Status Updates (logs will appear AFTER mission update)
    if squads_to_update_status:
        for s in squads_to_update_status:
             if s.current_status != 'Integriert':
                old_status = s.current_status # Not used in simple log, but good to know
                s.current_status = 'Integriert'
                s.last_status_change = datetime.utcnow()
                db.session.commit() # Commit each status change
                log_action('STATUS', f"{s.name}: Status auf {STATUS_MAP.get('Integriert', 'Integriert')} gesetzt", 
                           squad_id=s.id, mission_id=mission.id)

    # Auto-update Ambulanz status (Check all current squads)
    for s in mission.squads:
        update_ambulanz_occupancy(s)

    return jsonify(mission.to_dict())

@app.route('/api/missions/<int:id>', methods=['DELETE'])
def delete_mission(id):
    sid = get_session_id()
    mission = Mission.query.filter_by(id=id, session_id=sid).first_or_404()
    
    data = request.json or {}
    reason = data.get('reason', 'Keine Begründung')
    
    log_action('EINSATZ GELÖSCHT', LogMessages.MISSION_DELETED.format(number=mission.mission_number or mission.id, reason=reason), mission_id=mission.id)
    
    # Soft Delete instead of hard delete
    mission.is_deleted = True
    mission.deletion_reason = reason
    
    # We don't remove squad associations so we can still see who was assigned in history,
    # but for active squad view we need to ensure we don't pick up deleted missions.
    
    db.session.commit()
    
    return jsonify({'status': 'deleted'})

@app.route('/api/changes', methods=['GET'])
def get_changes():
    sid = get_session_id()
    logs = LogEntry.query.filter_by(session_id=sid).order_by(LogEntry.timestamp.desc()).all()
    return jsonify([l.to_dict() for l in logs])

# --- Helper Functions --- (Appending to previous helper section logically, but placing here for context)

def generate_export_file(config):
    output = io.StringIO()
    sid = config.session_id if config else get_session_id()

    # Helper for local time conversion
    def to_local(dt_obj):
        if not dt_obj:
            return None
        # Assume server local time is desired
        # UTC -> Local System Time
        return dt_obj.replace(tzinfo=timezone.utc).astimezone(None)
    
    # Header
    output.write(f"{LogMessages.REPORT_TITLE_TXT}\n")
    if config:
        output.write(f"{LogMessages.LBL_SERVICE} {config.location}\n")
        if config.address:
            output.write(f"{LogMessages.LBL_ADDRESS} {config.address}\n")
        
        # Format times nicely
        s_local = to_local(config.start_time)
        e_local = to_local(config.end_time)
        
        s_str = s_local.strftime('%d.%m.%Y %H:%M') if s_local else '?'
        e_str = e_local.strftime('%d.%m.%Y %H:%M') if e_local else 'Laufend'
        
        output.write(f"{LogMessages.LBL_PERIOD} {s_str} - {e_str}\n")
    output.write("\n")
    
    # Missions
    missions = Mission.query.filter_by(session_id=sid).order_by(Mission.created_at).all()
    output.write(f"=== {LogMessages.SECTION_MISSIONS} ({len(missions)}) ===\n\n")
    
    for m in missions:
        output.write(f"{LogMessages.LBL_MISSION_NUM.format(number=m.mission_number or m.id)}\n")
        
        # Show start time and end time (if completed)
        start_local = to_local(m.created_at)
        start_time = start_local.strftime('%d.%m.%Y %H:%M:%S') if start_local else '?'
        
        if m.status == 'Abgeschlossen':
            # Find the completion time from logs
            m_logs = LogEntry.query.filter_by(mission_id=m.id, action='EINSATZ UPDATE', session_id=sid).order_by(LogEntry.timestamp.desc()).all()
            end_time = 'Abgeschlossen'
            for l in m_logs:
                if 'Status: Laufend -> Abgeschlossen' in (l.details or "") or 'auf Abgeschlossen' in (l.details or ""):
                    end_local = to_local(l.timestamp)
                    end_time = end_local.strftime('%d.%m.%Y %H:%M:%S')
                    break
            
            outcome_display = m.outcome
            if m.outcome == 'ARM' or m.outcome == 'Übergeben' or m.outcome == 'ARM (Anderes Rettungsmittel)' or (m.outcome and m.outcome.startswith('Übergeben')):
                basic = "Übergeben"
                parts = []
                if m.arm_type: parts.append(m.arm_type)
                if m.arm_id: parts.append(m.arm_id)
                if m.arm_notes: parts.append(m.arm_notes)
                
                if parts:
                    outcome_display = f"{basic} / {' / '.join(parts)}"
                else:
                    outcome_display = basic
                
            output.write(f"{LogMessages.LBL_TIME} {start_time} - {end_time} ({outcome_display})\n")
        else:
            output.write(f"{LogMessages.LBL_TIME} {start_time} - Laufend\n")
        
        output.write(f"{LogMessages.LBL_LOCATION} {m.location}\n")
        output.write(f"{LogMessages.LBL_REASON} {m.reason}\n")
        val_entity = m.alarming_entity or "-"
        output.write(f"{LogMessages.LBL_ALARMING}: {val_entity}\n")
        output.write(f"{LogMessages.LBL_SQUADS}: {', '.join([s.name for s in m.squads])}\n")
        
        if m.description:
            output.write(f"{LogMessages.LBL_SITUATION} {m.description}\n")
        if m.notes:
            output.write(f"{LogMessages.LBL_NOTES} {m.notes}\n")
        
        # Chronology of this mission
        m_logs = LogEntry.query.filter_by(mission_id=m.id).order_by(LogEntry.timestamp).all()
        if m_logs:
            output.write(f"  {LogMessages.LBL_HISTORY}\n")
            for l in m_logs:
                # Clean up log details "None"
                safe_details = l.details.replace("None", "(leer)") if l.details else ""
                cur_local = to_local(l.timestamp)
                ts_str = cur_local.strftime('%H:%M:%S') if cur_local else "?"
                output.write(f"  - [{ts_str}] {l.action}: {safe_details}\n")
        
        output.write("-" * 40 + "\n\n")

    # Squad Activity / Pause Analysis
    output.write(f"=== {LogMessages.SECTION_SQUADS} ===\n\n")
    squads = Squad.query.filter_by(session_id=sid).all()
    for s in squads:
        # Count missions for this squad
        mission_count = len([m for m in s.missions])
        
        sn_text = f" [DN: {s.service_numbers}]" if s.service_numbers else ""
        output.write(f"Trupp: {s.name} ({s.qualification}){sn_text} - {mission_count} Einsätze\n")
        s_logs = LogEntry.query.filter_by(squad_id=s.id).order_by(LogEntry.timestamp).all()
        
        # Track pause periods (start and end times)
        pause_periods = []
        pause_start = None
        
        for l in s_logs:
            safe_details = l.details.replace("None", "(leer)") if l.details else ""
            
            cur_local = to_local(l.timestamp)
            ts_str = cur_local.strftime('%H:%M:%S') if cur_local else "?"
            
            if l.action == 'STATUS':
                # Add mission context if available
                mission_context = ""
                if l.mission_id:
                    mission = Mission.query.filter_by(id=l.mission_id, session_id=sid).first()
                    if mission:
                        mission_num = mission.mission_number or mission.id
                        mission_context = f" (Einsatz #{mission_num})"
                
                output.write(f"  [{ts_str}] {safe_details}{mission_context}\n")
                
                # Check if status changed to Pause
                if '-> Pause' in l.details:
                    pause_start = cur_local
                # Check if status changed from Pause to something else
                elif pause_start and 'Pause ->' in l.details:
                    pause_end = cur_local
                    pause_periods.append(f"{pause_start.strftime('%H:%M:%S')} - {pause_end.strftime('%H:%M:%S')}")
                    pause_start = None
        
        # If pause is still ongoing (no end time)
        if pause_start:
            pause_periods.append(f"{pause_start.strftime('%H:%M:%S')} - laufend")
        
        # Summary of pauses
        if pause_periods:
            output.write(f"  {LogMessages.LBL_PAUSES}: {'; '.join(pause_periods)}\n")
        output.write("\n")
    
    # Full Log
    output.write(f"=== {LogMessages.SECTION_LOG} ===\n")
    all_logs = LogEntry.query.filter_by(session_id=sid).order_by(LogEntry.timestamp).all()
    for l in all_logs:
        safe_details = l.details.replace("None", "(leer)") if l.details else ""
        l_local = to_local(l.timestamp)
        ts_full = l_local.strftime('%Y-%m-%d %H:%M:%S') if l_local else "?"
        output.write(f"[{ts_full}] [{l.action}] {safe_details}\n")
        
    output.write("\n")

    # Deleted Missions
    deleted_missions = Mission.query.filter_by(session_id=sid, is_deleted=True).order_by(Mission.created_at).all()
    if deleted_missions:
        output.write(f"=== {LogMessages.SECTION_DELETED} ===\n\n")
        for m in deleted_missions:
            m_num = m.mission_number or m.id
            output.write(f"{LogMessages.LBL_MISSION_NUM.format(number=m_num)} ({m.location})\n")
            val_reason = m.deletion_reason or "-"
            output.write(f"  {LogMessages.LBL_DELETE_REASON} {val_reason}\n")
            output.write(f"  {LogMessages.LBL_ORIGINAL_ALARM} {m.reason}\n")
            if m.description:
                output.write(f"  {LogMessages.LBL_SITUATION} {m.description}\n")
            
            # Add logs for deleted mission context
            m_logs = LogEntry.query.filter_by(mission_id=m.id).order_by(LogEntry.timestamp).all()
            if m_logs:
                output.write(f"  {LogMessages.LBL_HISTORY}\n")
                for l in m_logs:
                     safe_details = l.details.replace("None", "(leer)") if l.details else ""
                     l_local = to_local(l.timestamp)
                     ts_str = l_local.strftime('%H:%M:%S') if l_local else "?"
                     output.write(f"  - [{ts_str}] {l.action}: {safe_details}\n")
            output.write("\n")

    # Convert to bytes
    mem = io.BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)
    
    return mem

@app.route('/api/export', methods=['GET'])
def export_data():
    sid = get_session_id()
    config = ShiftConfig.query.filter_by(is_active=True, session_id=sid).first()
    # Check if there is no active config, maybe get the last one?
    # For manual export button, usually we want current.
    # If no active config, maybe try to find the last created one.
    if not config:
        config = ShiftConfig.query.filter_by(session_id=sid).order_by(ShiftConfig.id.desc()).first()
        
    mem = generate_export_file(config)
    filename = f"protokoll_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    return send_file(mem, as_attachment=True, download_name=filename, mimetype='text/plain')

@app.route('/api/config/end', methods=['POST'])
def end_shift():
    sid = get_session_id()
    config = ShiftConfig.query.filter_by(is_active=True, session_id=sid).first()
    if config:
        config.is_active = False
        config.end_time = datetime.utcnow()
        config.end_time = datetime.utcnow()
        # Cleanup Access Tokens
        Squad.query.filter_by(session_id=sid).update({Squad.access_token: None})
        db.session.commit()
        log_action('KONFIGURATION', LogMessages.SHIFT_ENDED.format(location=config.location))
        
    # Reset predefined options to default values
    PredefinedOption.query.filter_by(session_id=sid).delete()
    
    # Load default options from file if it exists
    default_file = 'default_options.txt'
    if os.path.exists(default_file):
        try:
            with open(default_file, 'r', encoding='utf-8') as f:
                current_category = None
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):  # Skip empty lines and comments
                        continue
                    
                    # Check if this is a category header
                    if line.startswith('[') and line.endswith(']'):
                        current_category = line[1:-1].lower()
                    elif current_category in ['location', 'entity', 'reason']:
                        db.session.add(PredefinedOption(category=current_category, value=line, session_id=sid))
        except Exception as e:
            print(f"Error loading default options: {e}")
    
    db.session.commit()
        
    # Generate export (even if config was None/already ended, try to get last)
    # Re-fetch or reuse config object (which is now inactive).
    if not config:
         config = ShiftConfig.query.filter_by(session_id=sid).order_by(ShiftConfig.id.desc()).first()
         
    mem = generate_export_file(config)
    filename = f"abschluss_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    return send_file(mem, as_attachment=True, download_name=filename, mimetype='text/plain')



def generate_pdf_file(config):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []
    sid = config.session_id if config else get_session_id()
    
    # Styles
    title_style = styles['Title']
    heading2 = styles['Heading2']
    heading3 = styles['Heading3']
    normal_style = styles['Normal']
    small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=8, leading=10)
    
    # Title
    story.append(Paragraph(LogMessages.REPORT_TITLE_PDF, title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Shift Info
    s_str = config.start_time.strftime('%d.%m.%Y %H:%M') if config and config.start_time else '?'
    e_str = config.end_time.strftime('%d.%m.%Y %H:%M') if config and config.end_time else 'Laufend'
    loc = config.location if config else 'Unbekannt'
    addr = config.address if config and config.address else '-'
    
    info_data = [
        [f"{LogMessages.LBL_SERVICE}", loc, f"{LogMessages.LBL_ADDRESS}", addr],
        [f"{LogMessages.LBL_PERIOD}", f"{s_str} - {e_str}", "", ""]
    ]
    t = Table(info_data, colWidths=[3*cm, 8*cm, 3*cm, 8*cm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'), # Labels bold
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
    ]))
    story.append(t)
    story.append(Spacer(1, 1*cm))
    
    # Statistics Calculation
    valid_missions = Mission.query.filter_by(session_id=sid, is_deleted=False).order_by(Mission.created_at).all()
    
    # Graphs
    # 1. Missions per Hour
    hours = {}
    for m in valid_missions:
        if m.created_at:
            h = m.created_at.strftime('%H:00')
            hours[h] = hours.get(h, 0) + 1
    
    sorted_hours = sorted(hours.keys())
    counts = [hours[h] for h in sorted_hours]
    
    # Plotting
    if valid_missions:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
        
        # Bar Chart
        if sorted_hours:
            ax1.bar(sorted_hours, counts, color='skyblue')
            ax1.set_title('Einsätze pro Stunde')
            ax1.set_xlabel('Uhrzeit')
            ax1.set_ylabel('Anzahl')
        else:
            ax1.text(0.5, 0.5, 'Keine Daten', ha='center', va='center')

        # Pie Chart (Reasons)
        reasons = {}
        for m in valid_missions:
            reasons[m.reason] = reasons.get(m.reason, 0) + 1
        
        if reasons:
            ax2.pie(reasons.values(), labels=reasons.keys(), autopct='%1.1f%%', startangle=90)
            ax2.set_title('Einsatzarten')
        else:
            ax2.text(0.5, 0.5, 'Keine Daten', ha='center', va='center')
        
        plt.tight_layout()
        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png')
        plt.close(fig)
        img_buf.seek(0)
        
        img = RLImage(img_buf, width=20*cm, height=8*cm)
        story.append(img)
        story.append(Spacer(1, 1*cm))

    # Response Times
    response_times = []
    for m in valid_missions:
        logs = LogEntry.query.filter_by(mission_id=m.id, session_id=sid).all()
        arrived_time = None
        for l in logs:
            if '-> BO' in (l.details or "") or '-> 4' in (l.details or ""): 
                 arrived_time = l.timestamp
                 break
        
        if arrived_time and m.created_at:
            delta = (arrived_time - m.created_at).total_seconds() / 60.0 # Minutes
            if delta > 0:
                response_times.append(delta)

    if response_times:
         avg_resp = sum(response_times) / len(response_times)
         story.append(Paragraph(f"Durchschnittliche Response Time (Disponiert -> BO): {avg_resp:.1f} Minuten", normal_style))
         story.append(Spacer(1, 0.5*cm))

    # Detailed Missions
    story.append(Paragraph("Einsatz-Details", heading2))
    story.append(Spacer(1, 0.2*cm))

    for m in valid_missions:
        m_num = m.mission_number or str(m.id)
        story.append(Paragraph(LogMessages.LBL_MISSION_NUM.format(number=m_num), heading3))
        
        # Details Table for this mission
        start_t = m.created_at.strftime('%d.%m.%Y %H:%M:%S') if m.created_at else "?"
        
        # Determine End Time
        end_time = "Laufend"
        if m.status == 'Abgeschlossen':
            m_logs = LogEntry.query.filter_by(mission_id=m.id, action='EINSATZ UPDATE', session_id=sid).order_by(LogEntry.timestamp.desc()).all()
            end_time = "Abgeschlossen"
            for l in m_logs:
                if 'Status: Laufend -> Abgeschlossen' in (l.details or "") or 'auf Abgeschlossen' in (l.details or ""):
                    end_time = l.timestamp.strftime('%d.%m.%Y %H:%M:%S')
                    break

        outcome = m.outcome or "-"
        if (m.outcome == 'ARM' or m.outcome == 'ARM (Anderes Rettungsmittel)') and m.arm_id:
             outcome = f"ARM {m.arm_id}"

        # Location Display with History
        loc_display = m.location
        if m.initial_location and m.initial_location != m.location:
            loc_display = f"{m.location} (Initial: {m.initial_location})"

        det_data = [
            [f"{LogMessages.LBL_TIME}", f"{start_t} - {end_time}", f"{LogMessages.LBL_OUTCOME}", outcome],
            [f"{LogMessages.LBL_LOCATION}", Paragraph(loc_display, normal_style), f"{LogMessages.LBL_ALARMING}:", m.alarming_entity or "-"],
            [f"{LogMessages.LBL_REASON}", Paragraph(m.reason, normal_style), f"{LogMessages.LBL_SQUADS}:", ", ".join([s.name for s in m.squads])]
        ]
        
        # Add description and notes if present
        if m.description:
             det_data.append([f"{LogMessages.LBL_SITUATION}", Paragraph(m.description, normal_style), "", ""])
        if m.notes:
             det_data.append([f"{LogMessages.LBL_NOTES}", Paragraph(m.notes, normal_style), "", ""])

        dt = Table(det_data, colWidths=[2*cm, 9*cm, 3*cm, 9*cm])
        dt.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ]))
        story.append(dt)
        
        # Mission Log
        m_logs = LogEntry.query.filter_by(mission_id=m.id).order_by(LogEntry.timestamp).all()
        if m_logs:
            story.append(Spacer(1, 0.2*cm))
            story.append(Paragraph(LogMessages.LBL_HISTORY, styles['Normal']))
            log_data = []
            for l in m_logs:
                safe_details = l.details.replace("None", "(leer)") if l.details else ""
                log_data.append([
                    l.timestamp.strftime('%H:%M:%S'),
                    l.action,
                    Paragraph(safe_details, small_style)
                ])
            
            lt = Table(log_data, colWidths=[2*cm, 4*cm, 16*cm])
            lt.setStyle(TableStyle([
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            story.append(lt)
            
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph("-" * 120, small_style)) # Separator
        story.append(Spacer(1, 0.5*cm))

    # Squad Activity
    story.append(PageBreak())
    story.append(Paragraph(LogMessages.SECTION_SQUADS, heading2))
    
    squads = Squad.query.filter_by(session_id=sid).all()
    for s in squads:
        mission_count = len([m for m in s.missions])
        sn_text = f" [DN: {s.service_numbers}]" if s.service_numbers else ""
        story.append(Paragraph(f"Trupp: {s.name} ({s.qualification}){sn_text} - {mission_count} Einsätze", heading3))
        
        s_logs = LogEntry.query.filter_by(squad_id=s.id).order_by(LogEntry.timestamp).all()
        
        # Logs list
        squad_log_data = []
        
        # Pause Calculation vars
        pause_periods = []
        pause_start = None
        
        for l in s_logs:
            safe_details = l.details.replace("None", "(leer)") if l.details else ""
            
            # Pause Calculation Logic
            # Check for Status Change log entries
            if l.action == 'STATUS':
                # Example detail: "Alpha: Statuswechsel von Einsatzbereit auf Pause"
                # We need to detect "auf Pause" (Start) and "von Pause" (End)
                # Or based on status codes if we logged them, but we satisfy with text matching since we standardized logs.
                # Actually, our standardized logs are "Statuswechsel von X auf Y".
                
                if "auf Pause" in safe_details:
                    if pause_start is None:
                        pause_start = l.timestamp
                
                if "von Pause" in safe_details:
                    if pause_start:
                        p_end = l.timestamp
                        duration = int((p_end - pause_start).total_seconds() / 60)
                        pause_periods.append(f"{pause_start.strftime('%H:%M')} - {p_end.strftime('%H:%M')} ({duration} Min.)")
                        pause_start = None # Reset
            
            # Format display log
            mission_context = ""
            if l.mission_id:
                mis = Mission.query.filter_by(id=l.mission_id, session_id=sid).first()
                if mis:
                     m_num = mis.mission_number or mis.id
                     mission_context = f" (Einsatz #{m_num})"
            
            squad_log_data.append([
                l.timestamp.strftime('%H:%M:%S'),
                Paragraph(f"{safe_details}{mission_context}", small_style)
            ])
            
        # Check if still in pause at end of log
        if pause_start:
             pause_periods.append(f"{pause_start.strftime('%H:%M')} - ... (laufend)")

        # Display Pause Summary
        if pause_periods:
            story.append(Paragraph(f"<b>{LogMessages.LBL_PAUSES}:</b> {', '.join(pause_periods)}", normal_style))
            story.append(Spacer(1, 0.2*cm))
        else:
             if len(mission_count_list := [m for m in s.missions]) > 0: # Just to not clutter empty squads
                  story.append(Paragraph(LogMessages.LBL_NO_PAUSES, normal_style))
                  story.append(Spacer(1, 0.2*cm))

        if squad_log_data:
            slt = Table(squad_log_data, colWidths=[2.5*cm, 18*cm])
            slt.setStyle(TableStyle([
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.whitesmoke, colors.white])
            ]))
            story.append(slt)
        
        story.append(Spacer(1, 0.5*cm))

    # Full Log
    story.append(PageBreak())
    story.append(Paragraph(LogMessages.SECTION_LOG, heading2))
    
    all_logs = LogEntry.query.filter_by(session_id=sid).order_by(LogEntry.timestamp).all()
    full_log_data = [["Zeit", "Aktion", "Details"]]
    for l in all_logs:
        safe_details = l.details.replace("None", "(leer)") if l.details else ""
        full_log_data.append([
            l.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            l.action,
            Paragraph(safe_details, small_style)
        ])
    
    flt = Table(full_log_data, colWidths=[4*cm, 4*cm, 18*cm], repeatRows=1)
    flt.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    story.append(flt)

    # Deleted Missions
    deleted_missions = Mission.query.filter_by(session_id=sid, is_deleted=True).order_by(Mission.created_at).all()
    if deleted_missions:
        story.append(PageBreak())
        story.append(Paragraph(LogMessages.SECTION_DELETED, heading2))
        
        for m in deleted_missions:
             m_num = m.mission_number or str(m.id)
             story.append(Paragraph(f"{LogMessages.LBL_MISSION_NUM.format(number=m_num)} ({m.location})", heading3))
             story.append(Paragraph(f"{LogMessages.LBL_DELETE_REASON} {m.deletion_reason or '-'}", normal_style))
             story.append(Spacer(1, 0.2*cm))
             
             # Logs for deleted mission
             m_logs = LogEntry.query.filter_by(mission_id=m.id).order_by(LogEntry.timestamp).all()
             if m_logs:
                 del_log_data = []
                 for l in m_logs:
                    safe_details = l.details.replace("None", "(leer)") if l.details else ""
                    del_log_data.append([
                        l.timestamp.strftime('%H:%M:%S'),
                        l.action,
                        Paragraph(safe_details, small_style)
                    ])
                 dlt = Table(del_log_data, colWidths=[2*cm, 4*cm, 16*cm])
                 dlt.setStyle(TableStyle([('FONTSIZE', (0,0), (-1,-1), 8), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
                 story.append(dlt)
             
             story.append(Spacer(1, 0.5*cm))

    doc.build(story)
    buffer.seek(0)
    return buffer
@app.route('/api/export/pdf', methods=['GET'])
def export_pdf():
    sid = get_session_id()
    config = ShiftConfig.query.filter_by(is_active=True, session_id=sid).first()
    if not config:
        config = ShiftConfig.query.filter_by(session_id=sid).order_by(ShiftConfig.id.desc()).first()
        
    mem = generate_pdf_file(config)
    filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return send_file(mem, as_attachment=True, download_name=filename, mimetype='application/pdf')

# --- Mobile View Route ---
@app.route('/squad/mobile-view', methods=['GET'])
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

    
@app.route('/api/logs/custom', methods=['POST'])
def custom_log():
    data = request.json
    details = data.get('details')
    if not details:
        return jsonify({'error': 'Details required'}), 400
    
    # Log as 'EREIGNIS'
    log_action('EREIGNIS', details)
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    with app.app_context():
        # Auto-create DB if not exists, but we rely on a manual reset or Init API for clean slate usually
        db.create_all()
    app.run(debug=True, port=5001)

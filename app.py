# Mission Control - Backend (Reload Triggered)
from flask import Flask, render_template, request, jsonify, send_file, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import io
import csv
import os
import uuid

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

    def to_dict(self):
        return {
            'location': self.location,
            'address': self.address,
            'start_time': (self.start_time.isoformat() + 'Z') if self.start_time else None,
            'end_time': (self.end_time.isoformat() + 'Z') if self.end_time else None,
            'is_active': self.is_active
        }

class Squad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    qualification = db.Column(db.String(20), default='San') # San, RS, NFS, NA
    current_status = db.Column(db.String(20), default='2') # 2 (EB), 3, 4, 7, 8
    position = db.Column(db.Integer, default=0)
    session_id = db.Column(db.String(100), nullable=False)

    __table_args__ = (db.UniqueConstraint('name', 'session_id', name='_name_session_uc'),)
    last_status_change = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    missions = db.relationship('Mission', secondary=mission_squad, back_populates='squads')
    
    def to_dict(self):
        # Find active mission for this squad
        # Prefer latest mission if multiple are active
        active_missions = [m for m in self.missions if m.status != 'Abgeschlossen' and not m.is_deleted]
        active_missions.sort(key=lambda x: x.created_at, reverse=True)
        
        active_mission = None
        if active_missions:
            m = active_missions[0]
            active_mission = {
                'id': m.id,
                'mission_number': m.mission_number,
                'location': m.location,
                'reason': m.reason
            }

        return {
            'id': self.id,
            'name': self.name,
            'qualification': self.qualification,
            'current_status': self.current_status,
            'position': self.position,
            'last_status_change': (self.last_status_change.isoformat() + 'Z') if self.last_status_change else None,
            'active_mission': active_mission
        }

class Mission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mission_number = db.Column(db.String(50), nullable=True) # Manual Entry
    location = db.Column(db.String(200), nullable=False)
    alarming_entity = db.Column(db.String(200), nullable=True)
    reason = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Laufend') # Laufend, Abgeschlossen
    outcome = db.Column(db.String(50), nullable=True) # Inter Unter, Belassen, ARM, PVW
    arm_id = db.Column(db.String(50), nullable=True)  # Kennung if ARM
    arm_type = db.Column(db.String(50), nullable=True) # Typ if ARM
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
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
            'alarming_entity': self.alarming_entity,
            'squads': [{'name': s.name, 'id': s.id, 'status': s.current_status} for s in self.squads],
            'squad_ids': [s.id for s in self.squads],
            'reason': self.reason,
            'description': self.description,
            'status': self.status,
            'outcome': self.outcome,
            'arm_id': self.arm_id,
            'arm_type': self.arm_type,
            'notes': self.notes,
            'created_at': (self.created_at.isoformat() + 'Z') if self.created_at else None
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
            'timestamp': self.timestamp.isoformat(),
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
    '1': 'Frei'
}

def get_session_id():
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
        sid = get_session_id()
        # simplified long polling check
        squads = Squad.query.filter_by(session_id=sid).order_by(Squad.position).all()
        missions = Mission.query.filter_by(session_id=sid, is_deleted=False).order_by(Mission.created_at.desc()).all()
        logs = LogEntry.query.filter_by(session_id=sid).order_by(LogEntry.timestamp.desc()).limit(50).all()
        
        return jsonify({
            'squads': [s.to_dict() for s in squads],
            'missions': [m.to_dict() for m in missions],
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

    new_config = ShiftConfig(
        location=data.get('location', ''),
        address=data.get('address', ''),
        start_time=start_dt,
        session_id=sid
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
        Squad.query.filter_by(session_id=sid).delete()
        Mission.query.filter_by(session_id=sid).delete()
        LogEntry.query.filter_by(session_id=sid).delete()
        # Note: mission_squad association table cleanup is trickier without session_id on it directly, 
        # but deleting missions/squads should cascade or leave orphans if we don't care. 
        # A clean way is:
        # db.session.execute(mission_squad.delete()) # This deletes ALL associations!
        # We need to only delete for squads in this session.
        # But for now, let's assume we are resetting everything for this user.
        # Since we just deleted all squads for this sid, the associations are invalid.
        # Ideally, we should clean them up, but SQLite might leave them.
        
        for s in data['squads']:
            new_squad = Squad(name=s['name'], qualification=s.get('qualification', 'San'), session_id=sid)
            db.session.add(new_squad)

    db.session.commit()
    log_action('KONFIGURATION', f"Dienst gestartet. Ort: {new_config.location}")
    return jsonify(new_config.to_dict())

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
        log_action('KONFIGURATION', f"Einstellungen geändert: {', '.join(changes)}")
    
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
    
    squad = Squad(name=data['name'], qualification=data.get('qualification', 'San'), session_id=sid)
    db.session.add(squad)
    db.session.commit()
    log_action('TRUPP NEU', f"{squad.name} ({squad.qualification})", squad_id=squad.id)
    return jsonify(squad.to_dict()), 201

@app.route('/api/squads/<int:id>', methods=['PUT'])
def update_squad(id):
    sid = get_session_id()
    squad = Squad.query.filter_by(id=id, session_id=sid).first_or_404()
    data = request.json
    
    changes = []
    if 'name' in data and data['name'] != squad.name:
        changes.append(f"Name: {squad.name} -> {data['name']}")
        squad.name = data['name']
        
    if 'qualification' in data and data['qualification'] != squad.qualification:
        changes.append(f"Qual: {squad.qualification} -> {data['qualification']}")
        squad.qualification = data.get('qualification')

    if changes:
        db.session.commit()
        log_action('TRUPP UPDATE', f"{squad.name} bearbeitet: {', '.join(changes)}", squad_id=squad.id)
        
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
    db.session.execute(mission_squad.delete().where(mission_squad.c.squad_id == id))
    
    db.session.delete(squad)
    db.session.commit()
    
    log_action('TRUPP GELÖSCHT', f"{name}")
    return jsonify({'status': 'deleted'})

@app.route('/api/squads/<int:id>/status', methods=['POST'])
def update_squad_status(id):
    sid = get_session_id()
    squad = Squad.query.filter_by(id=id, session_id=sid).first_or_404()
    data = request.json
    new_status = data.get('status')
    
    if new_status and new_status != squad.current_status:
        old_status = squad.current_status
        squad.current_status = new_status
        squad.last_status_change = datetime.utcnow()
        db.session.commit()
        
        # Log logic: if squad is in an active mission, allow logging that linkage
        # But a squad can be in multiple missions? Usually one active mission.
        active_mission_id = None
        for m in squad.missions:
            if m.status != 'Abgeschlossen':
                active_mission_id = m.id
                break
        
        old_label = STATUS_MAP.get(old_status, old_status)
        new_label = STATUS_MAP.get(new_status, new_status)
        log_action('STATUS', f"{squad.name}: {old_label} -> {new_label}", 
                   squad_id=squad.id, mission_id=active_mission_id)
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
        notes=data.get('notes', ''),
        session_id=get_session_id()
    )
    
    # Handle Squads
    if 'squad_ids' in data:
        for sid in data['squad_ids']:
            squad = Squad.query.get(sid)
            if squad:
                new_mission.squads.append(squad)
    
    db.session.add(new_mission)
    db.session.commit()

    log_action('EINSATZ NEU', f"Neuer Einsatz: {new_mission.reason} in {new_mission.location}", mission_id=new_mission.id)
    return jsonify(new_mission.to_dict()), 201

@app.route('/api/missions/<int:id>', methods=['PUT'])
def update_mission(id):
    sid = get_session_id()
    mission = Mission.query.filter_by(id=id, session_id=sid, is_deleted=False).first_or_404()
    data = request.json
    
    changes = []
    
    if 'status' in data and data['status'] != mission.status:
        changes.append(f"Status: {mission.status} -> {data['status']}")
        mission.status = data['status']
    
    if 'outcome' in data and data['outcome'] != mission.outcome:
        mission.outcome = data['outcome']
        
        # Check if ARM details are provided in this request OR already exist
        current_arm_id = data.get('arm_id', mission.arm_id)
        
        if (mission.outcome == 'ARM' or mission.outcome == 'ARM (Anderes Rettungsmittel)') and current_arm_id:
             changes.append(f"Ausgang: ARM / {current_arm_id}")
        else:
             changes.append(f"Ausgang: {mission.outcome}")
        
    if 'arm_id' in data and data['arm_id'] != mission.arm_id:
        # Only log if specifically changed (and not just set during initial ARM outcome setting if that was already logged above)
        # However, the block above only logs "Ausgang: ...". 
        # If outcome didn't change (e.g. already ARM), we need to log this.
        # If outcome DID change, we logged "ARM / new_id". 
        # So we should check if we already logged outcome change to avoid duplicate "ARM / ..." logs if possible,
        # OR just log "Kennung geändert: ..."
        
        if 'outcome' not in data or data['outcome'] == mission.outcome:
             changes.append(f"ARM Kennung: {mission.arm_id or ''} -> {data['arm_id']}")
        
        mission.arm_id = data['arm_id']

    if 'arm_type' in data and data['arm_type'] != mission.arm_type:
        if 'outcome' not in data or data['outcome'] == mission.outcome:
            changes.append(f"ARM Typ: {mission.arm_type or ''} -> {data['arm_type']}")
        mission.arm_type = data['arm_type']
    
    if 'squad_ids' in data:
        # Update roster
        current_ids = {s.id for s in mission.squads}
        new_ids = set(data['squad_ids'])
        if current_ids != new_ids:
            changes.append("Trupps aktualisiert")
            mission.squads = []
            for sid in new_ids:
                s = Squad.query.get(sid)
                if s: 
                    mission.squads.append(s)

    # Handle description separately to include content in log
    if 'description' in data and mission.description != data['description']:
        mission.description = data['description']
        desc_text = mission.description if mission.description else "(leer)"
        changes.append(f"Lagebeschreibung: {desc_text}")

    # Handle other fields
    fields = ['location', 'reason', 'mission_number', 'alarming_entity']
    for f in fields:
        if f in data and getattr(mission, f) != data[f]:
            changes.append(f"{f.capitalize()} geändert")
            setattr(mission, f, data[f])
            
    if 'notes' in data and mission.notes != data['notes']:
        mission.notes = data['notes']
        # Limit length if very long? 
        changes.append(f"Notiz: {mission.notes}")

    if changes:
        db.session.commit()
        log_action('EINSATZ UPDATE', ", ".join(changes), mission_id=mission.id)

    return jsonify(mission.to_dict())

@app.route('/api/missions/<int:id>', methods=['DELETE'])
def delete_mission(id):
    sid = get_session_id()
    mission = Mission.query.filter_by(id=id, session_id=sid).first_or_404()
    
    data = request.json or {}
    reason = data.get('reason', 'Keine Begründung')
    
    log_action('EINSATZ GELÖSCHT', f"Einsatz {mission.mission_number or mission.id} gelöscht. Grund: {reason}", mission_id=mission.id)
    
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
    
    # Header
    output.write("=== EINSATZPROTOKOLL ===\n")
    if config:
        output.write(f"Dienst: {config.location}\n")
        if config.address:
            output.write(f"Adresse: {config.address}\n")
        
        # Format times nicely
        s_str = config.start_time.strftime('%d.%m.%Y %H:%M') if config.start_time else '?'
        e_str = config.end_time.strftime('%d.%m.%Y %H:%M') if config.end_time else 'Laufend'
        
        output.write(f"Zeitraum: {s_str} - {e_str}\n")
    output.write("\n")
    
    # Missions
    missions = Mission.query.filter_by(session_id=sid).order_by(Mission.created_at).all()
    output.write(f"=== EINSÄTZE ({len(missions)}) ===\n\n")
    
    for m in missions:
        output.write(f"Einsatz #{m.mission_number or m.id}\n")
        
        # Show start time and end time (if completed)
        start_time = m.created_at.strftime('%d.%m.%Y %H:%M:%S') if m.created_at else '?'
        if m.status == 'Abgeschlossen':
            # Find the completion time from logs
            completion_log = LogEntry.query.filter_by(mission_id=m.id, action='EINSATZ UPDATE', session_id=sid).filter(
                LogEntry.details.like('%Status: Laufend -> Abgeschlossen%')
            ).order_by(LogEntry.timestamp.desc()).first()
            
            if completion_log:
                end_time = completion_log.timestamp.strftime('%d.%m.%Y %H:%M:%S')
            else:
                end_time = 'Abgeschlossen'
            
            outcome_display = m.outcome
            if (m.outcome == 'ARM' or m.outcome == 'ARM (Anderes Rettungsmittel)') and m.arm_id:
                outcome_display = f"ARM / {m.arm_id}"
                
            output.write(f"Zeit: {start_time} - {end_time} ({outcome_display})\n")
        else:
            output.write(f"Zeit: {start_time} - Laufend\n")
        
        output.write(f"Ort: {m.location}\n")
        output.write(f"Grund: {m.reason}\n")
        output.write(f"Alarmierung: {m.alarming_entity}\n")
        output.write(f"Beteiligte Trupps: {', '.join([s.name for s in m.squads])}\n")
        if m.description:
            output.write(f"Lage: {m.description}\n")
        if m.notes:
            output.write(f"Notizen: {m.notes}\n")
        
        # Chronology of this mission
        m_logs = LogEntry.query.filter_by(mission_id=m.id).order_by(LogEntry.timestamp).all()
        if m_logs:
            output.write("  Verlauf:\n")
            for l in m_logs:
                output.write(f"  - [{l.timestamp.strftime('%H:%M:%S')}] {l.action}: {l.details}\n")
        
        output.write("-" * 40 + "\n\n")

    # Squad Activity / Pause Analysis
    output.write("=== TRUPP-AKTIVITÄT ===\n\n")
    squads = Squad.query.filter_by(session_id=sid).all()
    for s in squads:
        # Count missions for this squad
        mission_count = len([m for m in s.missions])
        
        output.write(f"Trupp: {s.name} ({s.qualification}) - {mission_count} Einsätze\n")
        s_logs = LogEntry.query.filter_by(squad_id=s.id).order_by(LogEntry.timestamp).all()
        
        # Track pause periods (start and end times)
        pause_periods = []
        pause_start = None
        
        for l in s_logs:
            if l.action == 'STATUS':
                # Add mission context if available
                mission_context = ""
                if l.mission_id:
                    mission = Mission.query.filter_by(id=l.mission_id, session_id=sid).first()
                    if mission:
                        mission_num = mission.mission_number or mission.id
                        mission_context = f" (Einsatz #{mission_num})"
                
                output.write(f"  [{l.timestamp.strftime('%H:%M:%S')}] {l.details}{mission_context}\n")
                
                # Check if status changed to Pause
                if '-> Pause' in l.details:
                    pause_start = l.timestamp
                # Check if status changed from Pause to something else
                elif pause_start and 'Pause ->' in l.details:
                    pause_end = l.timestamp
                    pause_periods.append(f"{pause_start.strftime('%H:%M:%S')} - {pause_end.strftime('%H:%M:%S')}")
                    pause_start = None
        
        # If pause is still ongoing (no end time)
        if pause_start:
            pause_periods.append(f"{pause_start.strftime('%H:%M:%S')} - laufend")
        
        # Summary of pauses
        if pause_periods:
            output.write(f"  Pausen: {'; '.join(pause_periods)}\n")
        output.write("\n")
    
    # Full Log
    output.write("=== GESAMTES LOGBUCH ===\n")
    all_logs = LogEntry.query.filter_by(session_id=sid).order_by(LogEntry.timestamp).all()
    for l in all_logs:
        output.write(f"[{l.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] [{l.action}] {l.details}\n")
        
    output.write("\n")

    # Deleted Missions
    deleted_missions = Mission.query.filter_by(session_id=sid, is_deleted=True).order_by(Mission.created_at).all()
    if deleted_missions:
        output.write("=== GELÖSCHTE EINSÄTZE ===\n\n")
        for m in deleted_missions:
            m_num = m.mission_number or m.id
            output.write(f"Einsatz #{m_num} ({m.location})\n")
            output.write(f"  Grund für Löschung: {m.deletion_reason}\n")
            output.write(f"  Urspr. Alarmierung: {m.reason}\n")
            if m.description:
                output.write(f"  Lage: {m.description}\n")
            
            # Add logs for deleted mission context
            m_logs = LogEntry.query.filter_by(mission_id=m.id).order_by(LogEntry.timestamp).all()
            if m_logs:
                output.write("  Verlauf vor Löschung:\n")
                for l in m_logs:
                     output.write(f"  - [{l.timestamp.strftime('%H:%M:%S')}] {l.action}: {l.details}\n")
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
        db.session.commit()
        log_action('KONFIGURATION', f"Dienst beendet: {config.location}")
        
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

if __name__ == '__main__':
    with app.app_context():
        # Auto-create DB if not exists, but we rely on a manual reset or Init API for clean slate usually
        db.create_all()
    app.run(debug=True, port=5001)

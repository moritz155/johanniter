from .extensions import db
from datetime import datetime

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
    naca_score = db.Column(db.String(200), nullable=True) # NACA Full Text
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
            'naca_score': self.naca_score,
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

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.value, # For consistency with other models that have 'name'
            'value': self.value,
            'category': self.category
        }

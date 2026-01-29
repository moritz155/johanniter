from flask import Blueprint, request, jsonify, send_file, session
from datetime import datetime
import uuid
import os
from werkzeug.security import generate_password_hash, check_password_hash

from ..extensions import db
from ..models import ShiftConfig, Squad, Mission, LogEntry, PredefinedOption
from ..utils import (
    get_session_id, log_action, update_ambulanz_occupancy, 
    generate_export_file, generate_pdf_file, 
    STATUS_MAP, STATUS_CODES
)
from ..messages import LogMessages

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/init', methods=['GET'])
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
    
@api_bp.route('/api/updates', methods=['GET'])
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

@api_bp.route('/api/config', methods=['POST'])
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
        default_file = 'scripts/default_options.txt' # Adjusted path assuming scripts moved or keeping root?
        # NOTE: default_options.txt is likely still at root unless I moved it. 
        # I did not move default_options.txt in previous steps, only python scripts.
        # But wait, app is now in app/ so root is .., but working dir is usually root.
        # I'll check where default_options.txt is. It's at root.
        
        if not os.path.exists(default_file):
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

@api_bp.route('/api/join', methods=['POST'])
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

@api_bp.route('/api/config', methods=['PUT'])
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


@api_bp.route('/api/squads', methods=['POST'])
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

@api_bp.route('/api/squads/<int:id>', methods=['PUT'])
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
                 new_loc = new_val or "(Automatisch)"
                 changes.append(f"Standort: {new_loc}")
                 squad.custom_location = new_val

                 # Feature: Add Abgabeort to Mission Notes if active mission exists
                 if new_val:
                     am_for_notes = None
                     for m in squad.missions:
                         if m.status != 'Abgeschlossen' and not m.is_deleted:
                             am_for_notes = m
                             break
                     
                     if am_for_notes:
                         # Append to notes
                         # Use local time approximation or just simple format
                         timestamp = datetime.now().strftime("%H:%M") 
                         note_add = f"[{timestamp}] Abgabeort: {new_val}"
                         if am_for_notes.notes:
                             am_for_notes.notes += f"\n{note_add}"
                         else:
                             am_for_notes.notes = note_add


    if changes:
        db.session.commit()
        log_action('TRUPP UPDATE', LogMessages.SQUAD_UPDATED.format(name=squad.name, changes='; '.join(changes)), squad_id=squad.id)
        
    return jsonify(squad.to_dict())

@api_bp.route('/api/squads/reorder', methods=['POST'])
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

@api_bp.route('/api/squads/<int:id>', methods=['DELETE'])
def delete_squad(id):
    sid = get_session_id()
    squad = Squad.query.filter_by(id=id, session_id=sid).first_or_404()
    name = squad.name
    
    # Delete association rows manually if not cascaded by model
    db.session.execute(db.text("DELETE FROM mission_squad WHERE squad_id = :id"), {'id': id})
    
    db.session.delete(squad)
    db.session.commit()
    
    log_action('TRUPP GELÖSCHT', LogMessages.SQUAD_REMOVED.format(name=name))
    return jsonify({'status': 'deleted'})

@api_bp.route('/api/squads/<int:id>/status', methods=['POST'])
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
            if len(squad.missions) > 0:
                # Find active one
                for m in squad.missions:
                     if m.status != 'Abgeschlossen' and not m.is_deleted:
                         active_mission_id = m.id
                         break

            old_state_text = STATUS_CODES.get(str(old_status), str(old_status))
            new_state_text = STATUS_CODES.get(str(new_status), str(new_status))
            
            # If standard key not found, try robust fallback
            if old_state_text == str(old_status) and old_status in ['6', 'NEB']: old_state_text = 'NEB / Pause'
            if new_state_text == str(new_status) and new_status in ['6', 'NEB']: new_state_text = 'NEB / Pause'

            log_action('STATUS', LogMessages.STATUS_CHANGED.format(
                name=squad.name, 
                status=f"{old_state_text} -> {new_state_text}"
            ), squad_id=squad.id, mission_id=active_mission_id)
            
        except Exception as e:
            print(f"Log Error: {e}")
            # Swallow logging error to prevent client crash
            pass

        return jsonify(squad.to_dict())
    
    return jsonify(squad.to_dict())

@api_bp.route('/api/missions', methods=['POST'])
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
        naca_score=data.get('naca_score'),
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

@api_bp.route('/api/missions/<int:id>', methods=['PUT'])
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

    if 'naca_score' in data and data['naca_score'] != mission.naca_score:
        new_val = data['naca_score'] or ""
        changes.append(f"NACA: {new_val}")
        mission.naca_score = data['naca_score']
    
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

@api_bp.route('/api/missions/<int:id>', methods=['DELETE'])
def delete_mission(id):
    sid = get_session_id()
    mission = Mission.query.filter_by(id=id, session_id=sid).first_or_404()
    
    data = request.json or {}
    reason = data.get('reason', 'Keine Begründung')
    
    log_action('EINSATZ GELÖSCHT', LogMessages.MISSION_DELETED.format(number=mission.mission_number or mission.id, reason=reason), mission_id=mission.id)
    
    # Soft Delete instead of hard delete
    mission.is_deleted = True
    mission.deletion_reason = reason
    
    db.session.commit()
    
    return jsonify({'status': 'deleted'})

@api_bp.route('/api/changes', methods=['GET'])
def get_changes():
    sid = get_session_id()
    logs = LogEntry.query.filter_by(session_id=sid).order_by(LogEntry.timestamp.desc()).all()
    return jsonify([l.to_dict() for l in logs])

@api_bp.route('/api/export', methods=['GET'])
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

@api_bp.route('/api/export/pdf', methods=['GET'])
def export_pdf():
    sid = get_session_id()
    config = ShiftConfig.query.filter_by(is_active=True, session_id=sid).first()
    if not config:
        config = ShiftConfig.query.filter_by(session_id=sid).order_by(ShiftConfig.id.desc()).first()
        
    mem = generate_pdf_file(config)
    filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return send_file(mem, as_attachment=True, download_name=filename, mimetype='application/pdf')

@api_bp.route('/api/config/end', methods=['POST'])
def end_shift():
    sid = get_session_id()
    config = ShiftConfig.query.filter_by(is_active=True, session_id=sid).first()
    if config:
        config.is_active = False
        config.end_time = datetime.utcnow()
        # Cleanup Access Tokens
        Squad.query.filter_by(session_id=sid).update({Squad.access_token: None})
        db.session.commit()
        log_action('KONFIGURATION', LogMessages.SHIFT_ENDED.format(location=config.location))
        
    # Reset predefined options to default values
    PredefinedOption.query.filter_by(session_id=sid).delete()
    
    # Load default options from file if it exists
    default_file = 'scripts/default_options.txt'
    if not os.path.exists(default_file):
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

@api_bp.route('/api/logs/custom', methods=['POST'])
def custom_log():
    data = request.json
    details = data.get('details')
    if not details:
        return jsonify({'error': 'Details required'}), 400
    
    # Log as 'EREIGNIS'
    log_action('EREIGNIS', details)
    return jsonify({'status': 'ok'})

from flask import request, session
import uuid
import io
import os
from datetime import datetime, timezone
from .extensions import db
from .models import LogEntry, Squad, Mission, ShiftConfig, PredefinedOption
from .messages import LogMessages

# Report libraries
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

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

STATUS_CODES = {
    '1': 'Funkbereit',
    '2': 'EB',
    '3': 'zBO',
    '4': 'BO',
    '5': 'Sprechwunsch',
    '6': 'NEB / Pause',
    '7': 'zAO',
    '8': 'AO',
    '0': 'Aus',
    'NEB': 'NEB / Pause'
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

def to_local(dt_obj):
    if not dt_obj:
        return None
    # Assume server local time is desired
    # UTC -> Local System Time
    return dt_obj.replace(tzinfo=timezone.utc).astimezone(None)

def generate_export_file(config):
    output = io.StringIO()
    sid = config.session_id if config else get_session_id()

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
            # Try to find specific log
            found_end_log = False
            for l in m_logs:
                if 'Status: Laufend -> Abgeschlossen' in (l.details or "") or 'auf Abgeschlossen' in (l.details or ""):
                    end_local = to_local(l.timestamp)
                    end_time = end_local.strftime('%d.%m.%Y %H:%M:%S')
                    found_end_log = True
                    break
            
            # Fallback if no specific log found but status is Abgeschlossen
            if not found_end_log and m.updated_at:
                end_local = to_local(m.updated_at)
                end_time = end_local.strftime('%d.%m.%Y %H:%M:%S')
            
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
        
        if m.naca_score:
            output.write(f"NACA: {m.naca_score}\n")
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
        label_type = s.type if s.type else "Trupp"
        output.write(f"{label_type}: {s.name} ({s.qualification}){sn_text} - {mission_count} Einsätze\n")
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
         story.append(Paragraph(LogMessages.LBL_RESPONSE_TIME.format(minutes=f"{avg_resp:.1f}"), normal_style))
         story.append(Spacer(1, 0.5*cm))

    # Detailed Missions
    story.append(Paragraph(LogMessages.SECTION_MISSIONS, heading2))
    story.append(Spacer(1, 0.2*cm))

    for m in valid_missions:
        mission_elements = []  # Group elements for this mission
        
        m_num = m.mission_number or str(m.id)
        mission_elements.append(Paragraph(LogMessages.LBL_MISSION_NUM.format(number=m_num), heading3))
        
        # Details Table for this mission
        start_t = m.created_at.strftime('%d.%m.%Y %H:%M:%S') if m.created_at else "?"
        
        # Determine End Time
        end_time = "Laufend"
        if m.status == 'Abgeschlossen':
            # Try to find specific log
            found_end_log = False
            m_logs = LogEntry.query.filter_by(mission_id=m.id, action='EINSATZ UPDATE', session_id=sid).order_by(LogEntry.timestamp.desc()).all()
            for l in m_logs:
                if 'Status: Laufend -> Abgeschlossen' in (l.details or "") or 'auf Abgeschlossen' in (l.details or ""):
                    end_time = l.timestamp.strftime('%d.%m.%Y %H:%M:%S')
                    found_end_log = True
                    break
            
            # Fallback
            if not found_end_log and m.updated_at:
                 end_time = m.updated_at.strftime('%d.%m.%Y %H:%M:%S')

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
        
        if m.naca_score:
             det_data.append(["NACA:", m.naca_score, "", ""])
        
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
        mission_elements.append(dt)
        
        # Mission Log
        m_logs = LogEntry.query.filter_by(mission_id=m.id).order_by(LogEntry.timestamp).all()
        if m_logs:
            mission_elements.append(Spacer(1, 0.2*cm))
            mission_elements.append(Paragraph(LogMessages.LBL_HISTORY, styles['Normal']))
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
            mission_elements.append(lt)
            
        mission_elements.append(Spacer(1, 0.5*cm))
        mission_elements.append(Paragraph("-" * 120, small_style)) # Separator
        mission_elements.append(Spacer(1, 0.5*cm))

        # Add the grouped elements to the story, ensuring they stay together
        story.append(KeepTogether(mission_elements))

    # Squad Activity
    story.append(PageBreak())
    story.append(Paragraph(LogMessages.SECTION_SQUADS, heading2))
    
    squads = Squad.query.filter_by(session_id=sid).all()
    for s in squads:
        mission_count = len([m for m in s.missions])
        sn_text = f" [DN: {s.service_numbers}]" if s.service_numbers else ""
        label_type = s.type if s.type else "Trupp"
        story.append(Paragraph(f"{label_type}: {s.name} ({s.qualification}){sn_text} - {mission_count} Einsätze", heading3))
        
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
             if len([m for m in s.missions]) > 0: # Just to not clutter empty squads
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

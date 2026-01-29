class LogMessages:
    # --- Logging ---
    SHIFT_STARTED = "Dienstbetrieb aufgenommen. Stützpunkt: {location}"
    CONFIG_CHANGED = "Systemkonfiguration geändert: {changes}"
    SHIFT_ENDED = "Dienstschluss / Einsatzende. Abschlussort: {location}"
    
    SQUAD_CREATED = "Einheit in Dienst gestellt: '{name}' ({qualification} | DN: {numbers})"
    SQUAD_UPDATED = "Stammdatenänderung '{name}': {changes}"
    SQUAD_REMOVED = "Einheit '{name}' außer Dienst gestellt"
    
    STATUS_CHANGED = "Statusänderung {name}: {status}"
    STATUS_AUTO_BUSY = "Status (System): Einsatzübernahme / Besetzt"
    STATUS_AUTO_FREE = "Status (System): Einsatzbereit (Auto-Frei)" # Added for completeness based on code logic
    DISPATCHED_AUTO = "Disposition (System): Zuweisung zu Einsatz #{number}"
    PATIENT_ASSIGNED = "Disposition (System): Patient zugewiesen" # For Ambulanz logic
    STATUS_INTEGRATED = "Status auf Integriert gesetzt" # For Mission assignment context
    
    MISSION_CREATED = "Einsatzeröffnung #{number}: {reason} // {location}"
    MISSION_UPDATED = "Änderungen an Einsatz #{number}: {changes}"
    MISSION_DELETED = "Einsatz #{number} storniert. Grund: {reason}"
    
    # Notiz
    NOTE_ADDED = "Lagemeldung / Vermerk dokumentiert"
    NOTE_CHANGED = "Lagemeldung aktualisiert: {old} zu {new}" # Keeping logic for change tracking if needed or simplifiying?
    # User asked for "Notiz hinzugefügt" -> "Lagemeldung / Vermerk dokumentiert"
    # The code also has "Notiz geändert..." logic. I will adapt that to fit the professional tone.
    
    # --- Export Headers & Labels ---
    REPORT_TITLE_TXT = "=== EINSATZDOKUMENTATION / DIENSTPROTOKOLL ==="
    REPORT_TITLE_PDF = "Einsatzdokumentation / Dienstprotokoll"
    
    SECTION_MISSIONS = "EINSÄTZE"
    SECTION_SQUADS = "EINGESETZTE KRÄFTE" # Replacing TRUPP-AKTIVITÄT
    SECTION_LOG = "GESAMTES LOGBUCH"
    SECTION_DELETED = "STORNIERTE EINSÄTZE" # Replacing GELÖSCHTE EINSÄTZE
    
    # Export Labels
    LBL_SERVICE = "Dienst:"
    LBL_ADDRESS = "Adresse:"
    LBL_PERIOD = "Zeitraum:"
    
    LBL_MISSION_NUM = "Einsatz #{number}"
    LBL_TIME = "Zeit:"
    LBL_OUTCOME = "Ausgang:"
    LBL_LOCATION = "Ort:"
    LBL_ALARMING = "Meldebild" # Was: Alarmierung
    LBL_REASON = "Grund:" 
    LBL_SQUADS = "Eingesetzte Kräfte" # Was: Beteiligte Trupps
    LBL_SITUATION = "Lage:"
    LBL_NOTES = "Notizen:"
    LBL_HISTORY = "Verlauf:"
    
    LBL_RESPONSE_TIME = "Ø Hilfsfrist / Reaktionszeit (Alarmierung -> Eintreffen): {minutes} min"
    
    LBL_PAUSES = "Ruhezeiten" # Was: Pausen
    LBL_NO_PAUSES = "Keine Ruhezeiten dokumentiert."
    
    LBL_DELETE_REASON = "Grund für Stornierung:" # Was: Grund für Löschung
    LBL_ORIGINAL_ALARM = "Urspr. Meldebild:" # Was: Urspr. Alarmierung

# Patch Notes - 13.12.2025

## Neue Funktionen
- **Trupp-Management per Drag & Drop:**
  - Trupps können nun per Drag & Drop in der Liste neu sortiert werden.
  - Ein Trupp kann per Drag & Drop direkt auf einen offenen Einsatz gezogen werden. Er wird dem Einsatz automatisch zugewiesen und der Status wechselt auf "zBO" (Status 3).
- **Einsätze Löschen (Soft Delete):**
  - Einsätze können nun mit Angabe eines Grundes gelöscht werden.
  - Gelöschte Einsätze verschwinden aus der aktiven Ansicht, bleiben aber im Hintergrund erhalten.
  - **Export:** Gelöschte Einsätze werden im Export-Protokoll in einem eigenen Abschnitt ("Gelöschte Einsätze") am Ende des Dokuments inklusive Begründung und Historie aufgelistet.
- **Wetter-Widget:** Anzeige von aktuellem Wetter und Temperatur in der Kopfzeile (basierend auf Standort oder IP).

## Anpassungen & Verbesserungen
- **Trupp-Status:** Der Standard-Status für neue Trupps ist nun "EB" (Status 2). Status "1" (Frei) wurde entfernt.
- **Benutzeroberfläche (UI):**
  - **Dialog-Fenster:** Alle "Abbrechen"-Buttons wurden durch ein einheitliches "X"-Symbol oben rechts ersetzt.
  - **Buttons:** Die Buttons "Speichern", "Abschließen" und "Löschen" haben nun eine einheitliche Größe und Schriftart.
  - **Button-Layout:** "Löschen" ist linksbündig, "Abschließen" und "Speichern" sind rechtsbündig gruppiert.
  - **Dynamische Titel:** Das Fenster zeigt nun korrekt "Neuer Einsatz" oder "Einsatz bearbeiten" im Titel an, je nach Kontext.
  - **Kompakte Darstellung:** Lange Einsatz-Ausgänge werden in der Liste abgekürzt (z.B. "Int. Unt.").

## Bugfixes
- Fehler behoben, bei dem die "Löschen"-Funktion für Einsätze nicht korrekt ausgeführt wurde.
- Layout-Probleme in kleineren Dialog-Fenstern behoben.

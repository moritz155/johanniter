let squadsData = [];
let missionsData = [];
let optionsData = {};
let configData = null;

// Theme Toggle Logic
function toggleTheme() {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    updateThemeIcon(isDark);
}

function updateThemeIcon(isDark) {
    const btn = document.getElementById('btn-theme-toggle');
    if (!btn) return;
    const svg = btn.querySelector('svg');
    if (isDark) {
        // Sun icon
        svg.innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
    } else {
        // Moon icon
        svg.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
    }
}

// Color Customization
function setHeaderColor(color) {
    document.documentElement.style.setProperty('--header-bg', color);
    localStorage.setItem('headerColor', color);
}

// Load Theme on Init
const savedTheme = localStorage.getItem('theme');
if (savedTheme === 'dark') {
    document.body.classList.add('dark-mode');
}

const savedColor = localStorage.getItem('headerColor');
if (savedColor) {
    setHeaderColor(savedColor);
}

document.addEventListener('DOMContentLoaded', () => {
    // Initial Icon Update
    updateThemeIcon(document.body.classList.contains('dark-mode'));

    loadData();
    setInterval(updateClock, 1000);
    setInterval(updateTimers, 1000);
});

async function loadData() {
    try {
        const response = await fetch('/api/init');
        const data = await response.json();

        configData = data.config;
        squadsData = data.squads;
        missionsData = data.missions;
        optionsData = data.options;

        if (!configData) {
            document.getElementById('welcome-screen').classList.add('active');
            document.querySelector('header').style.display = 'none';
            document.querySelector('main').style.display = 'none';
            document.querySelector('footer').style.display = 'none';
        } else {
            document.getElementById('welcome-screen').classList.remove('active');
            document.querySelector('header').style.display = '';
            document.querySelector('main').style.display = '';
            document.querySelector('footer').style.display = '';
            document.getElementById('shift-location').textContent = configData.location;
            renderSquads();
            renderMissions();
            populateDatalists();
            updateLastLog();
        }
    } catch (error) {
        console.error('Error loading data:', error);
    }
}

async function startShift(e) {
    e.preventDefault();
    const locInfo = document.body.dataset.locInfo || "N/A";
    const loc = document.getElementById('conf-location').value;
    const addr = document.getElementById('conf-address').value;
    const start = document.getElementById('conf-start').value;

    // Default location if empty (optional)
    const finalLoc = loc.trim() || 'Dienst ' + new Date().toLocaleDateString();

    // Collect squads from dynamic inputs
    const squads = [];
    document.querySelectorAll('.squad-input-item input').forEach((input, index) => {
        const name = input.value.trim() || `Trupp ${index + 1}`;
        squads.push({ name: name });
    });

    try {
        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                location: finalLoc,
                address: addr,
                start_time: start || null,
                squads: squads
            })
        });
        closeModal('shift-setup-modal');
        document.getElementById('welcome-screen').classList.remove('active');
        loadData();
    } catch (error) {
        console.error('Error starting shift:', error);
    }
}

function updateSquadInputs() {
    const count = parseInt(document.getElementById('conf-squad-count').value) || 0;
    const container = document.getElementById('squad-inputs-container');

    // Preserve existing values if expanding
    const currentValues = Array.from(container.querySelectorAll('input')).map(i => i.value);

    container.innerHTML = '';

    for (let i = 0; i < count; i++) {
        const div = document.createElement('div');
        div.className = 'squad-input-item';
        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = `Trupp ${i + 1}`;
        input.value = currentValues[i] || ''; // Restore or empty
        div.appendChild(input);
        container.appendChild(div);
    }
}

function changeSquadCount(delta) {
    const input = document.getElementById('conf-squad-count');
    let val = parseInt(input.value) || 0;
    val += delta;
    if (val < 0) val = 0;
    if (val > 20) val = 20;
    input.value = val;
    updateSquadInputs();
}

function openShiftSetup() {
    document.getElementById('shift-setup-modal').classList.add('open');
}

// --- Guide / Tour System ---
// --- Tutorial System ---
let currentTutorialStep = 0;
const totalTutorialSteps = 4;

function openTutorial() {
    currentTutorialStep = 0;
    updateTutorialUI();
    document.getElementById('tutorial-modal').classList.add('open');
}

function nextTutorialStep() {
    if (currentTutorialStep < totalTutorialSteps - 1) {
        currentTutorialStep++;
        updateTutorialUI();
    } else {
        closeModal('tutorial-modal');
    }
}

function prevTutorialStep() {
    if (currentTutorialStep > 0) {
        currentTutorialStep--;
        updateTutorialUI();
    }
}

function updateTutorialUI() {
    // Show correct slide
    document.querySelectorAll('.tutorial-slide').forEach((slide, index) => {
        if (index === currentTutorialStep) {
            slide.classList.add('active');
        } else {
            slide.classList.remove('active');
        }
    });

    // Update dots
    document.querySelectorAll('.dot').forEach((dot, index) => {
        if (index === currentTutorialStep) {
            dot.classList.add('active');
        } else {
            dot.classList.remove('active');
        }
    });

    // Update buttons
    document.getElementById('btn-tut-prev').disabled = currentTutorialStep === 0;
    const nextBtn = document.getElementById('btn-tut-next');
    if (currentTutorialStep === totalTutorialSteps - 1) {
        nextBtn.textContent = 'Verstanden';
        nextBtn.classList.add('btn-success');
        nextBtn.classList.remove('btn-primary');
    } else {
        nextBtn.textContent = 'Weiter';
        nextBtn.classList.add('btn-primary');
        nextBtn.classList.remove('btn-success');
    }
}

function openConfigModal() {
    if (!configData) return;
    document.getElementById('edit-conf-location').value = configData.location || '';
    document.getElementById('edit-conf-address').value = configData.address || '';
    document.getElementById('edit-conf-start').value = configData.start_time ? configData.start_time.slice(0, 16) : '';
    document.getElementById('edit-conf-end').value = configData.end_time ? configData.end_time.slice(0, 16) : '';

    document.getElementById('config-modal').classList.add('open');
}

async function updateConfig(e) {
    e.preventDefault();
    const payload = {
        location: document.getElementById('edit-conf-location').value,
        address: document.getElementById('edit-conf-address').value,
        start_time: document.getElementById('edit-conf-start').value,
        end_time: document.getElementById('edit-conf-end').value
    };

    // Handle file upload for locations
    const fileInput = document.getElementById('locations-file');
    if (fileInput.files.length > 0) {
        const file = fileInput.files[0];
        const text = await file.text();
        const locations = text.split('\n')
            .map(line => line.trim())
            .filter(line => line && !line.startsWith('#'));

        if (locations.length > 0) {
            payload.locations = locations;
        }
    }

    try {
        await fetch('/api/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        closeModal('config-modal');
        loadData();
    } catch (error) {
        console.error('Error updating config:', error);
    }
}

async function endShift() {
    if (!confirm("Möchten Sie den Dienst wirklich beenden? Der aktuelle Status wird deaktiviert.")) return;

    try {
        const response = await fetch('/api/config/end', { method: 'POST' });
        if (response.ok) {
            // Returns blob (export file)
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `abschluss_export.txt`;
            document.body.appendChild(a);
            a.click();
            a.remove();

            // Give it a moment to download before reloading
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        }
    } catch (error) {
        console.error("Error ending shift:", error);
    }
}

function updateClock() {
    const now = new Date();
    document.getElementById('clock').textContent = now.toLocaleTimeString();
    document.getElementById('date').textContent = now.toLocaleDateString();
}

// --- Squads ---

function renderSquads() {
    const container = document.getElementById('squad-list');
    container.innerHTML = '';

    squadsData.forEach(squad => {
        const card = document.createElement('div');
        card.className = 'squad-card';

        // Status mapping
        const statuses = [
            { code: '2', label: 'EB', class: 's2' },
            { code: '3', label: 'zBO', class: 's3' },
            { code: '4', label: 'BO', class: 's4' },
            { code: '7', label: 'zAO', class: 's7' },
            { code: '8', label: 'AO', class: 's8' },
            { code: 'Pause', label: 'Pause', class: 'sP' },
            { code: 'NEB', label: 'NEB', class: 'sNEB' }
        ];

        let buttonsHtml = '';
        statuses.forEach(st => {
            const active = squad.current_status === st.code ? 'active' : '';
            buttonsHtml += `<button class="status-btn ${st.class} ${active}" 
                onclick="setSquadStatus(${squad.id}, '${st.code}')">${st.label}</button>`;
        });

        // Location Info
        let locInfo = squad.current_status;
        const statusMap = {
            '2': 'Einsatzbereit',
            '3': 'Zum Berufungsort',
            '4': 'Am Berufungsort',
            '7': 'Zum Abgabeort',
            '8': 'Am Abgabeort',
            'Pause': 'Pause',
            'NEB': 'Nicht Einsatzbereit'
        };

        if (statusMap[squad.current_status]) {
            locInfo = statusMap[squad.current_status];
        }

        if (squad.active_mission) {
            locInfo = `Einsatz #${squad.active_mission.mission_number || squad.active_mission.id} (${squad.active_mission.location}) - ${squad.active_mission.reason}`;

            // Warning Check: Mission active but Status is 2 (EB), Pause, or NEB
            const invalidStatuses = ['2', 'Pause', 'NEB'];
            if (invalidStatuses.includes(squad.current_status)) {
                locInfo += `<span class="status-warning-dot" title="Status prüfen!"></span>`;
            }
        }

        card.setAttribute('draggable', true);
        card.dataset.id = squad.id;
        card.addEventListener('dragstart', handleDragStart);
        card.addEventListener('dragover', handleDragOver);
        card.addEventListener('drop', handleDrop);
        card.addEventListener('dragenter', handleDragEnter);
        card.addEventListener('dragleave', handleDragLeave);

        card.innerHTML = `
            <div class="squad-info">
                <div style="display:flex; align-items:center; gap: 0.5rem;">
                    <h3>${squad.name} <span class="qual-badge">${squad.qualification}</span></h3>
                    <button class="icon-btn tiny" onclick='editSquad(${JSON.stringify(squad)})' title="Trupp bearbeiten">✎</button>
                </div>
                <div class="squad-status-text">${locInfo}</div>
                <div class="squad-actions">
                    ${buttonsHtml}
                </div>
            </div>
            <div class="squad-timer" id="timer-${squad.id}" data-change="${squad.last_status_change}" style="margin-right: 1.5rem;">
                00:00
            </div>
        `;
        container.appendChild(card);
    });
    updateTimers();
}

function updateTimers() {
    const now = new Date();
    squadsData.forEach(squad => {
        const el = document.getElementById(`timer-${squad.id}`);
        if (!el) return;

        // Hide timer if status is '2' (EB)
        if (squad.current_status === '2') {
            el.style.visibility = 'hidden';
            return;
        }
        el.style.visibility = 'visible';

        // Count up from last change
        const changeTime = new Date(squad.last_status_change);
        const diff = Math.floor((now - changeTime) / 1000);

        if (diff < 0) { el.textContent = '00:00'; return; }

        const m = Math.floor(diff / 60).toString().padStart(2, '0');
        const s = (diff % 60).toString().padStart(2, '0');

        if (diff > 3600) {
            const h = Math.floor(diff / 3600).toString().padStart(2, '0');
            const mRem = Math.floor((diff % 3600) / 60).toString().padStart(2, '0');
            const sRem = (diff % 60).toString().padStart(2, '0');
            el.textContent = `${h}:${mRem}:${sRem}`;
        } else {
            el.textContent = `${m}:${s}`;
        }
    });
}

let pendingNebSquadId = null;
let nebConflictQueue = [];
let currentNebMission = null;

async function setSquadStatus(id, status) {
    // Check for NEB and Active Missions
    if (status === 'NEB') {
        const squad = squadsData.find(s => s.id === id);
        if (squad) {
            // Find ALL active missions this squad is in
            const activeMissions = missionsData.filter(m =>
                m.status !== 'Abgeschlossen' && m.squad_ids.includes(id)
            );

            if (activeMissions.length > 0) {
                pendingNebSquadId = id;
                nebConflictQueue = [...activeMissions];
                processNextNebConflict();
                return; // Stop here, wait for queue processing
            }
        }
    }

    // Normal path
    await performStatusUpdate(id, status);
}

function processNextNebConflict() {
    if (nebConflictQueue.length === 0) {
        // Queue finished -> Proceed to set NEB status
        if (pendingNebSquadId) {
            performStatusUpdate(pendingNebSquadId, 'NEB');
            pendingNebSquadId = null;
        }
        return;
    }

    currentNebMission = nebConflictQueue.shift();
    const squad = squadsData.find(s => s.id === pendingNebSquadId);
    if (!squad || !currentNebMission) return;

    const mNum = currentNebMission.mission_number || currentNebMission.id;

    // Set Modal Text
    document.getElementById('neb-confirm-text').innerHTML =
        `<strong>${squad.name}</strong> ist aktuell dem Einsatz <strong>#${mNum}</strong> zugewiesen.<br>Wie möchten Sie fortfahren?`;

    // Open Modal
    document.getElementById('neb-confirm-modal').classList.add('open');
}

async function resolveNebConflict(action) {
    if (!pendingNebSquadId || !currentNebMission) return;
    const sId = pendingNebSquadId;
    const mission = currentNebMission;

    // Close modal first
    closeModal('neb-confirm-modal');

    if (action === 'remove') {
        const newSquadIds = mission.squad_ids.filter(sid => sid !== sId);
        try {
            await fetch(`/api/missions/${mission.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ squad_ids: newSquadIds })
            });
        } catch (e) {
            console.error("Error removing squad:", e);
            alert("Fehler beim Entfernen aus dem Einsatz.");
        }
    }

    // Proceed to next item in queue
    // For 'keep', we just do nothing and move next.
    // For 'cancel' (implied by closing modal without action), we should probably stop the chain?
    // But here 'action' comes from buttons. The X button calls closeModal directly.
    // So if X is clicked, the queue halts and status is NOT updated. This is correct behavior (Cancel).

    // Wait a brief moment for UI transition? Not strictly necessary but looks better.
    setTimeout(() => {
        processNextNebConflict();
    }, 200);
}

async function performStatusUpdate(id, status) {
    await fetch(`/api/squads/${id}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status })
    });
    loadData();
}

function openSquadModal() {
    document.getElementById('s-form').reset();
    document.getElementById('s-id').value = '';

    // Reset Modal State for New Squad
    document.getElementById('squad-modal-title').textContent = 'Neuer Trupp';
    document.getElementById('btn-delete-squad').style.display = 'none';

    document.getElementById('squad-modal').classList.add('open');
}

function editSquad(squad) {
    document.getElementById('s-form').reset();
    document.getElementById('s-id').value = squad.id;
    document.getElementById('s-name').value = squad.name;
    document.getElementById('s-qual').value = squad.qualification;

    // Set Modal State for Edit
    document.getElementById('squad-modal-title').textContent = 'Trupp bearbeiten';
    document.getElementById('btn-delete-squad').style.display = 'block';

    document.getElementById('squad-modal').classList.add('open');
}

async function submitSquad(e) {
    e.preventDefault();
    const id = document.getElementById('s-id').value;
    const name = document.getElementById('s-name').value;
    const qual = document.getElementById('s-qual').value;

    if (id) {
        // Edit
        await fetch(`/api/squads/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, qualification: qual })
        });
    } else {
        // Create
        await fetch('/api/squads', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, qualification: qual })
        });
    }

    closeModal('squad-modal');
    loadData();
}

async function deleteSquad() {
    const id = document.getElementById('s-id').value;
    if (!id) return;

    if (!confirm("Trupp wirklich löschen?")) return;

    await fetch(`/api/squads/${id}`, { method: 'DELETE' });

    closeModal('squad-modal');
    loadData();
}

// --- Missions ---

function renderMissions() {
    const container = document.getElementById('mission-list');
    container.innerHTML = '';

    // Stats
    const total = missionsData.length;
    const open = missionsData.filter(m => m.status !== 'Abgeschlossen').length;
    const statsEl = document.getElementById('mission-stats');
    if (statsEl) {
        statsEl.textContent = `(Gesamt: ${total} | Offen: ${open})`;
    }

    missionsData.forEach(mission => {
        const card = document.createElement('div');
        card.className = `mission-card ${mission.status === 'Abgeschlossen' ? 'done' : ''}`;

        // Enable Drop if active
        if (mission.status !== 'Abgeschlossen') {
            card.addEventListener('dragover', allowDrop);
            card.addEventListener('drop', (e) => handleMissionDrop(e, mission));
        }

        const date = new Date(mission.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        // Helper map for statuses (replicated from renderSquads or could be global)
        const statusMap = {
            '2': { label: 'EB', class: 's2' },
            '3': { label: 'zBO', class: 's3' },
            '4': { label: 'BO', class: 's4' },
            '7': { label: 'zAO', class: 's7' },
            '8': { label: 'AO', class: 's8' },
            'Pause': { label: 'Pause', class: 'sP' },
            'NEB': { label: 'NEB', class: 'sNEB' },
            '2': { label: 'EB', class: 's2' } // Fallback to EB if unknown
        };

        const squadsHtml = mission.squads.map(sq => {
            // sq is now {name, id, status}
            // Only show status badge if mission is not completed
            if (mission.status === 'Abgeschlossen') {
                return `<span class="squad-tag">${sq.name}</span>`;
            } else {
                const st = statusMap[sq.status] || { label: 'EB', class: 's2' };
                return `<span class="squad-tag">
                    ${sq.name} <span class="mini-status ${st.class}">${st.label}</span>
                </span>`;
            }
        }).join(' ');

        card.innerHTML = `
            <div class="mission-header">
                <span class="mission-id">#${mission.mission_number || mission.id}</span>
                <span class="mission-time">${date}</span>
                <span class="mission-status-badge ${mission.status}" 
                      ${mission.status === 'Laufend' ? `style="cursor: pointer;" onclick='openCompleteMissionModal(${mission.id})' title="Einsatz abschließen"` : ''}>
                    ${mission.status}
                </span>
                <button class="edit-btn" onclick='editMission(${JSON.stringify(mission)})'>✎</button>
            </div>
            <div class="mission-details">
                <div><strong>Ort:</strong> ${mission.location}</div>
                <div><strong>Grund:</strong> ${mission.reason}</div>
                <div class="full-width"><strong>Trupps:</strong> <div style="display:inline-flex; gap:0.5rem; flex-wrap:wrap;">${squadsHtml}</div></div>
                ${mission.alarming_entity ? `<div><strong>Alarm:</strong> ${mission.alarming_entity}</div>` : ''}

                ${(() => {
                if (!mission.outcome) return '';
                const outcomeMap = {
                    'Intervention unterblieben': 'Int. Unt.',
                    'Belassen': 'Belassen',
                    'Belassen (vor Ort belassen)': 'Belassen',
                    'ARM': 'ARM',
                    'ARM (Anderes Rettungsmittel)': 'ARM',
                    'PVW': 'PVW',
                    'PVW (Patient verweigert)': 'PVW'
                };
                const abbr = outcomeMap[mission.outcome] || mission.outcome;
                let display = `<div><strong>Ausgang:</strong> <span style="color: #4CAF50; font-weight: 600;">${abbr}</span></div>`;

                if ((mission.outcome === 'ARM' || mission.outcome === 'ARM (Anderes Rettungsmittel)') && mission.arm_id) {
                    display += `<div><strong>ARM:</strong> Typ: ${mission.arm_type || '?'}, Kennung: ${mission.arm_id}</div>`;
                }
                return display;
            })()}
            </div>
            </div>
            ${mission.description ? `<div class="mission-desc">${mission.description}</div>` : ''}
            ${mission.notes ? `<div class="mission-notes">Note: ${mission.notes}</div>` : ''}
        `;
        container.appendChild(card);
    });
}

function openNewMissionModal() {
    document.getElementById('new-mission-form').reset();
    document.getElementById('edit-mission-id').value = '';
    document.getElementById('mission-modal-title').innerText = "Neuer Einsatz"; // Set Title for New


    // Populate Checkboxes
    // Populate Checkboxes - Horizontal Layout with Badges
    const container = document.getElementById('m-squad-select');
    container.innerHTML = '';

    // Reset buttons visibility
    document.getElementById('btn-delete-mission').style.display = 'none';
    document.getElementById('btn-complete-mission').style.display = 'none';

    // Always show outcome group, reset value
    const outcomeGroup = document.getElementById('outcome-group');
    outcomeGroup.style.display = 'none';
    document.getElementById('m-outcome').value = "";

    // Inline Flex container style
    container.style.display = 'flex';
    container.style.flexWrap = 'wrap';
    container.style.gap = '1rem';

    const statusMap = {
        '2': { label: 'EB', class: 's2' },
        '3': { label: 'zBO', class: 's3' },
        '4': { label: 'BO', class: 's4' },
        '7': { label: 'zAO', class: 's7' },
        '8': { label: 'AO', class: 's8' },
        'Pause': { label: 'Pause', class: 'sP' },
        'NEB': { label: 'NEB', class: 'sNEB' },
        '1': { label: 'Frei', class: 's1' }
    };

    squadsData.forEach(s => {
        const div = document.createElement('div');
        div.className = 'squad-select-item';

        const st = statusMap[s.current_status] || { label: s.current_status, class: 's1' };

        div.innerHTML = `
            <button type="button" class="squad-select-btn" data-squad-id="${s.id}" onclick="toggleSquadSelection(this)">
                <span class="squad-name">${s.name}</span>
                <span class="mini-status ${st.class}">${st.label}</span>
            </button>
        `;
        container.appendChild(div);
    });
    document.getElementById('new-mission-modal').classList.add('open');
}

function toggleSquadSelection(button) {
    button.classList.toggle('selected');
}

function editMission(mission) {
    document.getElementById('new-mission-form').reset();
    document.getElementById('edit-mission-id').value = mission.id;
    document.getElementById('mission-modal-title').innerText = "Einsatz bearbeiten"; // Set Title for Edit


    document.getElementById('m-number').value = mission.mission_number || '';
    document.getElementById('m-location').value = mission.location;
    document.getElementById('m-entity').value = mission.alarming_entity || '';
    document.getElementById('m-reason').value = mission.reason;
    document.getElementById('m-desc').value = mission.description || '';
    document.getElementById('m-notes').value = mission.notes || '';

    // Checkboxes - Horizontal Layout with Badges (same as new mission)
    const container = document.getElementById('m-squad-select');
    container.innerHTML = '';

    // Inline Flex container style
    container.style.display = 'flex';
    container.style.flexWrap = 'wrap';
    container.style.gap = '1rem';

    const statusMap = {
        '2': { label: 'EB', class: 's2' },
        '3': { label: 'zBO', class: 's3' },
        '4': { label: 'BO', class: 's4' },
        '7': { label: 'zAO', class: 's7' },
        '8': { label: 'AO', class: 's8' },
        'Pause': { label: 'Pause', class: 'sP' },
        'NEB': { label: 'NEB', class: 'sNEB' },
        '1': { label: 'Frei', class: 's1' }
    };

    squadsData.forEach(s => {
        const isSelected = mission.squad_ids.includes(s.id);
        const div = document.createElement('div');
        div.className = 'squad-select-item';

        const st = statusMap[s.current_status] || { label: s.current_status, class: 's1' };

        div.innerHTML = `
            <button type="button" class="squad-select-btn ${isSelected ? 'selected' : ''}" data-squad-id="${s.id}" onclick="toggleSquadSelection(this)">
                <span class="squad-name">${s.name}</span>
                <span class="mini-status ${st.class}">${st.label}</span>
            </button>
        `;
        container.appendChild(div);
    });

    // Show outcome field and complete button if mission is not yet completed
    const outcomeGroup = document.getElementById('outcome-group');
    const completeBtn = document.getElementById('btn-complete-mission');

    // Always show outcome group
    outcomeGroup.style.display = 'block';

    if (mission.status !== 'Abgeschlossen') {
        completeBtn.style.display = 'inline-block';
    } else {
        completeBtn.style.display = 'none';
    }

    // Always populate outcome if exists
    if (mission.outcome) {
        document.getElementById('m-outcome').value = mission.outcome;
        outcomeGroup.style.display = 'block'; // Ensure visible if we have data
    }

    // Show Delete button for editing
    document.getElementById('btn-delete-mission').style.display = 'inline-block';

    // Add Status Dropdown if Edit
    // (Simplification: User asks to edit mission. We can reuse form but what about Status? 
    // Usually status is handled via "Finish" button but user says "Edit Mission". 
    // Let's add a status selector if editing)

    let statusDiv = document.getElementById('edit-status-group');
    if (!statusDiv) {
        statusDiv = document.createElement('div');
        statusDiv.id = 'edit-status-group';
        statusDiv.className = 'form-group';
        const btnGroup = document.getElementById('new-mission-form').querySelector('button[type="submit"]').parentNode;
        btnGroup.parentNode.insertBefore(statusDiv, btnGroup);
    }

    // Only show status dropdown if mission is already completed (to allow re-opening)
    // or if we want to allow changing status manually. 
    // User requested: "Status not selectable if mission is running".
    // So if running, hide it (or show text only). Defaults to 'Laufend' implicitly if not sent.

    statusDiv.innerHTML = '';
    if (mission.status === 'Abgeschlossen') {
        statusDiv.innerHTML = `
            <label>Status</label>
            <select id="m-status">
                <option value="Laufend">Laufend (Wiedereröffnen)</option>
                <option value="Abgeschlossen" selected>Abgeschlossen</option>
            </select>
        `;
    } else {
        // If running, don't show the dropdown at all. 
        // User must use "Abschließen" button to complete.
        // We might show a static label though?
        // Let's just hide it as requested "nicht auswählbar".
        statusDiv.innerHTML = '';
    }

    document.getElementById('new-mission-modal').classList.add('open');
}

function openCompleteMissionModal(id) {
    document.getElementById('complete-mission-id').value = id;
    document.getElementById('complete-mission-outcome').value = '';
    // Reset ARM fields
    document.getElementById('arm-fields').style.display = 'none';
    document.getElementById('arm-id').value = '';
    document.getElementById('arm-type').value = '';
    document.getElementById('complete-mission-modal').classList.add('open');
}

function toggleArmFields() {
    const outcome = document.getElementById('complete-mission-outcome').value;
    const armGroup = document.getElementById('arm-fields');
    if (outcome === 'ARM' || outcome === 'ARM (Anderes Rettungsmittel)') {
        armGroup.style.display = 'block';
    } else {
        armGroup.style.display = 'none';
    }
}

async function submitCompletion() {
    const id = document.getElementById('complete-mission-id').value;
    const outcome = document.getElementById('complete-mission-outcome').value;

    if (!outcome) {
        alert('Bitte wählen Sie einen Ausgang aus.');
        return;
    }

    const payload = {
        status: 'Abgeschlossen',
        outcome: outcome
    };

    if (outcome === 'ARM' || outcome === 'ARM (Anderes Rettungsmittel)') {
        const armId = document.getElementById('arm-id').value;
        const armType = document.getElementById('arm-type').value;

        // Fields are optional now
        if (armId) payload.arm_id = armId;
        if (armType) payload.arm_type = armType;
    }

    try {
        await fetch(`/api/missions/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        closeModal('complete-mission-modal');
        loadData();
    } catch (e) {
        console.error("Completion failed:", e);
        alert("Fehler beim Abschließen des Einsatzes.");
    }
}

async function submitMission(e) {
    e.preventDefault();
    const id = document.getElementById('edit-mission-id').value;

    // Get selected squads from buttons
    const squadIds = Array.from(document.querySelectorAll('#m-squad-select .squad-select-btn.selected'))
        .map(btn => parseInt(btn.dataset.squadId));

    const payload = {
        mission_number: document.getElementById('m-number').value,
        location: document.getElementById('m-location').value,
        alarming_entity: document.getElementById('m-entity').value,
        reason: document.getElementById('m-reason').value,
        description: document.getElementById('m-desc').value,
        notes: document.getElementById('m-notes').value,
        outcome: document.getElementById('m-outcome').value || null,
        squad_ids: squadIds
    };

    try {
        let response;
        if (id) {
            // Edit
            const statusEl = document.getElementById('m-status');
            if (statusEl) payload.status = statusEl.value;

            response = await fetch(`/api/missions/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        } else {
            // Create
            response = await fetch('/api/missions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        }

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || 'Serverfehler beim Speichern');
        }

        // Only close and reload if successful
        // Remove status selector if added
        const statusDiv = document.getElementById('edit-status-group');
        if (statusDiv) statusDiv.remove();

        // Hide outcome group - NO, keep it visible for next usage or reset is handled by open
        // document.getElementById('outcome-group').style.display = 'none';
        document.getElementById('btn-complete-mission').style.display = 'none';

        closeModal('new-mission-modal');
        loadData();

    } catch (error) {
        console.error('Error submitting mission:', error);
        alert('Fehler beim Speichern: ' + error.message);
    }
}

async function completeMission() {
    const id = document.getElementById('edit-mission-id').value;
    if (!id) return;

    // Validate outcome is selected
    const outcomeEl = document.getElementById('m-outcome');
    if (!outcomeEl.value) {
        alert('Bitte wählen Sie einen Ausgang für den Einsatz aus.');
        return;
    }

    // Get selected squads from buttons
    const squadIds = Array.from(document.querySelectorAll('#m-squad-select .squad-select-btn.selected'))
        .map(btn => parseInt(btn.dataset.squadId));

    const payload = {
        mission_number: document.getElementById('m-number').value,
        location: document.getElementById('m-location').value,
        alarming_entity: document.getElementById('m-entity').value,
        reason: document.getElementById('m-reason').value,
        description: document.getElementById('m-desc').value,
        notes: document.getElementById('m-notes').value,
        squad_ids: squadIds,
        status: 'Abgeschlossen',
        outcome: outcomeEl.value
    };

    await fetch(`/api/missions/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    // Remove status selector if added
    const statusDiv = document.getElementById('edit-status-group');
    if (statusDiv) statusDiv.remove();

    // Hide outcome group
    document.getElementById('outcome-group').style.display = 'none';
    document.getElementById('btn-complete-mission').style.display = 'none';

    // Hide outcome group
    document.getElementById('outcome-group').style.display = 'none';
    document.getElementById('btn-complete-mission').style.display = 'none';

    closeModal('new-mission-modal');
    loadData();
}


function openDeleteMissionModal() {
    document.getElementById('delete-mission-reason').value = '';
    document.getElementById('delete-mission-modal').classList.add('open');
}

async function confirmDeleteMission() {
    const id = document.getElementById('edit-mission-id').value;
    const reason = document.getElementById('delete-mission-reason').value;

    if (!reason.trim()) {
        alert("Bitte geben Sie eine Begründung an.");
        return;
    }

    try {
        await fetch(`/api/missions/${id}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: reason })
        });

        closeModal('delete-mission-modal');
        closeModal('new-mission-modal');
        loadData();
    } catch (e) {
        console.error("Delete failed:", e);
        alert("Fehler beim Löschen.");
    }
}



// --- Logs ---

async function openLogModal() {
    const response = await fetch('/api/changes');
    const logs = await response.json();

    const tbody = document.querySelector('#log-table tbody');
    tbody.innerHTML = '';

    logs.forEach(l => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${new Date(l.timestamp).toLocaleTimeString()}</td>
            <td>${l.action}</td>
            <td>${l.details}</td>
        `;
        tbody.appendChild(row);
    });

    document.getElementById('log-modal').classList.add('open');
}

async function updateLastLog() {
    const response = await fetch('/api/changes');
    const logs = await response.json();
    if (logs.length > 0) {
        document.getElementById('last-log').textContent =
            `${new Date(logs[0].timestamp).toLocaleTimeString()} - ${logs[0].details}`;
    }
}

// --- Utils ---

function populateDatalists() {
    for (const [key, values] of Object.entries(optionsData)) {
        const list = document.getElementById(`list-${key}`);
        if (list) {
            list.innerHTML = '';
            values.forEach(val => {
                const opt = document.createElement('option');
                opt.value = val;
                list.appendChild(opt);
            });
        }
    }
}

function closeModal(id) {
    document.getElementById(id).classList.remove('open');
    if (id === 'new-mission-modal') {
        const statusDiv = document.getElementById('edit-status-group');
        if (statusDiv) statusDiv.remove();
    }
}

// Weather Functionality
async function initWeather() {
    // 1. Try Geolocation
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => startWeatherUpdates(pos.coords.latitude, pos.coords.longitude),
            (err) => {
                console.warn("Weather location denied, falling back to IP:", err);
                useIpLocation();
            },
            { timeout: 5000 } // Don't wait forever
        );
    } else {
        useIpLocation();
    }
}

async function useIpLocation() {
    try {
        // Fallback: Use IP-based location (e.g., ip-api.com is free for non-commercial)
        // Or default to Berlin/Germany as generic fallback
        const res = await fetch('https://ipapi.co/json/');
        const data = await res.json();
        if (data.latitude && data.longitude) {
            startWeatherUpdates(data.latitude, data.longitude);
        } else {
            console.warn("IP location failed, defaulting to Berlin");
            startWeatherUpdates(52.52, 13.405);
        }
    } catch (e) {
        console.error("IP fallback failed:", e);
        startWeatherUpdates(52.52, 13.405); // Final Fallback
    }
}

function startWeatherUpdates(lat, lon) {
    fetchWeather(lat, lon);
    setInterval(() => fetchWeather(lat, lon), 30 * 60 * 1000);
}

async function fetchWeather(lat, lon) {
    try {
        const res = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`);
        const data = await res.json();
        const weather = data.current_weather;
        updateWeatherUI(weather.temperature, weather.weathercode);
    } catch (e) {
        console.error("Weather fetch failed:", e);
    }
}

function updateWeatherUI(temp, code) {
    const widget = document.getElementById('weather-widget');
    const iconEl = document.getElementById('weather-icon');
    const tempEl = document.getElementById('weather-temp');

    // WMO Weather Code Mapping
    let icon = '☀️';
    if (code >= 1 && code <= 3) icon = '⛅';
    else if (code >= 45 && code <= 48) icon = '🌫️';
    else if (code >= 51 && code <= 55) icon = '🌦️';
    else if (code >= 61 && code <= 67) icon = '🌧️';
    else if (code >= 71 && code <= 77) icon = '🌨️';
    else if (code >= 80 && code <= 82) icon = '🌧️';
    else if (code >= 95 && code <= 99) icon = '⛈️';

    iconEl.textContent = icon;
    tempEl.textContent = `${Math.round(temp)}°C`;
    widget.classList.remove('hidden');
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    initWeather();
});

// --- Drag and Drop for Squads ---

let dragSrcEl = null;

function handleDragStart(e) {
    dragSrcEl = this;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', this.innerHTML);
    this.classList.add('dragging');
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDragEnter(e) {
    this.classList.add('over');
}

function handleDragLeave(e) {
    this.classList.remove('over');
}

function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }

    if (dragSrcEl !== this) {
        // Swap DOM elements
        const container = document.getElementById('squad-list');
        const cards = Array.from(container.children);
        const srcIndex = cards.indexOf(dragSrcEl);
        const targetIndex = cards.indexOf(this);

        if (srcIndex < targetIndex) {
            container.insertBefore(dragSrcEl, this.nextSibling);
        } else {
            container.insertBefore(dragSrcEl, this);
        }

        // Save new order
        saveSquadOrder();
    }

    return false;
}

function handleDragEnd(e) {
    const listItems = document.querySelectorAll('.squad-card');
    [].forEach.call(listItems, function (col) {
        col.classList.remove('over');
        col.classList.remove('dragging');
    });
}

// Add global dragend listener since 'drop' handles the drop logic but 'dragend' cleanup is safer on source
document.addEventListener('dragend', function (e) {
    if (e.target.classList.contains('squad-card')) {
        handleDragEnd(e);
    }
});

async function saveSquadOrder() {
    const container = document.getElementById('squad-list');
    const cards = Array.from(container.children);
    const order = cards.map(card => parseInt(card.dataset.id));

    try {
        await fetch('/api/squads/reorder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order: order })
        });
    } catch (e) {
        console.error("Order save failed:", e);
    }
}

// --- Drag Squad to Mission ---

function allowDrop(e) {
    e.preventDefault();
}

async function handleMissionDrop(e, mission) {
    e.preventDefault();
    if (!dragSrcEl || !dragSrcEl.classList.contains('squad-card')) return;

    const squadId = parseInt(dragSrcEl.dataset.id);
    if (!squadId) return;

    // Check if squad already assigned?
    const alreadyAssigned = mission.squads.some(s => s.id === squadId);
    if (alreadyAssigned) return;

    try {
        // 1. Update Mission: Add Squad
        const currentSquadIds = mission.squads.map(s => s.id);
        const newSquadIds = [...currentSquadIds, squadId];

        await fetch(`/api/missions/${mission.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ squad_ids: newSquadIds })
        });

        // 2. Update Squad Status to '3' (zBO)
        await fetch(`/api/squads/${squadId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: '3' }) // zBO
        });

        loadData();
    } catch (err) {
        console.error("Failed to assign squad to mission:", err);
        alert("Fehler beim Zuweisen des Trupps.");
    }
}

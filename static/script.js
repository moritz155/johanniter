let squadsData = [];
let missionsData = [];
let optionsData = {};
let configData = null;

document.addEventListener('DOMContentLoaded', () => {
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
    const loc = document.getElementById('conf-location').value;
    const addr = document.getElementById('conf-address').value;
    const start = document.getElementById('conf-start').value;
    const sqRaw = document.getElementById('conf-squads').value;

    // Default location if empty (optional)
    const finalLoc = loc.trim() || 'Dienst ' + new Date().toLocaleDateString();

    const squads = sqRaw.split(',').map(s => s.trim()).filter(s => s).map(s => ({ name: s }));

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

function openShiftSetup() {
    document.getElementById('shift-setup-modal').classList.add('open');
}

function openTutorial() {
    document.getElementById('tutorial-modal').classList.add('open');
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
    if (!confirm("Möchten Sie den Dienst wirklich beenden? Dies wird den aktuellen Status deaktivieren.")) return;

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
            locInfo = `Einsatz #${squad.active_mission.mission_number || squad.active_mission.id} (${squad.active_mission.location})`;
        }

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

async function setSquadStatus(id, status) {
    await fetch(`/api/squads/${id}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status })
    });
    // Optimistic update or reload? Reload is safer for sync
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
            '1': { label: 'Frei', class: 's1' } // Fallback
        };

        const squadsHtml = mission.squads.map(sq => {
            // sq is now {name, id, status}
            // Only show status badge if mission is not completed
            if (mission.status === 'Abgeschlossen') {
                return `<span class="squad-tag">${sq.name}</span>`;
            } else {
                const st = statusMap[sq.status] || { label: sq.status, class: 's1' };
                return `<span class="squad-tag">
                    ${sq.name} <span class="mini-status ${st.class}">${st.label}</span>
                </span>`;
            }
        }).join(' ');

        card.innerHTML = `
            <div class="mission-header">
                <span class="mission-id">#${mission.mission_number || mission.id}</span>
                <span class="mission-time">${date}</span>
                <span class="mission-status-badge ${mission.status}">${mission.status}</span>
                <button class="edit-btn" onclick='editMission(${JSON.stringify(mission)})'>✎</button>
            </div>
            <div class="mission-details">
                <div><strong>Ort:</strong> ${mission.location}</div>
                <div><strong>Grund:</strong> ${mission.reason}</div>
                <div class="full-width"><strong>Trupps:</strong> <div style="display:inline-flex; gap:0.5rem; flex-wrap:wrap;">${squadsHtml}</div></div>
                ${mission.alarming_entity ? `<div><strong>Alarm:</strong> ${mission.alarming_entity}</div>` : ''}
                ${mission.outcome ? `<div><strong>Ausgang:</strong> <span style="color: #4CAF50; font-weight: 600;">${mission.outcome}</span></div>` : ''}
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

    // Populate Checkboxes
    // Populate Checkboxes - Horizontal Layout with Badges
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

    if (mission.status !== 'Abgeschlossen') {
        outcomeGroup.style.display = 'block';
        completeBtn.style.display = 'inline-block';

        // Set outcome value if already set
        const outcomeSelect = document.getElementById('m-outcome');
        if (mission.outcome) {
            outcomeSelect.value = mission.outcome;
        }
    } else {
        outcomeGroup.style.display = 'none';
        completeBtn.style.display = 'none';
    }

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

    statusDiv.innerHTML = `
        <label>Status</label>
        <select id="m-status">
            <option value="Laufend" ${mission.status === 'Laufend' ? 'selected' : ''}>Laufend</option>
            <option value="Abgeschlossen" ${mission.status === 'Abgeschlossen' ? 'selected' : ''}>Abgeschlossen</option>
        </select>
    `;

    document.getElementById('new-mission-modal').classList.add('open');
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
        squad_ids: squadIds
    };

    if (id) {
        // Edit
        const statusEl = document.getElementById('m-status');
        if (statusEl) payload.status = statusEl.value;

        // Include outcome if provided
        const outcomeEl = document.getElementById('m-outcome');
        if (outcomeEl && outcomeEl.value) {
            payload.outcome = outcomeEl.value;
        }

        await fetch(`/api/missions/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    } else {
        // Create
        await fetch('/api/missions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    }

    // Remove status selector if added
    const statusDiv = document.getElementById('edit-status-group');
    if (statusDiv) statusDiv.remove();

    // Hide outcome group
    document.getElementById('outcome-group').style.display = 'none';
    document.getElementById('btn-complete-mission').style.display = 'none';

    closeModal('new-mission-modal');
    loadData();
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

    closeModal('new-mission-modal');
    loadData();
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

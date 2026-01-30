let squadsData = [];
let missionsData = [];
let optionsData = {};
let configData = null;

// GLOBAL FETCH INTERCEPTOR for Session Robustness
const originalFetch = window.fetch;
window.fetch = async function (url, options = {}) {
    const sid = localStorage.getItem('session_id');
    if (sid) {
        options.headers = options.headers || {};
        // Handle Headers object or plain object
        if (options.headers instanceof Headers) {
            options.headers.append('X-Session-ID', sid);
        } else if (Array.isArray(options.headers)) {
            options.headers.push(['X-Session-ID', sid]);
        } else {
            options.headers['X-Session-ID'] = sid;
        }
    }

    // Ensure cookies are sent for session affinity
    if (!options.credentials) {
        options.credentials = 'same-origin';
    }

    return originalFetch(url, options);
};

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
    fetchWeather(); // Fetch once on load
    setInterval(fetchWeather, 600000); // Refresh every 10 mins
    setInterval(updateClock, 1000);
    setInterval(updateTimers, 1000);
    setInterval(loadData, 5000); // Polling for live updates
    checkMobile(); // Check initial view
});

async function loadData() {
    try {
        const response = await fetch('/api/init');
        const data = await response.json();

        // DEBUG: Temporary diagnostic
        const lsID = localStorage.getItem('session_id');
        const configID = data.config ? data.config.session_id : 'null';
        // if (!data.config) alert(`DEBUG: Load Failed! Config is NULL.\nLocal Session: ${lsID}\nServer returned: ${configID}`);

        configData = data.config;
        if (configData && configData.session_id) {
            localStorage.setItem('session_id', configData.session_id);
        }

        squadsData = data.squads;

        // Preserve active edits in missionsData
        if (document.activeElement && document.activeElement.hasAttribute('data-mission-id')) {
            const activeId = parseInt(document.activeElement.dataset.missionId);
            const activeField = document.activeElement.dataset.field; // "location", "notes", etc

            if (activeId && activeField) {
                const incomingMission = data.missions.find(m => m.id === activeId);
                if (incomingMission) {
                    // Overwrite incoming data with current DOM value to prevent reversion
                    console.log(`Preserving active edit for Mission ${activeId} Field ${activeField}`);
                    incomingMission[activeField] = document.activeElement.innerText;
                }
            }
        }

        // Merge Strategy: Respect recent local edits (Grace Period 5s)
        const now = Date.now();
        const grace = 5000;
        const localMap = new Map(missionsData.map(m => [m.id, m]));

        missionsData = data.missions.map(serverM => {
            const localM = localMap.get(serverM.id);
            if (localM) {
                if (localM._lastEdit_notes && (now - localM._lastEdit_notes < grace)) {
                    // console.log("Preserving local notes for", serverM.id);
                    serverM.notes = localM.notes;
                    serverM._lastEdit_notes = localM._lastEdit_notes;
                }
                if (localM._lastEdit_description && (now - localM._lastEdit_description < grace)) {
                    serverM.description = localM.description;
                    serverM._lastEdit_description = localM._lastEdit_description;
                }
                if (localM._lastEdit_location && (now - localM._lastEdit_location < grace)) {
                    serverM.location = localM.location;
                    serverM._lastEdit_location = localM._lastEdit_location;
                }
            }
            return serverM;
        });

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
            checkMobile(); // Update mobile view just in case
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
    const pwd = document.getElementById('conf-password').value;
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
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                location: finalLoc,
                address: addr,
                password: pwd,
                start_time: start || null,
                squads: squads
            })
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || "Serverfehler beim Setup");
        }

        const data = await response.json();
        if (data.session_id) {
            localStorage.setItem('session_id', data.session_id);
        }

        closeModal('shift-setup-modal');
        document.getElementById('welcome-screen').classList.remove('active');
        loadData();
    } catch (error) {
        console.error('Error starting shift:', error);
        alert("Fehler: " + error.message);
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
    document.getElementById('conf-password').value = ''; // Reset
}

function openJoinModal() {
    document.getElementById('join-modal').classList.add('open');
    document.getElementById('join-password').value = '';
}

async function joinShift(e) {
    e.preventDefault();
    const pwd = document.getElementById('join-password').value;

    if (!pwd) {
        alert("Bitte Passwort eingeben.");
        return;
    }

    try {
        const response = await fetch('/api/join', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: pwd })
        });

        const data = await response.json();

        if (data.success) {
            if (data.session_id) {
                localStorage.setItem('session_id', data.session_id);
            }
            closeModal('join-modal');
            document.getElementById('welcome-screen').classList.remove('active');
            // Reload data to sync with the session we just joined
            loadData();
        } else {
            alert(data.message || "Beitritt fehlgeschlagen.");
        }
    } catch (error) {
        console.error("Join error:", error);
        alert("Verbindungsfehler beim Beitreten.");
    }
}

// --- Guide / Tour System ---
// --- Tutorial System ---
let currentTutorialStep = 0;
const totalTutorialSteps = 5;

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

async function fetchWeather() {
    const debugEl = document.getElementById('weather-debug');
    const widget = document.getElementById('weather-widget');

    // Unhide immediately so we can see "Start..."
    if (widget) widget.classList.remove('hidden');
    if (debugEl) debugEl.textContent = "Start...";

    // Default to Berlin (Johanniter HQ area approx)
    let lat = 52.52;
    let lon = 13.41;

    // Try to get actual location
    if (navigator.geolocation) {
        if (debugEl) debugEl.textContent = "Locating...";
        try {
            const position = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 });
            });
            lat = position.coords.latitude;
            lon = position.coords.longitude;
            if (debugEl) debugEl.textContent = "Loc: OK";
        } catch (e) {
            console.log("Geolocation denied or error, using default.");
            if (debugEl) debugEl.textContent = "Loc: Fail/Def";
        }
    }

    try {
        if (debugEl) debugEl.textContent += " Fetching...";
        // api.open-meteo.com is free and needs no key
        const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true&timezone=auto&_=${new Date().getTime()}`;
        console.log(`Fetching weather from: ${url}`);

        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();

        if (data.current_weather) {
            const temp = Math.round(data.current_weather.temperature);
            const code = data.current_weather.weathercode;
            const isDay = data.current_weather.is_day; // 1 = Day, 0 = Night
            console.log(`Weather: ${temp}°C, Code: ${code}, isDay: ${isDay}`);

            // Map codes to icons
            let icon = '❓';

            // Function to choose day/night icon
            const getIcon = (d, n) => isDay === 1 ? d : n;

            if (code === 0) icon = getIcon('☀️', '🌙'); // Clear sky
            else if (code === 1) icon = getIcon('🌤️', '🌙'); // Mainly clear
            else if (code === 2) icon = getIcon('⛅', '🌙'); // Partly cloudy (Moon preferred at night)
            else if (code === 3) icon = '☁️'; // Overcast
            else if (code === 45 || code === 48) icon = '🌫️'; // Fog
            else if (code >= 51 && code <= 67) icon = '🌧️'; // Drizzle / Rain
            else if (code >= 71 && code <= 77) icon = '🌨️'; // Snow
            else if (code >= 80 && code <= 82) icon = '🌦️'; // Rain showers
            else if (code >= 85 && code <= 86) icon = '❄️'; // Snow showers
            else if (code >= 95) icon = '⛈️'; // Thunderstorm

            const widget = document.getElementById('weather-widget');
            const iconEl = document.getElementById('weather-icon');
            const tempEl = document.getElementById('weather-temp');

            if (widget && iconEl && tempEl) {
                iconEl.textContent = icon;
                tempEl.textContent = `${temp}°C`;

                // Visible Debug Info
                if (debugEl) {
                    debugEl.textContent = `[C:${code} D:${isDay}]`;
                    debugEl.style.color = isDay === 1 ? 'yellow' : 'cyan';
                }

                // Tooltip
                widget.title = `Code: ${code}, Day: ${isDay} (1=Day, 0=Night). Click for details.`;
                widget.classList.remove('hidden');

                // Update global coords for click handler
                window.weatherLat = lat;
                window.weatherLon = lon;

                console.log(`Weather Updated: ${icon} ${temp}°C (Code: ${code}, Day: ${isDay})`);
            }
        }
    } catch (error) {
        console.error('Error fetching weather:', error);
        if (debugEl) debugEl.textContent = `Err: ${error.message}`;
    }
}

// Global click handler (attached once)
document.addEventListener('DOMContentLoaded', () => {
    // Refresh Button
    const refreshBtn = document.getElementById('refresh-weather');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent widget click
            fetchWeather();
        });
    }

    // Widget Click (Link)
    const widget = document.getElementById('weather-widget');
    if (widget) {
        widget.addEventListener('click', () => {
            const lat = window.weatherLat || 52.52;
            const lon = window.weatherLon || 13.41;
            // Meteoblue URL with specific coordinates
            const weatherUrl = `https://www.meteoblue.com/en/weather/week/index?lat=${lat}&lon=${lon}`;
            window.open(weatherUrl, '_blank');
        });
    }
});

// --- Custom Log Event ---
function addCustomLogEvent() {
    document.getElementById('custom-event-input').value = '';
    document.getElementById('custom-event-modal').classList.add('open');
    // Focus after opening
    setTimeout(() => document.getElementById('custom-event-input').focus(), 100);
}

async function submitCustomEvent(e) {
    e.preventDefault();
    const text = document.getElementById('custom-event-input').value.trim();
    if (!text) return;

    try {
        await fetch('/api/logs/custom', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ details: text })
        });

        closeModal('custom-event-modal');
        // Reload logs if we are in the log modal
        loadData();
    } catch (error) {
        console.error("Error adding custom log:", error);
        alert("Fehler beim Speichern des Ereignisses.");
    }
}


// --- Squads ---

function renderSquads() {
    const container = document.getElementById('squad-list');

    // 1. Remove squads that are no longer in data
    const activeIds = new Set(squadsData.map(s => s.id));
    Array.from(container.children).forEach(child => {
        const id = parseInt(child.dataset.id);
        if (!activeIds.has(id)) {
            child.remove();
        }
    });

    // 2. Update or Create squads
    squadsData.forEach(squad => {
        let card = document.getElementById(`squad-card-${squad.id}`);
        const isNew = !card;

        if (isNew) {
            card = document.createElement('div');
            card.id = `squad-card-${squad.id}`;
            card.className = 'squad-card';
            card.dataset.id = squad.id;
            card.setAttribute('draggable', true);

            // Drag Events
            card.addEventListener('dragstart', handleDragStart);
            card.addEventListener('dragover', handleDragOver);
            card.addEventListener('drop', handleDrop);
            card.addEventListener('dragenter', handleDragEnter);
            card.addEventListener('dragleave', handleDragLeave);

            container.appendChild(card);
        }

        // Generate Content
        let contentHtml = '';

        // --- AMBULANZ Logic ---
        if (squad.type === 'Ambulanz') {
            const ambulanzStatuses = [
                { code: '2', label: 'EB', class: 's2' },
                { code: 'NEB', label: 'NEB', class: 'sNEB' },
                { code: '4', label: 'Besetzt', class: 's4' }
            ];

            let buttonsHtml = '';
            ambulanzStatuses.forEach(st => {
                const active = squad.current_status === st.code ? 'active' : '';
                buttonsHtml += `<button class="status-btn ${st.class} ${active}" 
                    onclick="setSquadStatus(${squad.id}, '${st.code}')">${st.label}</button>`;
            });

            const patCount = squad.patient_count || 0;
            const infoText = `<strong>Patienten: ${patCount}</strong>`;

            contentHtml = `
                <div class="squad-info">
                    <div style="display:flex; align-items:center; gap: 0.5rem;">
                        <h3>${squad.name} <span style="font-size:0.8em; opacity:0.7;">(BHP)</span></h3>
                         <button class="icon-btn tiny" onclick='editSquad(${JSON.stringify(squad).replace(/'/g, "&#39;")})' title="Bearbeiten">✎</button>
                    </div>
                    <div class="squad-status-text status-${squad.current_status}" style="cursor:default;">${infoText}</div>
                    <div class="squad-actions">
                        ${buttonsHtml}
                    </div>
                </div>
                 <div class="squad-timer" id="timer-${squad.id}" data-change="${squad.last_status_change}" style="margin-right: 1.5rem;">00:00</div>
            `;

        } else {
            // --- TRUPP Logic ---
            const statuses = [
                { code: '2', label: 'EB', class: 's2' },
                { code: '3', label: 'zBO', class: 's3' },
                { code: '4', label: 'BO', class: 's4' },
                { code: '7', label: 'zAO', class: 's7' },
                { code: '8', label: 'AO', class: 's8' },
                { code: 'Pause', label: 'Pause', class: 'sP' },
                { code: 'NEB', label: 'NEB', class: 'sNEB' }
            ];

            let locInfo = squad.current_status;
            const statusMap = {
                '2': 'Einsatzbereit', '3': 'Zum Berufungsort', '4': 'Am Berufungsort',
                '7': 'Zum Abgabeort', '8': 'Am Abgabeort', 'Pause': 'Pause',
                'NEB': 'Nicht Einsatzbereit', 'Integriert': 'Disponiert'
            };

            if (squad.active_mission) {
                let leftPart = "";
                let rightPart = "";

                let destName = "BHP";
                if (squad.custom_location) {
                    destName = squad.custom_location;
                } else {
                    const activeM = squad.active_mission;
                    const fullMission = missionsData.find(m => m.id === activeM.id);
                    if (fullMission && fullMission.squad_ids) {
                        const amb = squadsData.find(s => fullMission.squad_ids.includes(s.id) && s.type === 'Ambulanz');
                        if (amb) destName = amb.name;
                    }
                }

                if (squad.current_status === '7') {
                    const missionNum = squad.active_mission.mission_number || squad.active_mission.id;
                    leftPart = `Einsatz #${missionNum} (${squad.active_mission.location}) - ${squad.active_mission.reason}`;
                    rightPart = "r. " + destName;
                } else if (squad.current_status === '8') {
                    const missionNum = squad.active_mission.mission_number || squad.active_mission.id;
                    leftPart = `Einsatz #${missionNum} (${squad.active_mission.location}) - ${squad.active_mission.reason}`;
                    rightPart = destName;
                } else {
                    leftPart = `Einsatz #${squad.active_mission.mission_number || squad.active_mission.id} - ${squad.active_mission.reason}`;
                    if (squad.current_status === '3') rightPart = "r. " + squad.active_mission.location;
                    else rightPart = squad.active_mission.location;
                }

                if (squad.custom_location && !['3', '4', '7', '8'].includes(squad.current_status)) {
                    rightPart = squad.custom_location;
                }

                locInfo = `<span>${leftPart}</span><span>${rightPart}</span>`;

                const invalidStatuses = ['2', 'Pause', 'NEB'];
                if (invalidStatuses.includes(squad.current_status)) {
                    locInfo += `<span class="status-warning-dot" title="Status prüfen!"></span>`;
                }
            } else {
                if (statusMap[squad.current_status]) {
                    const defaultText = statusMap[squad.current_status];
                    let rightPart = "";

                    if (['3', '4', '7', '8'].includes(squad.current_status)) {
                        let destName = squad.custom_location || "BHP";
                        if (squad.current_status === '7') rightPart = "r. " + destName;
                        else if (squad.current_status === '8') rightPart = destName;
                        else if (['3', '4'].includes(squad.current_status)) {
                            const completedMissions = missionsData
                                .filter(m => m.status === 'Abgeschlossen' && m.squad_ids && m.squad_ids.includes(squad.id))
                                .sort((a, b) => (b.id) - (a.id));
                            const lastMission = completedMissions.length > 0 ? completedMissions[0] : null;
                            if (squad.current_status === '3') rightPart = lastMission ? ("r. " + lastMission.location) : "r. Standort?";
                            else rightPart = lastMission ? lastMission.location : "Standort?";
                        }
                    } else {
                        if (squad.custom_location) rightPart = squad.custom_location;
                    }

                    if (rightPart) locInfo = `<span>${defaultText}</span><span>${rightPart}</span>`;
                    else locInfo = `<span>${defaultText}</span>`;
                }
            }

            let buttonsHtml = '';
            statuses.forEach(st => {
                let label = st.label;
                let className = st.class;
                if (squad.current_status === 'Integriert' && st.code === '2') {
                    label = 'Disp'; className = 'sDip';
                }
                const active = squad.current_status === st.code ? 'active' : '';
                buttonsHtml += `<button class="status-btn ${className} ${active}" 
                    onclick="setSquadStatus(${squad.id}, '${st.code}')">${label}</button>`;
            });

            const badgeOnClick = `onclick="openLocationModal(${squad.id}, '${squad.custom_location || ''}')"`;
            let badgeClass = `squad-status-text status-${squad.current_status} clickable-badge`;

            contentHtml = `
                <div class="squad-info">
                    <div style="display:flex; align-items:center; gap: 0.5rem;">
                        <h3>${squad.name} <span class="qual-badge">${squad.qualification}</span></h3>
                        <button class="icon-btn tiny" onclick='editSquad(${JSON.stringify(squad).replace(/'/g, "&#39;")})' title="Trupp bearbeiten">✎</button>
                    </div>
                    <div class="${badgeClass}" ${badgeOnClick} title="Klicken um Standort zu ändern">${locInfo}</div>
                    <div class="squad-actions">
                        ${buttonsHtml}
                    </div>
                </div>
                <div class="squad-timer" id="timer-${squad.id}" data-change="${squad.last_status_change}" style="margin-right: 1.5rem;">00:00</div>
            `;
        } // End Else

        // DOM PATCH: Only update if changed
        if (card.innerHTML !== contentHtml) {
            card.innerHTML = contentHtml;
        }
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

let pendingStatusCtx = { id: null, targetStatus: null };
let nebConflictQueue = [];
let currentNebMission = null;

async function setSquadStatus(id, status) {
    // Check for NEB and Active Missions
    // Check for NEB and Active Missions OR Integriert -> EB (2)
    const squad = squadsData.find(s => s.id === id);
    if (!squad) return;

    // --- zAO (Status 7) Interception for Destination Selection ---
    if (status === '7') {
        const ambulanzUnits = squadsData.filter(s => s.type === 'Ambulanz');
        if (ambulanzUnits.length > 0) {
            // Open Destination Modal
            openDestinationModal(id, ambulanzUnits);
            return;
        }
    }

    if (status === 'NEB' || status === '2') {
        // Find ALL active missions this squad is in
        const activeMissions = missionsData.filter(m =>
            m.status !== 'Abgeschlossen' && m.squad_ids.includes(id)
        );

        if (activeMissions.length > 0) {
            pendingStatusCtx = { id: id, targetStatus: status };
            nebConflictQueue = [...activeMissions];
            processNextNebConflict();
            return;
        }
    }

    // Normal path
    await performStatusUpdate(id, status);
}

// Destination Selection Logic
let pendingDestinationSquadId = null;

function openDestinationModal(squadId, ambulanzUnits) {
    pendingDestinationSquadId = squadId;
    const container = document.getElementById('destination-options');
    container.innerHTML = '';

    // 1. Ambulanz Units
    ambulanzUnits.forEach(unit => {
        const patCount = unit.patient_count || 0;
        const btn = document.createElement('div');
        btn.className = 'destination-btn';
        if (patCount > 0) btn.classList.add('active-patients');

        btn.innerHTML = `
            ${unit.name}
            <small>${patCount} Patienten</small>
        `;
        btn.onclick = () => selectDestination(unit);
        container.appendChild(btn);
    });

    // 2. Custom Separator/Input
    const customDiv = document.createElement('div');
    customDiv.style.gridColumn = "1 / -1";
    customDiv.style.marginTop = "1rem";
    customDiv.style.borderTop = "1px solid #var(--border)";
    customDiv.style.paddingTop = "1rem";

    // Using inline styles for simplicity, or adding classes? keeping it simple for now.
    customDiv.innerHTML = `
        <label style="display:block; margin-bottom:0.5rem; font-weight:bold; color:var(--text);">Oder anderes Ziel:</label>
        <div style="display:flex; gap:0.5rem;">
            <input type="text" id="dest-custom-input" placeholder="z.B. Uniklinik, KH ..." style="flex:1; padding:0.5rem; border:1px solid var(--border); border-radius:4px; font-size:1rem;">
            <button class="btn-primary" onclick="submitCustomDestination()">Setzen</button>
        </div>
    `;
    container.appendChild(customDiv);

    document.getElementById('destination-modal').classList.add('open');
}

async function selectDestination(ambulanzSquad) {
    const sId = pendingDestinationSquadId;
    if (!sId) return;

    closeModal('destination-modal');

    // 1. Set Status to zAO (7)
    await performStatusUpdate(sId, '7');

    // 2. Assign Ambulanz to the ACTIVE mission of this squad
    let squad = squadsData.find(s => s.id === sId);
    if (squad && squad.active_mission) {

        let m = squad.active_mission;

        // Safety: Ensure we have the full mission (with squad_ids)
        if (!m.squad_ids) {
            const fullM = missionsData.find(mis => mis.id === m.id);
            if (fullM) {
                m = fullM;
            } else {
                // Fallback if not found in missionsData (rare)
                // We'll trust the backend add if we just send specific update? 
                // But the API likely replaces the list.
                console.error("Mission not found in local data, cannot safely assign Ambulanz.");
                return;
            }
        }

        if (!m.squad_ids.includes(ambulanzSquad.id)) {
            const newIds = [...m.squad_ids, ambulanzSquad.id];
            try {
                await fetch(`/api/missions/${m.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ squad_ids: newIds })
                });
                console.log(`Assigned ${ambulanzSquad.name} to mission via zAO trigger.`);
            } catch (e) {
                console.error("Error assigning Ambulanz:", e);
                alert("Fehler beim Zuweisen der Ambulanz.");
            }
        }
    }
}

async function submitCustomDestination() {
    const sId = pendingDestinationSquadId;
    if (!sId) return;

    const val = document.getElementById('dest-custom-input').value.trim();
    if (!val) {
        alert("Bitte Ziel eingeben.");
        return;
    }

    closeModal('destination-modal');

    // 1. Set Status to zAO (7)
    await performStatusUpdate(sId, '7');

    // 2. Set Custom Location Override
    try {
        await fetch(`/api/squads/${sId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ custom_location: val })
        });
    } catch (e) {
        console.error("Error setting custom location:", e);
    }
}

function processNextNebConflict() {
    if (nebConflictQueue.length === 0) {
        // Queue finished -> Proceed to set target status
        if (pendingStatusCtx.id) {
            performStatusUpdate(pendingStatusCtx.id, pendingStatusCtx.targetStatus);
            pendingStatusCtx = { id: null, targetStatus: null };
        }
        return;
    }

    currentNebMission = nebConflictQueue.shift();
    const squad = squadsData.find(s => s.id === pendingStatusCtx.id);
    if (!squad || !currentNebMission) return;

    const mNum = currentNebMission.mission_number || currentNebMission.id;
    const target = pendingStatusCtx.targetStatus;

    // Set Modal content based on Target
    const title = document.querySelector('#neb-confirm-modal h2');
    const text = document.getElementById('neb-confirm-text');
    const btnRemove = document.getElementById('btn-neb-remove');
    const btnKeep = document.getElementById('btn-neb-keep');

    if (target === '2') {
        // Active Mission -> EB Case
        if (title) title.textContent = "Trupp ist im Einsatz";
        text.innerHTML = `<strong>${squad.name}</strong> ist aktuell dem Einsatz <strong>#${mNum}</strong> zugewiesen.<br>Wie möchten Sie fortfahren?`;

        btnRemove.textContent = "Aus Einsatz entfernen & EB setzen";
        btnRemove.style.display = 'block';

        btnKeep.textContent = "Im Einsatz behalten & EB setzen";
        btnKeep.style.display = 'block';
    } else {
        // Standard NEB Case
        if (title) title.textContent = "Trupp ist im Einsatz";
        text.innerHTML = `<strong>${squad.name}</strong> ist aktuell dem Einsatz <strong>#${mNum}</strong> zugewiesen.<br>Wie möchten Sie fortfahren?`;

        btnRemove.textContent = "Aus Einsatz entfernen & NEB setzen";
        btnRemove.style.display = 'block';

        btnKeep.textContent = "Im Einsatz behalten & NEB setzen";
        btnKeep.style.display = 'block';
    }

    // Open Modal
    document.getElementById('neb-confirm-modal').classList.add('open');
}

async function resolveNebConflict(action) {
    if (!pendingStatusCtx.id || !currentNebMission) return;
    const sId = pendingStatusCtx.id;
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
    document.getElementById('squad-modal-title').textContent = 'Neuer Trupp';
    document.getElementById('btn-delete-squad').style.display = 'none';
    document.getElementById('btn-show-qr').style.display = 'none';
    document.getElementById('qr-code-container').style.display = 'none';

    document.getElementById('squad-modal').classList.add('open');
}

function editSquad(squad) {
    document.getElementById('s-form').reset();
    document.getElementById('s-id').value = squad.id;
    document.getElementById('s-name').value = squad.name;
    document.getElementById('s-qual').value = squad.qualification;
    document.getElementById('s-numbers').value = squad.service_numbers || '';

    // Set Modal State for Edit
    document.getElementById('squad-modal-title').textContent = 'Trupp bearbeiten';
    document.getElementById('btn-delete-squad').style.display = 'block';
    document.getElementById('btn-show-qr').style.display = 'block';

    // Reset QR Area
    document.getElementById('qr-code-container').style.display = 'none';
    document.getElementById('qrcode').innerHTML = '';

    document.getElementById('squad-modal').classList.add('open');
}

function showSquadQR() {
    const id = document.getElementById('s-id').value;
    const squad = squadsData.find(s => s.id == id);
    if (!squad || !squad.access_token) {
        alert("Kein Access Token gefunden. Bitte Seite aktualisieren.");
        return;
    }

    const container = document.getElementById('qr-code-container');
    const qrDiv = document.getElementById('qrcode');
    const link = document.getElementById('qr-link');

    if (container.style.display === 'block') {
        container.style.display = 'none';
        return;
    }

    qrDiv.innerHTML = '';
    const url = `${window.location.origin}/squad/mobile-view?token=${squad.access_token}`;

    new QRCode(qrDiv, {
        text: url,
        width: 128,
        height: 128
    });

    link.href = url;
    container.style.display = 'block';
}

// Squad Management
function toggleSquadFields() {
    const type = document.getElementById('s-type').value;
    const groupNumbers = document.getElementById('group-numbers');

    // Example: Hide service numbers for Ambulanz if desired?
    // User didn't ask, but Ambulanz usually is a place.
    // Let's keep it visible but maybe optional.
    // If Ambulanz, maybe hide Qualification?
    // Currently just a placeholder function if needed.
}

async function submitSquad(e) {
    e.preventDefault();
    const id = document.getElementById('s-id').value;
    const name = document.getElementById('s-name').value;
    const qual = document.getElementById('s-qual').value;
    const type = document.getElementById('s-type').value; // Get Type
    const numbers = document.getElementById('s-numbers').value;

    const payload = {
        name: name,
        qualification: qual,
        type: type, // Send Type
        service_numbers: numbers
    };

    try {
        let url = '/api/squads';
        let method = 'POST';

        if (id) {
            url = `/api/squads/${id}`;
            method = 'PUT';
        }

        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            closeModal('squad-modal');
            loadData();
        } else {
            console.error('Error saving squad');
        }
    } catch (error) {
        console.error('Error:', error);
    }
}
// --- Manual Location Override ---
function openLocationModal(squadId, currentLocation) {
    document.getElementById('loc-squad-id').value = squadId;
    document.getElementById('loc-manual-input').value = currentLocation || '';
    document.getElementById('location-modal').classList.add('open');
}

async function submitLocationOverride(e) {
    e.preventDefault();
    const id = document.getElementById('loc-squad-id').value;
    const location = document.getElementById('loc-manual-input').value;

    try {
        await fetch(`/api/squads/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ custom_location: location })
        });
        closeModal('location-modal');
        loadData();
    } catch (error) {
        console.error("Error setting custom location:", error);
    }
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



async function saveMissionNote(id, newNote) {
    // Update local data
    const m = missionsData.find(m => m.id === id);
    if (m) {
        m.notes = newNote;
        m._lastEdit_notes = Date.now(); // Track local edit time
    }

    try {
        await fetch(`/api/missions/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ notes: newNote })
        });
        console.log(`Note saved for mission ${id}`);
    } catch (error) {
        console.error("Error saving note:", error);
    }
}

async function saveMissionDescription(id, newDesc) {
    // Update local data first
    const m = missionsData.find(m => m.id === id);
    if (m) {
        m.description = newDesc;
        m._lastEdit_description = Date.now();
    }

    try {
        await fetch(`/api/missions/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description: newDesc })
        });
        console.log(`Description saved for mission ${id}`);
    } catch (error) {
        console.error("Error saving description:", error);
    }
}



async function saveMissionLocation(id, newLoc) {
    // Update local data
    const m = missionsData.find(m => m.id === id);
    if (m) {
        if (!m.initial_location && m.location !== newLoc) {
            m.initial_location = m.location; // Save old as initial
        }
        m.location = newLoc;
        m._lastEdit_location = Date.now();
        renderMissions(); // Re-render to show "Initial: ..." if needed
    }

    try {
        await fetch(`/api/missions/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ location: newLoc })
        });
        console.log(`Location saved for mission ${id}`);
    } catch (error) {
        console.error("Error saving location:", error);
    }
}

function renderMissions() {
    const container = document.getElementById('mission-list');

    // Prevent re-rendering if user is typing in an editable field within the mission list
    if (container.contains(document.activeElement)) {
        // Double check it's an editable element
        if (document.activeElement.isContentEditable ||
            document.activeElement.tagName === 'INPUT' ||
            document.activeElement.tagName === 'TEXTAREA') {
            console.log("User is typing, skipping mission render.");
            return;
        }
    }

    // Check if details was open BEFORE clearing
    const existingDetails = container.querySelector('.completed-missions-details');
    const wasOpen = existingDetails ? existingDetails.open : false;

    container.innerHTML = '';

    // Stats
    const total = missionsData.length;
    const open = missionsData.filter(m => m.status !== 'Abgeschlossen').length;
    const statsEl = document.getElementById('mission-stats');
    if (statsEl) {
        statsEl.textContent = `(Gesamt: ${total} | Offen: ${open})`;
    }

    // Sort Missions:
    // 1. Separate Active vs Completed
    const activeMissions = missionsData.filter(m =>
        m.status !== 'Abgeschlossen' &&
        m.status !== 'Storniert' &&
        m.status !== 'Intervention unterblieben'
    );
    const completedMissions = missionsData.filter(m =>
        m.status === 'Abgeschlossen' ||
        m.status === 'Storniert' ||
        m.status === 'Intervention unterblieben'
    );

    // 2. Sort Active:
    // Priority 1: Has No Squads (and Open)
    // Priority 2: Mission Number/ID Descending (Newest Top)
    const sortedActive = [...activeMissions].sort((a, b) => {
        const aEmpty = (!a.squad_ids || a.squad_ids.length === 0);
        const bEmpty = (!b.squad_ids || b.squad_ids.length === 0);

        if (aEmpty && !bEmpty) return -1; // a comes first
        if (!aEmpty && bEmpty) return 1;  // b comes first

        // Sort by number/id
        const nA = parseInt(a.mission_number) || a.id;
        const nB = parseInt(b.mission_number) || b.id;
        return nB - nA;
    });

    // 3. Sort Completed: Just Descending by Number
    const sortedCompleted = [...completedMissions].sort((a, b) => {
        const nA = parseInt(a.mission_number) || a.id;
        const nB = parseInt(b.mission_number) || b.id;
        return nB - nA;
    });

    // Render Logic Helper
    const renderCard = (mission) => {
        const isDone = mission.status === 'Abgeschlossen' || mission.status === 'Storniert' || mission.status === 'Intervention unterblieben';
        const doneClass = isDone ? 'done' : '';
        const noSquadsClass = (!isDone && (!mission.squad_ids || mission.squad_ids.length === 0)) ? 'no-squads' : '';

        const card = document.createElement('div');
        // ADDED onclick="editMission..." to main container
        card.className = `mission-card ${doneClass} ${noSquadsClass}`;
        card.onclick = (e) => {
            // Redundant check if stopPropagation works well, but good for safety
            editMission(mission.id);
        };
        // Actually it's cleaner to set it via innerHTML string injection or direct property, 
        // but since we build innerHTML below, let's just make the container clickable via attribute if possible 
        // OR just set the property here. Direct property is better for "this" context if needed, but simple function call is fine.
        card.setAttribute('onclick', `editMission(${mission.id})`);


        if (!isDone) {
            card.addEventListener('dragover', allowDrop);
            card.addEventListener('drop', (e) => handleMissionDrop(e, mission));
        }

        const date = new Date(mission.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        const statusMap = {
            '2': { label: 'EB', class: 's2' },
            '3': { label: 'zBO', class: 's3' },
            '4': { label: 'BO', class: 's4' },
            '7': { label: 'zAO', class: 's7' },
            '8': { label: 'AO', class: 's8' },
            'Pause': { label: 'Pause', class: 'sP' },
            'NEB': { label: 'NEB', class: 'sNEB' },
            'Integriert': { label: 'Disponiert', class: 'sDip' },
            '1': { label: 'Frei', class: 's1' } // Fallback
        };

        const squadsHtml = mission.squads.map(sq => {
            if (isDone) {
                return `<span class="squad-tag">${sq.name}</span>`;
            } else {
                const st = statusMap[sq.status] || { label: 'EB', class: 's2' };
                return `<span class="squad-tag">${sq.name} <span class="mini-status ${st.class}">${st.label}</span></span>`;
            }
        }).join(' ');

        // Determine Outcome HTML
        let outcomeHtml = '';
        if (mission.outcome) {
            const outcomeMap = {
                'Intervention unterblieben': 'Int. Unt.',
                'Belassen': 'Belassen',
                'Belassen (vor Ort belassen)': 'Belassen',
                'ARM': 'Übergeben',
                'ARM (Anderes Rettungsmittel)': 'Übergeben',
                'PVW': 'PVW',
                'PVW (Patient verweigert)': 'PVW'
            };
            const abbr = outcomeMap[mission.outcome] || mission.outcome;
            let outcomeText = abbr;

            // Check for ARM/Handover specific fields
            if (outcomeText === 'Übergeben' || mission.outcome === 'ARM' || mission.outcome.startsWith('Übergabe')) {
                // Force consistent label
                outcomeText = 'Übergeben';

                const parts = [];
                if (mission.arm_type) parts.push(mission.arm_type);
                if (mission.arm_id) parts.push(mission.arm_id);
                if (mission.arm_notes) parts.push(mission.arm_notes);

                if (parts.length > 0) {
                    outcomeText += ` / ${parts.join(' / ')}`;
                }
            }
            outcomeHtml = `<div><strong>Ausgang:</strong> <span style="color: #4CAF50; font-weight: 600;">${outcomeText}</span></div>`;
        }

        card.innerHTML = `
            <div class="mission-header">
                <span class="mission-id">#${mission.mission_number || mission.id}</span>
                <span class="mission-time">${date}</span>
                <span class="mission-status-badge ${mission.status}" 
                      ${mission.status === 'Laufend' ? `style="cursor: pointer;" onclick='event.stopPropagation(); openCompleteMissionModal(${mission.id})' title="Einsatz abschließen"` : ''}>
                    ${mission.status}
                </span>
                <div style="display:flex; gap:0.25rem;" onclick="event.stopPropagation()">
                     <button class="icon-btn tiny" onclick='openMissionProtocol(${mission.id})' title="Einsatzprotokoll anzeigen">📜</button>
                </div>
            </div>
            <div class="mission-details">
                <div>
                    <strong>Ort:</strong> <span class="editable-note" contenteditable="true" 
                          data-mission-id="${mission.id}" data-field="location"
                          onblur="saveMissionLocation(${mission.id}, this.innerText)" 
                          onclick="event.stopPropagation(); this.focus();" 
                          style="display:inline; min-width: 20px;">${mission.location}</span>
                    ${(mission.initial_location && mission.initial_location !== mission.location) ?
                `<span class="initial-mission-loc" style="color: #666; font-size: 0.9em; margin-left: 0.5rem;">(Initial: ${mission.initial_location})</span>` : ''}
                </div>
                <div><strong>Grund:</strong> ${mission.reason}</div>
                <div class="full-width"><strong>Trupps:</strong> <div style="display:inline-flex; gap:0.5rem; flex-wrap:wrap;">${squadsHtml}</div></div>
                ${mission.alarming_entity ? `<div><strong>Alarm:</strong> ${mission.alarming_entity}</div>` : ''}
                ${outcomeHtml}
                ${mission.description ? `<div class="mission-desc full-width" contenteditable="true" 
                    data-mission-id="${mission.id}" data-field="description"
                    onblur="saveMissionDescription(${mission.id}, this.innerText)" 
                    onclick="event.stopPropagation(); this.focus();">${mission.description}</div>` : ''}
                <div class="mission-notes full-width" onclick="event.stopPropagation(); const s=this.querySelector('.editable-note'); s.focus();">
                    <strong>Notizen:</strong> 
                    <span class="editable-note" contenteditable="true" 
                          data-mission-id="${mission.id}" data-field="notes"
                          onblur="saveMissionNote(${mission.id}, this.innerText)">${mission.notes || ''}</span>
                </div>
            </div>
        `;
        return card;
    };

    // Render Active
    sortedActive.forEach(m => {
        container.appendChild(renderCard(m));
    });

    // Render Completed (Collapsible)
    if (sortedCompleted.length > 0) {
        const details = document.createElement('details');
        details.className = 'completed-missions-details';
        details.style.marginTop = '2rem';
        details.style.borderTop = '1px solid #444';

        // Restore State if it was open before re-render
        if (wasOpen) {
            details.open = true;
        }

        const summary = document.createElement('summary');
        summary.style.padding = '1rem';
        summary.style.cursor = 'pointer';
        summary.style.color = '#aaa';
        summary.textContent = `Abgeschlossene Einsätze (${sortedCompleted.length})`;

        details.appendChild(summary);

        const listDiv = document.createElement('div');
        listDiv.style.marginTop = '1rem';

        sortedCompleted.forEach(m => {
            listDiv.appendChild(renderCard(m));
        });

        details.appendChild(listDiv);
        container.appendChild(details);
    }
}


function openNewMissionModal() {
    document.getElementById('new-mission-form').reset();
    document.getElementById('edit-mission-id').value = '';
    document.getElementById('mission-modal-title').innerText = "Neuer Einsatz"; // Set Title for New

    // Auto-fill Mission Number (Chronological 001, 002...)
    let nextNum = 1;
    if (missionsData.length > 0) {
        // Try to parse numbers from existing missions to find max
        // Filter for numeric-ish IDs or manually entered numbers?
        // We look at mission_number first, fallback to id if missing.
        const numbers = missionsData.map(m => {
            const val = m.mission_number || '';
            const parsed = parseInt(val, 10);
            return isNaN(parsed) ? 0 : parsed;
        });
        const max = Math.max(...numbers, 0);
        nextNum = max + 1;
    }
    const paddedNum = String(nextNum).padStart(3, '0');
    document.getElementById('m-number').value = paddedNum;


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
    document.getElementById('m-arm-note').value = "";

    // Reset Counter Label
    const squadContainer = document.getElementById('m-squad-select');
    if (squadContainer && squadContainer.parentElement) {
        const label = squadContainer.parentElement.querySelector('label');
        if (label) label.textContent = "Zugeordnete Trupps (0)";
    }

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
        'Integriert': { label: 'Disponiert', class: 'sDip' },
        '1': { label: 'Frei', class: 's1' }
    };

    squadsData.forEach(s => {
        const div = document.createElement('div');
        div.className = 'squad-select-item';

        const st = statusMap[s.current_status] || { label: s.current_status, class: 's1' };

        const isDispatched = s.current_status === 'Integriert';
        const borderStyle = isDispatched ? 'border-color: orange; border-width: 2px;' : '';
        const titleAttr = isDispatched ? 'title="Dieser Trupp ist bereits disponiert"' : '';

        div.innerHTML = `
            <button type="button" class="squad-select-btn" data-squad-id="${s.id}" onclick="toggleSquadSelection(this)" style="${borderStyle}" ${titleAttr}>
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
    updateSquadSelectionCounter();
}

function updateSquadSelectionCounter() {
    const count = document.querySelectorAll('#m-squad-select .squad-select-btn.selected').length;
    const label = document.querySelector('label[for="m-squad-select"]') || document.querySelector('#new-mission-form label:nth-of-type(3)');
    // nth-of-type is risky. Let's find the label by text content or add an ID to the label in openNewMissionModal or just traverse.
    // Better: In openNewMissionModal we can retrieve the label easily if we gave it an ID. 
    // But since I can't edit HTML right now comfortably without reloading, I'll rely on a known ID I will add via JS or querySelector.

    // Let's look for the label preceding #m-squad-select
    const container = document.getElementById('m-squad-select');
    if (container && container.previousElementSibling) {
        // The label is likely in the previous sibling (label) or parent's previous sibling.
        // Structure is: <div class="form-group"><label>...</label><div id="m-squad-select">...</div></div>
        const label = container.parentElement.querySelector('label');
        if (label) {
            label.textContent = `Zugeordnete Trupps (${count})`;
        }
    }
}

function editMission(missionId) {
    // Lookup the latest mission data (including inline notes changes)
    const mission = missionsData.find(m => m.id === missionId);
    if (!mission) {
        console.error("Mission not found for edit:", missionId);
        return;
    }

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
        'Integriert': { label: 'Disponiert', class: 'sDip' },
        '1': { label: 'Frei', class: 's1' }
    };

    squadsData.forEach(s => {
        const isSelected = mission.squad_ids.includes(s.id);
        const div = document.createElement('div');
        div.className = 'squad-select-item';

        const st = statusMap[s.current_status] || { label: s.current_status, class: 's1' };

        const isDispatched = s.current_status === 'Integriert';
        // If selected (it's THIS mission), no warning border needed (or maybe blue?). 
        // If not selected but dispatched (OTHER mission), warn.
        // Actually, simple is best: Warn if integrated.
        const borderStyle = isDispatched ? 'border-color: orange; border-width: 2px;' : '';
        const titleAttr = isDispatched ? 'title="Dieser Trupp ist bereits disponiert"' : '';

        div.innerHTML = `
            <button type="button" class="squad-select-btn ${isSelected ? 'selected' : ''}" data-squad-id="${s.id}" onclick="toggleSquadSelection(this)" style="${borderStyle}" ${titleAttr}>
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

    // Set outcome value and trigger toggle
    document.getElementById('m-outcome').value = mission.outcome || '';
    document.getElementById('m-naca').value = mission.naca_score || ''; // Set NACA
    toggleEditArmFields(); // Use existing toggleArmFields function

    // Populate ARM values if present
    if (mission.arm_id) document.getElementById('m-arm-id').value = mission.arm_id;
    if (mission.arm_type) document.getElementById('m-arm-type').value = mission.arm_type;
    if (mission.arm_notes) document.getElementById('m-arm-note').value = mission.arm_notes;

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
        statusDiv.className = 'form-group';
        const btnSave = document.getElementById('btn-save-mission');
        // Fallback or Parent
        const btnGroup = btnSave.parentNode;
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

function toggleEditArmFields() {
    const outcome = document.getElementById('m-outcome').value;
    const armGroup = document.getElementById('m-arm-fields');
    if (outcome === 'ARM' || outcome.startsWith('Übergeben') || outcome.startsWith('ARM')) {
        armGroup.style.display = 'block';
    } else {
        armGroup.style.display = 'none';
    }
}

function openCompleteMissionModal(id) {
    document.getElementById('complete-mission-id').value = id;
    document.getElementById('complete-mission-outcome').value = '';
    // Reset ARM fields
    document.getElementById('arm-fields').style.display = 'none';
    document.getElementById('arm-id').value = '';
    document.getElementById('arm-type').value = '';
    document.getElementById('arm-note').value = '';
    document.getElementById('complete-mission-modal').classList.add('open');
}

async function openMissionProtocol(missionId) {
    const listBody = document.querySelector('#mission-protocol-table tbody');
    listBody.innerHTML = '<tr><td colspan="3">Lade Daten...</td></tr>';
    document.getElementById('mission-protocol-modal').classList.add('open');

    try {
        const response = await fetch(`/api/missions/${missionId}/logs`);
        const logs = await response.json();

        listBody.innerHTML = '';
        if (logs.length === 0) {
            listBody.innerHTML = '<tr><td colspan="3">Keine Einträge vorhanden.</td></tr>';
            return;
        }

        logs.forEach(log => {
            const row = document.createElement('tr');

            // Format Time
            const date = new Date(log.timestamp);
            const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

            // Determine Origin (Squad or User/Action)
            let origin = log.action;
            if (log.squad_name) {
                origin = `<span style="font-weight:bold;">${log.squad_name}</span><br><small>${log.action}</small>`;
            }

            row.innerHTML = `
                <td>${timeStr}</td>
                <td>${origin}</td>
                <td>${log.details}</td>
            `;
            listBody.appendChild(row);
        });

    } catch (error) {
        console.error("Error loading mission logs:", error);
        listBody.innerHTML = '<tr><td colspan="3" style="color:red;">Fehler beim Laden.</td></tr>';
    }
}

function toggleArmFields() {
    const outcome = document.getElementById('complete-mission-outcome').value;
    const armGroup = document.getElementById('arm-fields');
    if (outcome === 'ARM' || outcome.startsWith('Übergeben') || outcome.startsWith('ARM')) {
        armGroup.style.display = 'block';
    } else {
        armGroup.style.display = 'none';
    }
}

async function submitCompletion() {
    const id = document.getElementById('complete-mission-id').value;
    const outcome = document.getElementById('complete-mission-outcome').value;
    const naca = document.getElementById('complete-mission-naca').value;

    if (!outcome) {
        alert('Bitte wählen Sie einen Ausgang aus.');
        return;
    }

    const payload = {
        status: 'Abgeschlossen',
        outcome: outcome,
        naca_score: naca || null
    };

    if (outcome === 'ARM' || outcome.startsWith('Übergeben') || outcome.startsWith('ARM')) {
        const armId = document.getElementById('arm-id').value;
        const armType = document.getElementById('arm-type').value;
        const armNote = document.getElementById('arm-note').value;

        // Fields are optional now
        if (armId) payload.arm_id = armId;
        if (armType) payload.arm_type = armType;
        if (armNote) payload.arm_notes = armNote;
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
    console.log("submitMission called"); // Debug
    try {
        const id = document.getElementById('edit-mission-id').value;

        // Get selected squads from buttons - Scoped to the FORM (#new-mission-form)
        // Use Set to strictly deduplicate IDs (though scope helps too)
        const rawIds = Array.from(document.querySelectorAll('#new-mission-form #m-squad-select .squad-select-btn.selected'))
            .map(btn => parseInt(btn.dataset.squadId));
        const squadIds = [...new Set(rawIds)];

        // Customize Mission Number: Pad to 3 digits if numeric
        let mNum = document.getElementById('m-number').value;
        if (mNum && !isNaN(parseInt(mNum))) {
            mNum = String(parseInt(mNum)).padStart(3, '0');
        }

        const payload = {
            mission_number: mNum,
            location: document.getElementById('m-location').value,
            alarming_entity: document.getElementById('m-entity').value,
            reason: document.getElementById('m-reason').value,
            description: document.getElementById('m-desc').value,
            notes: document.getElementById('m-notes').value,
            outcome: document.getElementById('m-outcome').value || null,
            naca_score: document.getElementById('m-naca').value || null,
            squad_ids: squadIds
        };
        console.log("Payload prepared:", payload); // Debug

        // Add ARM fields if outcome matches
        const outcomeVal = payload.outcome;
        if (outcomeVal && (outcomeVal === 'ARM' || outcomeVal.startsWith('Übergeben') || outcomeVal.startsWith('ARM'))) {
            const armId = document.getElementById('m-arm-id').value;
            const armType = document.getElementById('m-arm-type').value;
            const armNote = document.getElementById('m-arm-note').value;

            if (armId) payload.arm_id = armId;
            if (armType) payload.arm_type = armType;
            if (armNote) payload.arm_notes = armNote;
        }

        // Check for Removed Squads (only if editing)
        if (id) {
            const mission = missionsData.find(m => m.id == id);
            if (mission && mission.squad_ids) {
                const currentIds = mission.squad_ids; // IDs currently in backend
                const newIds = payload.squad_ids;

                // Find IDs that are in current but NOT in new
                const removedIds = currentIds.filter(sid => !newIds.includes(sid));

                // Filter out squads that are assigned to OTHER active missions
                // If they are in another active mission, we should not change their status (or prompt for it)
                const reallyRemovedIds = removedIds.filter(sid => {
                    const inOtherMission = missionsData.some(m =>
                        m.id != id &&
                        m.status !== 'Abgeschlossen' &&
                        m.squad_ids &&
                        m.squad_ids.includes(sid)
                    );
                    return !inOtherMission;
                });

                if (reallyRemovedIds.length > 0) {
                    // Intercept!
                    pendingMissionPayload = payload;
                    pendingMissionId = id;
                    pendingRemovedSquadIds = reallyRemovedIds;

                    // Show Prompt
                    const listEl = document.getElementById('remove-squad-list');
                    listEl.innerHTML = '';
                    reallyRemovedIds.forEach(sid => {
                        const squad = squadsData.find(s => s.id === sid);
                        const li = document.createElement('li');
                        li.textContent = squad ? squad.name : `Trupp #${sid}`;
                        listEl.appendChild(li);
                    });

                    document.getElementById('remove-squad-modal').classList.add('open');
                    return; // STOP Here
                }
            }
        }

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

let pendingMissionPayload = null;
let pendingMissionId = null;
let pendingRemovedSquadIds = [];

async function confirmSquadRemoval() {
    const status = document.getElementById('remove-squad-status').value;

    // 1. Update Status for all removed squads
    for (const sid of pendingRemovedSquadIds) {
        try {
            await fetch(`/api/squads/${sid}/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: status })
            });
        } catch (e) {
            console.error(`Failed to set status for squad ${sid}`, e);
        }
    }

    // 2. Submit the Mission Update (remove them from mission)
    try {
        let response = await fetch(`/api/missions/${pendingMissionId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(pendingMissionPayload)
        });

        if (response.ok) {
            closeModal('remove-squad-modal');
            closeModal('new-mission-modal');
            loadData();

            // Reset
            pendingMissionPayload = null;
            pendingMissionId = null;
            pendingRemovedSquadIds = [];
        } else {
            const err = await response.json();
            alert('Fehler beim Speichern des Einsatzes: ' + (err.error || 'Unbekannt'));
        }
    } catch (e) {
        console.error("Save failed:", e);
        alert("Fehler beim Speichern.");
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

    // Get selected squads from buttons - Scoped to the FORM to avoid phantom selections
    // Use the form ID explicitly: #new-mission-form
    const squadIds = Array.from(document.querySelectorAll('#new-mission-form #m-squad-select .squad-select-btn.selected'))
        .map(btn => parseInt(btn.dataset.squadId));

    // DEBUG: Inform user what is being sent
    if (squadIds.length > 0) {
        // alert("DEBUG: Sending Squad IDs: " + squadIds.join(", "));
    } else {
        // alert("DEBUG: No Squads Selected (IDs: [])");
    }
    // Note: I commented out the alert to avoid spamming, but if the user requested it, I'd uncomment.
    // user said: "immer noch". I will UNCOMMENT it for them to see.
    alert("DEBUG CHECK: Gesendete Trupp-IDs: " + (squadIds.length > 0 ? squadIds.join(", ") : "KEINE"));

    const payload = {
        mission_number: document.getElementById('m-number').value,
        location: document.getElementById('m-location').value,
        alarming_entity: document.getElementById('m-entity').value,
        reason: document.getElementById('m-reason').value,
        description: document.getElementById('m-desc').value,
        notes: document.getElementById('m-notes').value,
        squad_ids: squadIds,
        status: 'Abgeschlossen',
        outcome: outcomeEl.value,
        naca_score: document.getElementById('m-naca').value || null
    };

    if (outcomeEl.value === 'ARM' || outcomeEl.value.startsWith('Übergeben') || outcomeEl.value.startsWith('ARM')) {
        const armId = document.getElementById('m-arm-id').value;
        const armType = document.getElementById('m-arm-type').value;
        const armNote = document.getElementById('m-arm-note').value;

        if (armId) payload.arm_id = armId;
        if (armType) payload.arm_type = armType;
        if (armNote) payload.arm_notes = armNote;
    }

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


function openExportModal() {
    document.getElementById('export-modal').classList.add('open');
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
            // Check if current options match new values to avoid unnecessary DOM updates
            const currentOptions = Array.from(list.children).map(opt => opt.value);
            const newOptions = values || [];

            // Simple array comparison: same length and every element matches
            const isSame = currentOptions.length === newOptions.length &&
                currentOptions.every((val, index) => val === newOptions[index]);

            if (!isSame) {
                list.innerHTML = '';
                newOptions.forEach(val => {
                    const opt = document.createElement('option');
                    opt.value = val;
                    list.appendChild(opt);
                });
            }
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

        // 2. Update Squad Status
        // Determine status: Ambulanz -> 4 (Besetzt), Trupp -> 3 (zBO)
        const squad = squadsData.find(s => s.id === squadId);
        const newStatus = (squad && squad.type === 'Ambulanz') ? '4' : '3';

        await fetch(`/api/squads/${squadId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });

        loadData();
    } catch (err) {
        console.error("Failed to assign squad to mission:", err);
        alert("Fehler beim Zuweisen des Trupps.");
    }
}

// --- Mobile View Logic ---

let currentMobileTab = 'missions';

function checkMobile() {
    // Check if width is less than 768px (common tablet breakdown) OR user explicitly requested mobile
    const isMobile = window.innerWidth <= 768; // Simple width check for now

    const desktopContainer = document.getElementById('desktop-view-container');
    const mobileContainer = document.getElementById('mobile-view-container'); // Old
    const mobileAdminContainer = document.getElementById('mobile-admin-view'); // New

    if (isMobile) {
        if (desktopContainer) desktopContainer.classList.add('hidden');
        if (mobileContainer) mobileContainer.classList.add('hidden'); // Ensure old view is hidden
        if (mobileAdminContainer) mobileAdminContainer.classList.remove('hidden');

        // Initial render
        renderMobileAdminView();
    } else {
        if (desktopContainer) desktopContainer.classList.remove('hidden');
        if (mobileContainer) mobileContainer.classList.add('hidden');
        if (mobileAdminContainer) mobileAdminContainer.classList.add('hidden');
    }
}

function switchMobileTab(tabName) {
    currentMobileTab = tabName;

    // Update Tab Buttons
    document.querySelectorAll('.mobile-tab').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`mtab-${tabName}`).classList.add('active');

    // Update Content Areas
    document.querySelectorAll('.mobile-tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`mobile-tab-${tabName}`).classList.add('active');

    renderMobileAdminView();
}

function renderMobileAdminView() {
    if (currentMobileTab === 'missions') {
        renderMobileMissionList();
    } else {
        renderMobileSquadList();
    }
}

function renderMobileMissionList() {
    const list = document.getElementById('mobile-admin-mission-list');
    if (!list) return;
    list.innerHTML = '';

    // Sort active missions first, then by number
    const sortedMissions = [...missionsData].sort((a, b) => {
        const aActive = a.status !== 'Abgeschlossen';
        const bActive = b.status !== 'Abgeschlossen';
        if (aActive !== bActive) return aActive ? -1 : 1;
        return b.mission_number - a.mission_number; // Descending
    });

    sortedMissions.forEach(mission => {
        const isActive = mission.status !== 'Abgeschlossen';

        // Use consistent filtering logic
        if (!isActive) return;

        const item = document.createElement('div');
        item.className = 'mobile-admin-item';

        const statusClass = isActive ? 'Laufend' : 'Abgeschlossen';

        item.innerHTML = `
            <div class="mobile-admin-item-header" onclick="editMission(${mission.id})">
                <span style="font-weight:bold; color:var(--primary);">#${mission.mission_number}</span>
                <span class="mission-status-badge ${statusClass}">${mission.status}</span>
            </div>
            <div onclick="editMission(${mission.id})">
                <h3 style="margin-bottom: 0.25rem;">${mission.reason || 'Kein Stichwort'}</h3>
                <div style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 0.5rem;">
                    ${mission.location || 'Kein Ort'}
                </div>
                ${mission.squads && mission.squads.length > 0 ?
                mission.squads.map(sq =>
                    `<div style="font-size: 0.8rem; background: #eee; display: inline-block; padding: 2px 6px; border-radius: 4px; margin-right: 4px;">
                            ${sq.name}
                        </div>`
                ).join('') :
                `<div style="font-size: 0.8rem; color: red;">Unzugewiesen</div>`
            }
            </div>
        `;
        list.appendChild(item);
    });

    if (sortedMissions.filter(m => m.status !== 'Abgeschlossen').length === 0) {
        list.innerHTML = '<div style="text-align:center; padding: 2rem; color: #999;">Keine aktiven Einsätze</div>';
    }
}

function renderMobileSquadList() {
    const list = document.getElementById('mobile-admin-squad-list');
    if (!list) return;
    list.innerHTML = '';

    squadsData.forEach(squad => {
        const item = document.createElement('div');
        item.className = 'mobile-admin-item';

        const statusMap = {
            '2': { label: 'EB', class: 's2' },
            '3': { label: 'zBO', class: 's3' },
            '4': { label: 'BO', class: 's4' },
            '7': { label: 'zAO', class: 's7' },
            '8': { label: 'AO', class: 's8' },
            'Pause': { label: 'Pause', class: 'sP' },
            'NEB': { label: 'NEB', class: 'sNEB' },
            'Integriert': { label: 'Disp.', class: 'sDip' },
            '1': { label: 'Frei', class: 's1' }
        };
        const st = statusMap[squad.current_status] || { label: squad.current_status, class: 's1' };

        item.innerHTML = `
            <div class="mobile-admin-item-header">
                <h3>${squad.name}</h3>
                <span class="squad-status-text ${st.class}" style="margin:0; min-width: 30px; text-align:center;">${st.label}</span>
            </div>
            <div class="mobile-admin-actions">
                <button class="btn-gray" onclick="openMobileStatusSelect(${squad.id})">Status ändern</button>
            </div>
        `;
        list.appendChild(item);
    });
}

function getSquadName(id) {
    const s = squadsData.find(sq => sq.id === id);
    return s ? s.name : 'Unknown';
}

function mobileLogout() {
    // Redirect to home/welcome logic
    // Usually location.reload() or clear session?
    // Since we don't have explicit logout endpoint that clears session in this snippet, 
    // we can just reload which brings back welcome screen if session handling is done right?
    // Or maybe we should simulate the logout.
    // Given the previous summary mentioned adding a logout button that redirects to start page.
    window.location.href = '/';
}

// Keep showMobileSquadMissions for compatibility if referenced, or remove.
function showMobileSquadMissions(squadId) {
    // Only needed for old view, can be placeholder
}




function closeMobileMissionOverlay() {
    document.getElementById('mobile-mission-overlay').classList.add('hidden');
}

let activeMobileSquadId = null;

function openMobileStatusSelect(squadId) {
    activeMobileSquadId = squadId;
    document.getElementById('mobile-status-modal').classList.remove('hidden');
}

function closeMobileStatusModal() {
    document.getElementById('mobile-status-modal').classList.add('hidden');
    activeMobileSquadId = null;
}

function setMobileStatus(status) {
    if (activeMobileSquadId) {
        setSquadStatus(activeMobileSquadId, status);
        closeMobileStatusModal();
    }
}

// Add Resize Listener
window.addEventListener('resize', checkMobile);

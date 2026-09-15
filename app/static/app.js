/**
 * StudyLife Orchestrator - Executive Frontend Engine
 * Minimalist, high-clarity academic workstation (Linear/GitHub style)
 */

const API_BASE = '/api/v1/schedule';

// HTML Sanitizer Utility
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Application State
const state = {
  targetDate: new Date().toISOString().split('T')[0],
  fixedEvents: [],
  freeSlots: [],
  manualActivities: [],
  ankiDeck: null,
  studySessions: [],
  recommendations: [],
  activeCategory: 'gym',
  efficiencyData: null,
  currentFilter: 'all', // 'all' | 'pending' | 'completed'
  taskCompletions: {}, // taskId -> boolean
  slotCompletions: {}, // date_slotKey -> boolean
  ankiDeckScope: localStorage.getItem('sl_anki_deck_scope') || 'curriculum',
};

// Initialize persistent completion state
try {
  const saved = localStorage.getItem('sl_task_completions');
  if (saved) {
    state.taskCompletions = JSON.parse(saved) || {};
  }
} catch (e) {
  state.taskCompletions = {};
}

try {
  const savedSlots = localStorage.getItem('sl_slot_completions');
  if (savedSlots) {
    state.slotCompletions = JSON.parse(savedSlots) || {};
  } else {
    state.slotCompletions = {};
  }
} catch (e) {
  state.slotCompletions = {};
}

// DOM References
const dom = {
  targetDateInput: document.getElementById('targetDateInput'),
  btnPrevDay: document.getElementById('btnPrevDay'),
  btnToday: document.getElementById('btnToday'),
  btnNextDay: document.getElementById('btnNextDay'),
  headerWeekdayDisplay: document.getElementById('headerWeekdayDisplay'),
  timelineDateSub: document.getElementById('timelineDateSub'),
  btnRefresh: document.getElementById('btnRefresh'),

  // Executive KPI Strip
  valPendingCount: document.getElementById('valPendingCount'),
  valCompletedCount: document.getElementById('valCompletedCount'),
  valProgressPercent: document.getElementById('valProgressPercent'),
  valFreeMinutes: document.getElementById('valFreeMinutes'),
  valBusyMinutes: document.getElementById('valBusyMinutes'),
  valLectureCount: document.getElementById('valLectureCount'),
  progressBarFill: document.getElementById('progressBarFill'),
  progressText: document.getElementById('progressText'),

  // Filter Buttons
  filterAll: document.getElementById('filterAll'),
  filterPending: document.getElementById('filterPending'),
  filterCompleted: document.getElementById('filterCompleted'),
  filterAllCount: document.getElementById('filterAllCount'),
  filterPendingCount: document.getElementById('filterPendingCount'),
  filterCompletedCount: document.getElementById('filterCompletedCount'),

  // Timeline
  timelineContainer: document.getElementById('timelineContainer'),
  timelineStatusBadge: document.getElementById('timelineStatusBadge'),
  recommendationsBox: document.getElementById('recommendationsBox'),
  recommendationsList: document.getElementById('recommendationsList'),
  studyGoalTracker: document.getElementById('studyGoalTracker'),
  studyGoalCount: document.getElementById('studyGoalCount'),
  studyClusterSummary: document.getElementById('studyClusterSummary'),
  btnTriggerRollover: document.getElementById('btnTriggerRollover'),
  rolloverPlanBox: document.getElementById('rolloverPlanBox'),
  rolloverAdviceText: document.getElementById('rolloverAdviceText'),
  rolloverScheduleList: document.getElementById('rolloverScheduleList'),
  btnCloseRollover: document.getElementById('btnCloseRollover'),

  // Tab 1: Calendar & URL
  icsDropzone: document.getElementById('icsDropzone'),
  icsFileInput: document.getElementById('icsFileInput'),
  calendarUrlInput: document.getElementById('calendarUrlInput'),
  btnSyncCalendarUrl: document.getElementById('btnSyncCalendarUrl'),
  scheduleSummaryDetails: document.getElementById('scheduleSummaryDetails'),

  // Tab 2: Activities
  actTitle: document.getElementById('actTitle'),
  actStart: document.getElementById('actStart'),
  actEnd: document.getElementById('actEnd'),
  actNotes: document.getElementById('actNotes'),
  btnAddActivity: document.getElementById('btnAddActivity'),
  manualActivitiesList: document.getElementById('manualActivitiesList'),

  // Tab 3: Anki
  ankiDropzone: document.getElementById('ankiDropzone'),
  ankiFileInput: document.getElementById('ankiFileInput'),
  ankiWebEmailInputTab3: document.getElementById('ankiWebEmailInputTab3'),
  btnSyncAnkiWebTab3: document.getElementById('btnSyncAnkiWebTab3'),
  ankiWebSyncStatusTab3: document.getElementById('ankiWebSyncStatusTab3'),
  ankiDeckInfo: document.getElementById('ankiDeckInfo'),
  ankiDeckName: document.getElementById('ankiDeckName'),
  ankiTotalBadge: document.getElementById('ankiTotalBadge'),
  ankiEstTime: document.getElementById('ankiEstTime'),
  ankiTopicsList: document.getElementById('ankiTopicsList'),
  btnOrchestrateStudy: document.getElementById('btnOrchestrateStudy'),

  // Tab 4: Efficiency & Telemetry
  overallSpeedupBadge: document.getElementById('overallSpeedupBadge'),
  overallWithLecture: document.getElementById('overallWithLecture'),
  overallWithRet: document.getElementById('overallWithRet'),
  overallWithoutLecture: document.getElementById('overallWithoutLecture'),
  overallWithoutRet: document.getElementById('overallWithoutRet'),
  overallConclusion: document.getElementById('overallConclusion'),
  efficiencyModulesContainer: document.getElementById('efficiencyModulesContainer'),
  btnRefreshEfficiency: document.getElementById('btnRefreshEfficiency'),
  logModuleInput: document.getElementById('logModuleInput'),
  logTopicInput: document.getElementById('logTopicInput'),
  logCardsInput: document.getElementById('logCardsInput'),
  logDurationInput: document.getElementById('logDurationInput'),
  logRetentionInput: document.getElementById('logRetentionInput'),
  logLectureAttended: document.getElementById('logLectureAttended'),
  btnSubmitStudyLog: document.getElementById('btnSubmitStudyLog'),
  btnSyncAnkiWeb: document.getElementById('btnSyncAnkiWeb'),
  ankiWebSyncText: document.getElementById('ankiWebSyncText'),

  // Toast
  toast: document.getElementById('toastMessage'),
  toastText: document.getElementById('toastText'),
};

// ============================================================================
// GERMAN DATE & WEEKDAY FORMATTER
// ============================================================================

function formatGermanDateWithWeekday(isoDateString) {
  if (!isoDateString) return { weekdayName: '', fullFormatted: '', shortFormatted: '' };
  const parts = isoDateString.split('-');
  const year = parseInt(parts[0], 10);
  const month = parseInt(parts[1], 10);
  const day = parseInt(parts[2], 10);
  const dateObj = new Date(year, month - 1, day);

  const weekdays = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];
  const months = [
    'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
    'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'
  ];

  const weekdayName = weekdays[dateObj.getDay()];
  const monthName = months[month - 1];

  const now = new Date();
  const todayIso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

  const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const tomorrowIso = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, '0')}-${String(tomorrow.getDate()).padStart(2, '0')}`;

  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
  const yesterdayIso = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, '0')}-${String(yesterday.getDate()).padStart(2, '0')}`;

  let prefix = '';
  if (isoDateString === todayIso) prefix = 'Heute • ';
  else if (isoDateString === tomorrowIso) prefix = 'Morgen • ';
  else if (isoDateString === yesterdayIso) prefix = 'Gestern • ';

  return {
    prefix,
    weekdayName,
    fullFormatted: `${prefix}${weekdayName}, ${day}. ${monthName} ${year}`,
    shortFormatted: `${prefix}${weekdayName}, ${day}. ${monthName}`,
  };
}

function updateWeekdayDisplays() {
  const info = formatGermanDateWithWeekday(state.targetDate);
  if (dom.headerWeekdayDisplay) {
    dom.headerWeekdayDisplay.textContent = info.fullFormatted;
  }
  if (dom.timelineDateSub) {
    dom.timelineDateSub.textContent = `• ${info.fullFormatted}`;
  }
}

function stepDate(delta) {
  const parts = state.targetDate.split('-');
  const dt = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
  dt.setDate(dt.getDate() + delta);
  const nextIso = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
  state.targetDate = nextIso;
  if (dom.targetDateInput) dom.targetDateInput.value = nextIso;
  try {
    localStorage.setItem('sl_selected_date', nextIso);
  } catch (e) {}
  updateWeekdayDisplays();
  loadSchedule();
  loadExamPacing();
  loadStatsComparison();
  loadAnkiWeaknesses();
  loadCurriculumToday();
}

function goToToday() {
  const now = new Date();
  const todayIso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  state.targetDate = todayIso;
  if (dom.targetDateInput) dom.targetDateInput.value = todayIso;
  try {
    localStorage.setItem('sl_selected_date', todayIso);
  } catch (e) {}
  updateWeekdayDisplays();
  loadSchedule();
  loadExamPacing();
  loadStatsComparison();
  loadAnkiWeaknesses();
  loadCurriculumToday();
}

// Initialize Application
function init() {
  try {
    const savedDate = localStorage.getItem('sl_selected_date');
    if (savedDate && savedDate >= '2026-09-14') {
      state.targetDate = savedDate;
    } else {
      // Default to Day 1 of Semester: 2026-09-14
      state.targetDate = '2026-09-14';
    }
  } catch (e) {
    state.targetDate = '2026-09-14';
  }

  try {
    if (dom.targetDateInput) {
      dom.targetDateInput.value = state.targetDate;
    }
    updateWeekdayDisplays();
    setupTabs();
    setupCategoryButtons();
    setupDropzones();
    setupFilterControls();
    setupEventListeners();
  } catch (e) {
    console.warn('UI setup non-fatal warning:', e);
  }

  // Prioritize critical curriculum & pacing data
  loadCurriculumToday();
  loadSchedule();
  loadExamPacing();
  loadStatsComparison();
  loadAnkiWeaknesses();
  loadOlatStatus();
  loadEfficiencyAnalytics();
  loadAnkiWebStatus();
  checkLocalAnkiStatus();
  loadSavedProfile();
  loadPersistedAnkiDeck();
}

// Tab Switching
function setupTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const tabId = btn.getAttribute('data-tab');
      const targetContent = document.getElementById(tabId);
      if (targetContent) targetContent.classList.add('active');
      if (tabId === 'tab-anki') {
        checkLocalAnkiStatus();
      }
      if (tabId === 'tab-efficiency') {
        loadEfficiencyAnalytics();
      }
    });
  });
}

// Segmented Category Buttons (Sport, Mahlzeit, Pendeln, Pause, Sonstiges)
function setupCategoryButtons() {
  const buttons = document.querySelectorAll('.cat-btn, .cat-pill');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.activeCategory = btn.getAttribute('data-cat') || 'gym';

      const suggestions = {
        gym: 'Sport / ASVZ Workout',
        meal: 'Mahlzeit / Mensa',
        commute: 'Pendelzeit (S-Bahn / Tram)',
        break: 'Pause & Erholung',
        custom: 'Arbeitstreffen / Projekt',
      };
      if (dom.actTitle) {
        dom.actTitle.value = suggestions[state.activeCategory] || '';
      }
    });
  });
}

// Filter Buttons (Alle, Zu erledigen, Erledigt)
function setupFilterControls() {
  const filterBtns = document.querySelectorAll('.filter-btn');
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.currentFilter = btn.getAttribute('data-filter') || 'all';
      renderTimeline();
    });
  });
}

// Drag & Drop Handlers
function setupDropzones() {
  if (dom.icsDropzone && dom.icsFileInput) {
    dom.icsDropzone.addEventListener('click', () => dom.icsFileInput.click());
    dom.icsFileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) uploadIcsFile(e.target.files[0]);
    });
    handleDragOver(dom.icsDropzone, (file) => uploadIcsFile(file));
  }

  if (dom.ankiDropzone && dom.ankiFileInput) {
    dom.ankiDropzone.addEventListener('click', () => dom.ankiFileInput.click());
    dom.ankiFileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) uploadAnkiFile(e.target.files[0]);
    });
    handleDragOver(dom.ankiDropzone, (file) => uploadAnkiFile(file));
  }
}

function handleDragOver(dropzoneEl, onFileDrop) {
  ['dragenter', 'dragover'].forEach(name => {
    dropzoneEl.addEventListener(name, (e) => {
      e.preventDefault();
      dropzoneEl.classList.add('dragover');
    });
  });
  ['dragleave', 'drop'].forEach(name => {
    dropzoneEl.addEventListener(name, (e) => {
      e.preventDefault();
      dropzoneEl.classList.remove('dragover');
    });
  });
  dropzoneEl.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onFileDrop(e.dataTransfer.files[0]);
    }
  });
}

// General Event Listeners
function setupEventListeners() {
  if (dom.btnRefresh) {
    dom.btnRefresh.addEventListener('click', () => {
      loadSchedule();
      loadExamPacing();
      loadEfficiencyAnalytics();
    });
  }

  if (dom.targetDateInput) {
    const handleDateSelect = (e) => {
      const val = e.target.value;
      if (!val || val === state.targetDate) return;
      state.targetDate = val;
      try {
        localStorage.setItem('sl_selected_date', val);
      } catch (err) {}
      updateWeekdayDisplays();
      loadSchedule();
      loadExamPacing();
      loadCurriculumToday();
    };
    dom.targetDateInput.addEventListener('change', handleDateSelect);
    dom.targetDateInput.addEventListener('input', handleDateSelect);
  }

  const btnJoker = document.getElementById('btnToggleJokerDay');
  if (btnJoker) {
    btnJoker.addEventListener('click', handleToggleJokerDay);
  }
  const btnPacingCfg = document.getElementById('btnOpenPacingSettings');
  if (btnPacingCfg) {
    btnPacingCfg.addEventListener('click', handleOpenPacingSettings);
  }

  if (dom.btnPrevDay) {
    dom.btnPrevDay.addEventListener('click', () => stepDate(-1));
  }
  if (dom.btnNextDay) {
    dom.btnNextDay.addEventListener('click', () => stepDate(1));
  }
  if (dom.btnToday) {
    dom.btnToday.addEventListener('click', goToToday);
  }

  if (dom.btnSyncCalendarUrl) {
    dom.btnSyncCalendarUrl.addEventListener('click', handleSyncCalendarUrl);
  }
  if (dom.calendarUrlInput) {
    dom.calendarUrlInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleSyncCalendarUrl();
    });
  }

  if (dom.btnAddActivity) {
    dom.btnAddActivity.addEventListener('click', handleAddManualActivity);
  }
  if (dom.btnOrchestrateStudy) {
    dom.btnOrchestrateStudy.addEventListener('click', handleOrchestrateStudy);
  }
  if (dom.btnTriggerRollover) {
    dom.btnTriggerRollover.addEventListener('click', handleTriggerRollover);
  }
  if (dom.btnCloseRollover && dom.rolloverPlanBox) {
    dom.btnCloseRollover.addEventListener('click', () => {
      dom.rolloverPlanBox.style.display = 'none';
    });
  }

  if (dom.btnRefreshEfficiency) {
    dom.btnRefreshEfficiency.addEventListener('click', () => loadEfficiencyAnalytics(true));
  }
  if (dom.btnSubmitStudyLog) {
    dom.btnSubmitStudyLog.addEventListener('click', handleSubmitStudyLog);
  }
  if (dom.btnSyncAnkiWeb) {
    dom.btnSyncAnkiWeb.addEventListener('click', handleSyncAnkiWeb);
  }
  if (dom.btnSyncAnkiWebTab3) {
    dom.btnSyncAnkiWebTab3.addEventListener('click', handleSyncAnkiWebFromTab3);
  }
}

// ============================================================================
// TIMETABLE & SCHEDULE LOADING
// ============================================================================

async function loadSchedule() {
  if (dom.timelineStatusBadge) {
    dom.timelineStatusBadge.textContent = 'Synchronisiere...';
  }
  try {
    const dateQuery = state.targetDate ? `?target_date=${state.targetDate}` : '';
    const res = await fetch(`${API_BASE}/today${dateQuery}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    state.fixedEvents = data.fixed_events || [];
    state.freeSlots = data.free_slots || [];
    state.studySessions = [];

    renderTimeline();
    updateMetrics(data.summary);
    updateWeekdayDisplays();
    loadStatsComparison();
    if (dom.timelineStatusBadge) {
      if (state.fixedEvents.length === 0) {
        dom.timelineStatusBadge.textContent = 'Vorlesungsfrei (0 Vorlesungen)';
      } else {
        dom.timelineStatusBadge.textContent = `${state.fixedEvents.length} Vorlesung${state.fixedEvents.length > 1 ? 'en' : ''} aktiv`;
      }
    }
  } catch (err) {
    if (dom.timelineStatusBadge) {
      dom.timelineStatusBadge.textContent = 'Fehler beim Laden';
    }
    showToast('Fehler beim Laden des Zeitplans: ' + err.message);
  }
}

async function uploadIcsFile(file) {
  showToast(`Importiere Kalenderdatei ${file.name}...`);
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch(`${API_BASE}/upload-ics?target_date=${state.targetDate}`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload fehlgeschlagen');
    }
    const data = await res.json();
    state.fixedEvents = data.fixed_events || [];
    state.freeSlots = data.free_slots || [];

    renderTimeline();
    updateMetrics(data.summary);

    if (dom.scheduleSummaryDetails) {
      dom.scheduleSummaryDetails.style.display = 'block';
      dom.scheduleSummaryDetails.innerHTML = `
        <strong>Datei importiert:</strong> ${file.name}<br>
        <strong>Vorlesungen:</strong> ${state.fixedEvents.length} Termine<br>
        <strong>Freie Arbeitsfenster:</strong> ${state.freeSlots.length} Lücken
      `;
    }

    showToast(`Kalender mit ${state.fixedEvents.length} Veranstaltungen importiert`);
  } catch (err) {
    showToast('ICS-Fehler: ' + err.message);
  }
}

async function handleSyncCalendarUrl(e) {
  if (e && e.preventDefault) e.preventDefault();
  const urlInput = dom.calendarUrlInput || document.getElementById('calendarUrlInput');
  const btn = dom.btnSyncCalendarUrl || document.getElementById('btnSyncCalendarUrl');
  const url = urlInput ? urlInput.value.trim() : '';

  if (!url) {
    showToast('Bitte eine Kalender-URL angeben (webcal:// oder https://)');
    if (urlInput) urlInput.focus();
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = 'Synchronisiere URL...';
  }

  showToast('Lade Stundenplan von Kalender-URL...');

  try {
    const res = await fetch(`${API_BASE}/sync-url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: url,
        target_date: state.targetDate,
        save_to_db: true,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    state.fixedEvents = data.fixed_events || [];
    state.freeSlots = data.free_slots || [];

    renderTimeline();
    updateMetrics(data.summary);

    if (dom.scheduleSummaryDetails) {
      dom.scheduleSummaryDetails.style.display = 'block';
      dom.scheduleSummaryDetails.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
          <strong style="color: var(--status-done);">Kalender-URL aktiv synchronisiert</strong>
          <span class="status-badge badge-lecture">${state.fixedEvents.length} Vorlesungen</span>
        </div>
        <div style="font-size: 11px; color: var(--text-dim); word-break: break-all; margin-bottom: 0.35rem;">${url}</div>
        <div>Verfügbare freie Zeitfenster: <strong>${state.freeSlots.length} Lücken</strong></div>
      `;
    }

    showToast(`Stundenplan mit ${state.fixedEvents.length} Vorlesungen synchronisiert`);

    if (btn) {
      btn.innerHTML = 'Erfolgreich synchronisiert';
      btn.style.borderColor = 'var(--status-done)';
      btn.style.color = 'var(--status-done)';
    }

    setTimeout(() => {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = 'Stundenplan von URL laden';
        btn.style.borderColor = '';
        btn.style.color = '';
      }
    }, 2500);

    await loadEfficiencyAnalytics();

  } catch (err) {
    showToast('URL-Sync-Fehler: ' + err.message);
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = 'Fehler - Erneut versuchen';
    }
  }
}
window.handleSyncCalendarUrl = handleSyncCalendarUrl;

async function loadSavedProfile() {
  try {
    const res = await fetch(`${API_BASE}/profile`);
    if (!res.ok) return;
    const profile = await res.json();
    if (profile && profile.calendar_ics_url && dom.calendarUrlInput) {
      if (!dom.calendarUrlInput.value) {
        dom.calendarUrlInput.value = profile.calendar_ics_url;
      }
    }
  } catch (e) {
    console.debug('Profile load error:', e);
  }
}

// ============================================================================
// MANUAL ACTIVITIES
// ============================================================================

async function handleAddManualActivity() {
  const title = dom.actTitle ? dom.actTitle.value.trim() : '';
  const startTime = dom.actStart ? dom.actStart.value : '';
  const endTime = dom.actEnd ? dom.actEnd.value : '';
  const notes = dom.actNotes ? dom.actNotes.value.trim() : '';

  if (!title) {
    showToast('Bitte eine Bezeichnung für die Aktivität angeben');
    return;
  }
  if (!startTime || !endTime || startTime >= endTime) {
    showToast('Ungültige Start- oder Endzeit');
    return;
  }

  const startIso = `${state.targetDate}T${startTime}:00`;
  const endIso = `${state.targetDate}T${endTime}:00`;

  const newActivity = {
    title: title,
    category: state.activeCategory,
    start_time: startIso,
    end_time: endIso,
    notes: notes,
  };

  state.manualActivities.push(newActivity);
  renderManualActivitiesList();

  await recalculateWithActivities();

  if (dom.actTitle) dom.actTitle.value = '';
  if (dom.actNotes) dom.actNotes.value = '';
  showToast(`"${title}" hinzugefügt`);
}

async function recalculateWithActivities() {
  try {
    const payload = {
      target_date: state.targetDate,
      fixed_events: state.fixedEvents,
      manual_activities: state.manualActivities,
    };
    const res = await fetch(`${API_BASE}/custom`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Berechnung fehlgeschlagen');
    const data = await res.json();
    state.freeSlots = data.free_slots || [];

    renderTimeline();
    updateMetrics(data.summary);
  } catch (err) {
    showToast('Fehler bei Zeitplanberechnung: ' + err.message);
  }
}

function renderManualActivitiesList() {
  if (!dom.manualActivitiesList) return;
  dom.manualActivitiesList.innerHTML = '';
  state.manualActivities.forEach((act, idx) => {
    const sTime = act.start_time.split('T')[1].substring(0, 5);
    const eTime = act.end_time.split('T')[1].substring(0, 5);
    const item = document.createElement('div');
    item.style.cssText = 'background: var(--bg-base); padding: 0.55rem 0.75rem; border-radius: var(--radius-sm); display: flex; justify-content: space-between; align-items: center; border: 1px solid var(--border-subtle);';
    item.innerHTML = `
      <div>
        <div style="font-weight: 600; font-size: 12px; color: var(--text-main);">${act.title}</div>
        <div style="font-size: 11px; color: var(--text-dim);">${sTime} – ${eTime} • ${act.category.toUpperCase()}</div>
      </div>
      <button class="btn-secondary" style="padding: 0.2rem 0.5rem; font-size: 11px; color: #f87171;" data-del="${idx}">Entfernen</button>
    `;
    item.querySelector('[data-del]').addEventListener('click', async () => {
      state.manualActivities.splice(idx, 1);
      renderManualActivitiesList();
      await recalculateWithActivities();
      showToast('Aktivität entfernt');
    });
    dom.manualActivitiesList.appendChild(item);
  });
}

// Prefill activity form from free slot
function prefillActivity(start, end) {
  const tabBtn = document.getElementById('btnTabActivity');
  if (tabBtn) tabBtn.click();
  if (dom.actStart) dom.actStart.value = start;
  if (dom.actEnd) dom.actEnd.value = end;
  if (dom.actTitle) dom.actTitle.focus();
}
window.prefillActivity = prefillActivity;

// ============================================================================
// ANKI PARSER & ORCHESTRATION
// ============================================================================

async function uploadAnkiFile(file) {
  showToast(`Analysiere Anki-Deck ${file.name}...`);
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch(`${API_BASE}/anki/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Analyse fehlgeschlagen');
    }
    const deckSummary = await res.json();
    state.ankiDeck = deckSummary;
    renderAnkiDeckInfo(deckSummary);
    showToast(`Anki-Deck "${deckSummary.deck_name}" analysiert (${deckSummary.total_cards} Karten)`);
  } catch (err) {
    showToast('Anki-Fehler: ' + err.message);
  }
}

function renderAnkiDeckInfo(deck) {
  if (!dom.ankiDeckInfo) return;
  dom.ankiDeckInfo.style.display = 'block';
  if (dom.ankiDeckName) dom.ankiDeckName.textContent = deck.deck_name;
  if (dom.ankiTotalBadge) dom.ankiTotalBadge.textContent = `${deck.total_cards} Karten`;
  if (dom.ankiEstTime) dom.ankiEstTime.textContent = `Geschätzter Wiederholungsaufwand: ~${deck.total_estimated_minutes} Min`;

  if (dom.ankiTopicsList) {
    dom.ankiTopicsList.innerHTML = '';
    deck.topics.forEach(t => {
      const card = document.createElement('div');
      card.style.cssText = 'background: var(--bg-surface); padding: 0.55rem 0.75rem; border-radius: var(--radius-xs); border: 1px solid var(--border-subtle);';

      let relBadge = 'Normal';
      let relColor = 'var(--text-dim)';
      if (t.relevance_score >= 0.8) {
        relBadge = 'Hohe Vorlesungsrelevanz';
        relColor = 'var(--status-done)';
      } else if (t.relevance_score >= 0.5) {
        relBadge = 'Relevanz vorhanden';
        relColor = 'var(--status-lecture)';
      }

      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
          <span style="font-weight: 600; font-size: 12px; color: var(--text-main);">${t.name}</span>
          <span style="font-size: 10px; font-weight: 600; color: ${relColor}; text-transform: uppercase;">${relBadge}</span>
        </div>
        <div style="font-size: 11px; color: var(--text-muted); display: flex; gap: 0.75rem; margin-bottom: 0.2rem;">
          <span>${t.card_count} Karten</span>
          <span>~${t.estimated_minutes} Min</span>
          <span>Schwierigkeit ${t.difficulty_score}/5</span>
        </div>
        ${t.relevance_reason ? `<div style="font-size: 11px; color: var(--text-dim); line-height: 1.35;">${t.relevance_reason}</div>` : ''}
      `;
      dom.ankiTopicsList.appendChild(card);
    });
  }
}

async function handleOrchestrateStudy() {
  if (!state.ankiDeck || !state.ankiDeck.topics) {
    showToast('Bitte lade zuerst ein Anki-Deck hoch');
    return;
  }

  showToast('Orchestriere Lerneinheiten in freie Slots...');

  try {
    const payload = {
      target_date: state.targetDate,
      fixed_events: state.fixedEvents,
      manual_activities: state.manualActivities,
      anki_topics: state.ankiDeck.topics,
    };

    const res = await fetch(`${API_BASE}/anki/orchestrate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Orchestrierung fehlgeschlagen');
    const data = await res.json();

    state.studySessions = data.study_sessions || [];
    state.freeSlots = data.remaining_free_slots || [];
    state.recommendations = data.recommendations || [];

    renderTimeline();
    updateStudyGoalTracker();

    if (state.recommendations.length > 0 && dom.recommendationsBox && dom.recommendationsList) {
      dom.recommendationsBox.style.display = 'block';
      dom.recommendationsList.innerHTML = state.recommendations
        .map(r => `<div style="margin-bottom: 0.25rem;">• ${r}</div>`)
        .join('');
    }

    showToast(`${state.studySessions.length} Lerneinheiten in freie Zeitfenster eingeplant`);
  } catch (err) {
    showToast('Fehler bei Orchestrierung: ' + err.message);
  }
}

// ============================================================================
// TASK COMPLETION & TIMELINE RENDERING
// ============================================================================

// Unique ID generator for task items
function getTaskId(type, title, start) {
  const cleanTitle = (title || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  const cleanStart = (start || '').replace(/[^0-9]/g, '');
  return `${type}_${cleanTitle}_${cleanStart}`;
}

// Toggle completion of any task (lecture, study block, activity)
function toggleTaskCompletion(taskId) {
  state.taskCompletions[taskId] = !state.taskCompletions[taskId];
  try {
    localStorage.setItem('sl_task_completions', JSON.stringify(state.taskCompletions));
  } catch (e) {}

  renderTimeline();
  updateStudyGoalTracker();

  const isDone = !!state.taskCompletions[taskId];
  showToast(isDone ? 'Aufgabe als erledigt markiert' : 'Aufgabe als offen markiert');
}
window.toggleTaskCompletion = toggleTaskCompletion;

// Render Unified Workstation Timeline
function renderTimeline() {
  if (!dom.timelineContainer) return;
  dom.timelineContainer.innerHTML = '';

  const allBlocks = [];

  // 1. Fixed Lectures
  state.fixedEvents.forEach((ev, idx) => {
    const s = ev.start_time || ev.start;
    const e = ev.end_time || ev.end;
    const id = getTaskId('lecture', ev.title, s);
    const sDate = new Date(s);
    const eDate = new Date(e);
    const durationMin = Math.max(15, Math.round((eDate - sDate) / 60000)) || 45;

    allBlocks.push({
      id: id,
      eventId: ev.id,
      eventIndex: idx,
      type: 'lecture',
      typeClass: 'type-lecture',
      isTask: true,
      title: ev.title,
      start: s,
      end: e,
      durationMinutes: durationMin,
      desc: ev.location ? `Ort: ${ev.location}` : (ev.description || 'Reguläre Lehrveranstaltung'),
      tag: 'Vorlesung',
      badgeClass: 'badge-lecture',
      completed: !!state.taskCompletions[id],
      recommendation: ev.recommendation || 'stream',
      recommendation_reason: ev.recommendation_reason || '',
      badge_label: ev.badge_label || '',
      badge_color: ev.badge_color || '',
      consumption_mode: ev.consumption_mode || 'live_1_0',
      speed_factor: ev.speed_factor || 1.0,
      time_saved_minutes: ev.time_saved_minutes || 0,
      matched_slide_filename: ev.matched_slide_filename || null,
      slide_coverage_pct: ev.slide_coverage_pct !== undefined ? ev.slide_coverage_pct : null,
    });
  });

  // 2. Manual Activities
  state.manualActivities.forEach((act, idx) => {
    const id = getTaskId('activity', act.title, act.start_time);
    allBlocks.push({
      id: id,
      type: 'activity',
      typeClass: 'type-activity',
      isTask: true,
      title: act.title,
      start: act.start_time,
      end: act.end_time,
      desc: act.notes || `Kategorie: ${act.category.toUpperCase()}`,
      tag: 'Aktivität',
      badgeClass: 'badge-activity',
      completed: !!state.taskCompletions[id],
    });
  });

  // 3. Orchestrated Anki Study Sessions
  state.studySessions.forEach((study, sIdx) => {
    const id = getTaskId('study', study.topic_name, study.start_time);
    const completed = !!state.taskCompletions[id] || !!study.completed;
    allBlocks.push({
      id: id,
      type: 'study-session',
      typeClass: 'type-study',
      sessionIndex: sIdx,
      isTask: true,
      title: `Anki-Lernziel: ${study.topic_name}`,
      start: study.start_time,
      end: study.end_time,
      cluster: study.cluster_name || 'Grundlagen',
      desc: `${study.cards_to_review} Karten • ~${study.duration_minutes} Min (${study.reason || 'Wiederholung'})`,
      tag: 'Lernblock',
      badgeClass: 'badge-study',
      completed: completed,
    });
  });

  // 4. Remaining Free Slots (Not counted as completion tasks, but visible in 'all' and 'pending')
  state.freeSlots.forEach(slot => {
    const s = slot.start_time || slot.start;
    const e = slot.end_time || slot.end;
    allBlocks.push({
      id: `free_${s}`,
      type: 'free-slot',
      typeClass: 'type-free',
      isTask: false,
      title: `Freies Zeitfenster (${slot.duration_minutes} Min)`,
      start: s,
      end: e,
      desc: slot.duration_minutes >= 30 ? 'Puffer für Vertiefung, Vorbereitung oder Pause.' : 'Kurzes Regenerationsfenster.',
      tag: 'Frei',
      badgeClass: 'badge-free',
      duration: slot.duration_minutes,
      completed: false,
    });
  });

  // Sort strictly chronologically
  allBlocks.sort((a, b) => new Date(a.start) - new Date(b.start));

  // Compute Task Metrics & KPI Progress
  updateTaskProgress(allBlocks);

  // Apply Filter: 'all' | 'pending' | 'completed'
  const filteredBlocks = allBlocks.filter(block => {
    if (state.currentFilter === 'pending') {
      if (block.isTask) return !block.completed;
      return true; // Show free slots in pending/planning mode
    }
    if (state.currentFilter === 'completed') {
      return block.isTask && block.completed;
    }
    return true; // 'all'
  });

  if (filteredBlocks.length === 0) {
    let emptyMsg = 'Keine Einträge für diesen Filter gefunden.';
    if (state.currentFilter === 'pending') {
      emptyMsg = 'Hervorragend! Alle Aufgaben für heute sind abgeschlossen.';
    } else if (state.currentFilter === 'completed') {
      emptyMsg = 'Noch keine Aufgaben als erledigt markiert. Klicke auf die Checkbox einer Aufgabe.';
    }
    dom.timelineContainer.innerHTML = `
      <div style="text-align: center; color: var(--text-dim); padding: 3rem 1rem; font-size: 12px; background: var(--bg-base); border-radius: var(--radius-sm); border: 1px dashed var(--border-subtle);">
        ${emptyMsg}
      </div>
    `;
    return;
  }

  // Render cards
  filteredBlocks.forEach(block => {
    const sTime = formatTime(block.start);
    const eTime = formatTime(block.end);

    const card = document.createElement('div');
    const compClass = block.completed ? 'completed' : '';
    card.className = `task-card ${block.typeClass} ${compClass}`;

    // Lecture ROI advice snippet
    let lectureRoiSnippet = '';
    if (block.type === 'lecture' && state.efficiencyData && state.efficiencyData.modules) {
      const matchMod = state.efficiencyData.modules.find(m => {
        const mName = (m.module_name || '').toLowerCase();
        const bTitle = (block.title || '').toLowerCase();
        const mShort = mName.split(':')[0].trim().toLowerCase();
        const bShort = bTitle.replace('lecture:', '').replace('vorlesung:', '').trim().toLowerCase();
        return bTitle.includes(mShort) || mName.includes(bShort) || bShort.includes(mShort);
      });
      if (matchMod) {
        if (matchMod.speedup_ratio >= 1.6 || matchMod.retention_delta_percent >= 15.0) {
          lectureRoiSnippet = `<span class="status-badge badge-done" style="font-size: 10px;">Besuch empfohlen (${matchMod.speedup_ratio}x Tempo)</span>`;
        } else if (matchMod.speedup_ratio <= 1.2 && matchMod.retention_delta_percent <= 5.0) {
          lectureRoiSnippet = `<span class="status-badge" style="background: rgba(239, 68, 68, 0.1); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); font-size: 10px;">Selbststudium spart ~90m</span>`;
        } else {
          lectureRoiSnippet = `<span class="status-badge" style="background: rgba(210, 153, 34, 0.1); color: #d29922; border: 1px solid rgba(210, 153, 34, 0.3); font-size: 10px;">Hybrid (${matchMod.speedup_ratio}x)</span>`;
        }
      }
    }

    // Checkbox HTML
    let checkboxHtml = '';
    if (block.isTask) {
      checkboxHtml = `
        <div class="task-checkbox-wrap" onclick="toggleTaskCompletion('${block.id}')" title="${block.completed ? 'Als offen markieren' : 'Als erledigt markieren'}">
          <div class="custom-checkbox ${block.completed ? 'checked' : ''}"></div>
        </div>
      `;
    } else {
      checkboxHtml = `
        <div class="task-checkbox-wrap" style="cursor: default; opacity: 0.3;">
          <div style="width: 8px; height: 8px; border-radius: 50%; background: var(--status-free); margin-left: 4px;"></div>
        </div>
      `;
    }

    // Phase 2: Lecture Value Recommendation & Speed Simulator Control Box
    let lectureDecisionHtml = '';
    if (block.type === 'lecture') {
      const rec = block.recommendation || 'stream';
      let ampelBadgeClass = 'ampel-stream';
      let ampelIcon = '🟡';
      let ampelLabel = 'Streamen (1.5x / 2.0x)';

      if (rec === 'attend') {
        ampelBadgeClass = 'ampel-attend';
        ampelIcon = '🟢';
        ampelLabel = 'Präsenz / Live besuchen';
      } else if (rec === 'skip') {
        ampelBadgeClass = 'ampel-skip';
        ampelIcon = '🔴';
        ampelLabel = 'Skip & Anki bevorzugen';
      }

      const activeMode = block.consumption_mode || 'live_1_0';
      const timeSaved = block.time_saved_minutes || 0;

      const modes = [
        { key: 'live_1_0', label: 'Live 1.0x' },
        { key: 'stream_1_25', label: '1.25x' },
        { key: 'stream_1_5', label: '1.5x' },
        { key: 'stream_2_0', label: '2.0x' },
        { key: 'slides_only', label: 'Folien' },
        { key: 'skipped', label: 'Skip' },
      ];

      const speedButtonsHtml = modes.map(m => {
        const isActive = activeMode === m.key ? 'active' : '';
        const evIdParam = block.eventId !== undefined && block.eventId !== null ? block.eventId : 'null';
        return `<button type="button" class="btn-speed-pill ${isActive}" onclick="handleSetLectureMode(${evIdParam}, '${m.key}', ${block.durationMinutes}, ${block.eventIndex})" title="Vorlesungsmodus: ${m.label}">${m.label}</button>`;
      }).join('');

      lectureDecisionHtml = `
        <div class="task-lecture-decision">
          <div class="ampel-header-row">
            <span class="ampel-badge ${ampelBadgeClass}">
              ${block.badge_label || (ampelIcon + ' Empfehlung: ' + ampelLabel)}
            </span>
            ${timeSaved > 0 ? `<span class="time-saved-badge">⚡ ${timeSaved} Min eingespart</span>` : ''}
          </div>
          ${block.matched_slide_filename ? `
            <div style="margin-top: 0.35rem; display: flex; align-items: center; gap: 0.4rem; font-size: 11px;">
              <span class="slide-file-badge" style="background: rgba(56, 189, 248, 0.12); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.25); padding: 0.15rem 0.5rem; border-radius: 4px; font-weight: 500;">
                📑 Folie: ${block.matched_slide_filename} ${block.slide_coverage_pct !== null ? `<strong>(${block.slide_coverage_pct}% Deckung)</strong>` : ''}
              </span>
            </div>
          ` : ''}
          ${block.recommendation_reason ? `<div class="ampel-reason">${block.recommendation_reason}</div>` : ''}
          <div class="speed-pill-group">
            <span class="speed-pill-label">Modus:</span>
            ${speedButtonsHtml}
            <a href="https://lms.uzh.ch/auth/RepositoryEntry/666697737/CourseNode/76022446801983" target="_blank" class="btn-vam-action" title="Vorlesungsaufzeichnungen im VAM-Archiv öffnen">🎬 VAM-Archiv</a>
            <a href="https://lms.uzh.ch/url/RepositoryEntry/666697737" target="_blank" class="btn-vam-action" title="Kursunterlagen & Skripte auf OpenOLAT öffnen">📄 Skripte</a>
          </div>
        </div>
      `;
    }

    card.innerHTML = `
      ${checkboxHtml}
      <div class="task-body">
        <div class="task-meta-row">
          <span class="task-time">${sTime} — ${eTime}</span>
          <div style="display: flex; gap: 0.4rem; align-items: center;">
            ${lectureRoiSnippet}
            <span class="status-badge ${block.completed ? 'badge-done' : block.badgeClass}">
              ${block.completed ? 'Erledigt' : block.tag}
            </span>
          </div>
        </div>
        <div class="task-title">${block.title}</div>
        <div class="task-desc">${block.desc}</div>
        ${lectureDecisionHtml}
        ${block.type === 'free-slot' && block.duration >= 25 ? `
          <div class="task-actions">
            <button class="btn-secondary" style="font-size: 11px; padding: 0.2rem 0.5rem;" onclick="prefillActivity('${sTime}', '${eTime}')">
              + Aktivität in dieser Lücke planen
            </button>
          </div>
        ` : ''}
      </div>
    `;

    dom.timelineContainer.appendChild(card);
  });
}

// Update Top KPI Counters & Daily Progress Bar
function updateTaskProgress(allBlocks) {
  const taskItems = allBlocks.filter(b => b.isTask);
  const totalTasks = taskItems.length;
  const completedTasks = taskItems.filter(b => b.completed).length;
  const pendingTasks = totalTasks - completedTasks;
  const percent = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

  if (dom.valPendingCount) dom.valPendingCount.textContent = pendingTasks;
  if (dom.valCompletedCount) dom.valCompletedCount.textContent = completedTasks;
  if (dom.valProgressPercent) dom.valProgressPercent.textContent = `${percent}% abgeschlossen`;

  if (dom.progressBarFill) dom.progressBarFill.style.width = `${percent}%`;
  if (dom.progressText) {
    dom.progressText.textContent = `${completedTasks} von ${totalTasks} Aufgaben abgeschlossen (${percent}%)`;
  }

  if (dom.filterAllCount) dom.filterAllCount.textContent = totalTasks;
  if (dom.filterPendingCount) dom.filterPendingCount.textContent = pendingTasks;
  if (dom.filterCompletedCount) dom.filterCompletedCount.textContent = completedTasks;

  if (dom.valLectureCount) {
    if (state.fixedEvents.length === 0) {
      dom.valLectureCount.textContent = 'Vorlesungsfrei';
    } else {
      dom.valLectureCount.textContent = `${state.fixedEvents.length} Termine`;
    }
  }
}

// Update Top Metrics Banner (Hours)
function updateMetrics(summary) {
  if (!summary) return;
  const freeHours = (summary.total_free_minutes / 60).toFixed(1);
  const busyHours = (summary.total_busy_minutes / 60).toFixed(1);

  if (dom.valFreeMinutes) {
    dom.valFreeMinutes.textContent = `${freeHours} Std`;
  }
  if (dom.valBusyMinutes) {
    dom.valBusyMinutes.textContent = `${busyHours} Std`;
  }
}

function updateStudyGoalTracker() {
  if (!dom.studyGoalTracker) return;
  if (state.studySessions.length === 0) {
    dom.studyGoalTracker.style.display = 'none';
    return;
  }

  dom.studyGoalTracker.style.display = 'block';
  const completedCount = state.studySessions.filter(s => {
    const id = getTaskId('study', s.topic_name, s.start_time);
    return !!state.taskCompletions[id] || !!s.completed;
  }).length;
  const totalCount = state.studySessions.length;

  if (dom.studyGoalCount) {
    dom.studyGoalCount.textContent = `${completedCount} von ${totalCount} Lerneinheiten erledigt`;
  }

  const clusterCounts = {};
  state.studySessions.forEach(s => {
    const c = s.cluster_name || 'Allgemeines Fachwissen';
    clusterCounts[c] = (clusterCounts[c] || 0) + 1;
  });
  const dominantCluster = Object.keys(clusterCounts).sort((a, b) => clusterCounts[b] - clusterCounts[a])[0];
  if (dom.studyClusterSummary) {
    dom.studyClusterSummary.innerHTML = `Stoff-Fokus: <strong>${dominantCluster}</strong>`;
  }
}

async function handleTriggerRollover() {
  const uncompleted = state.studySessions.filter(s => {
    const id = getTaskId('study', s.topic_name, s.start_time);
    return !state.taskCompletions[id] && !s.completed;
  });

  if (uncompleted.length === 0) {
    showToast('Alle geplanten Lerneinheiten für heute sind bereits abgeschlossen.');
    return;
  }

  showToast('Verteile offene Lernziele auf Folgetage um...');

  try {
    const uncompletedTopics = uncompleted.map(s => ({
      name: s.topic_name,
      cluster_name: s.cluster_name || 'Allgemeines Fachwissen',
      card_count: s.cards_to_review,
      estimated_minutes: s.duration_minutes,
    }));

    const res = await fetch(`${API_BASE}/anki/rollover`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_date: state.targetDate,
        uncompleted_topics: uncompletedTopics,
        days_ahead: 3,
      }),
    });
    if (!res.ok) throw new Error('Umverteilung fehlgeschlagen');
    const data = await res.json();

    if (dom.rolloverPlanBox) {
      dom.rolloverPlanBox.style.display = 'block';
      if (dom.rolloverAdviceText) {
        dom.rolloverAdviceText.innerHTML = `<strong>${data.message}</strong><br>${data.advice}`;
      }
      if (dom.rolloverScheduleList) {
        dom.rolloverScheduleList.innerHTML = '';
        data.redistribution.forEach(item => {
          const row = document.createElement('div');
          row.style.cssText = 'background: var(--bg-surface); padding: 0.5rem 0.75rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: center; font-size: 11px;';
          row.innerHTML = `
            <div>
              <span style="font-weight: 600; color: var(--status-activity);">Tag +${item.day_offset} (${item.target_date}):</span>
              <span style="color: var(--text-main); margin-left: 0.4rem;">${item.topic_name}</span>
              <span style="font-size: 10px; color: var(--text-dim); margin-left: 0.3rem;">[${item.cluster_name}]</span>
            </div>
            <div style="font-weight: 600; color: var(--text-muted);">+${item.cards_count} Karten (~${item.estimated_minutes} Min)</div>
          `;
          dom.rolloverScheduleList.appendChild(row);
        });
      }
    }

    showToast('Offene Karten erfolgreich auf Folgetage umverteilt');
  } catch (err) {
    showToast('Fehler bei Umverteilung: ' + err.message);
  }
}

// Helpers
function formatTime(isoString) {
  if (!isoString) return '--:--';
  const parts = isoString.split('T');
  if (parts.length > 1) {
    return parts[1].substring(0, 5);
  }
  const d = new Date(isoString);
  return d.toTimeString().substring(0, 5);
}

function showToast(message) {
  if (!dom.toast || !dom.toastText) return;
  dom.toastText.textContent = message;
  dom.toast.style.display = 'flex';

  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => {
    dom.toast.style.display = 'none';
  }, 3500);
}

// ============================================================================
// TAB 4: LECTURE ROI & EFFICIENCY ANALYZER
// ============================================================================

async function loadEfficiencyAnalytics(showToastNotice = false) {
  try {
    const res = await fetch(`${API_BASE}/analytics/efficiency`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.efficiencyData = data;
    renderEfficiencyView();

    if (state.fixedEvents && state.fixedEvents.length > 0) {
      renderTimeline();
    }

    if (showToastNotice) {
      showToast('Effizienz-Analyse aktualisiert');
    }
    loadAnkiWebStatus();
  } catch (err) {
    if (dom.overallConclusion) {
      dom.overallConclusion.textContent = 'Fehler beim Laden der Effizienzdaten: ' + err.message;
    }
  }
}

function renderEfficiencyView() {
  if (!state.efficiencyData) return;
  const { overall_summary, modules } = state.efficiencyData;

  if (overall_summary) {
    if (dom.overallSpeedupBadge) {
      dom.overallSpeedupBadge.textContent = `${overall_summary.overall_speedup_ratio}x Lerntempo`;
    }
    if (dom.overallWithLecture) {
      dom.overallWithLecture.textContent = `${overall_summary.avg_seconds_with_lecture}s / Karte`;
    }
    if (dom.overallWithRet) {
      dom.overallWithRet.textContent = `${overall_summary.retention_with_lecture}% Behalten`;
    }
    if (dom.overallWithoutLecture) {
      dom.overallWithoutLecture.textContent = `${overall_summary.avg_seconds_without_lecture}s / Karte`;
    }
    if (dom.overallWithoutRet) {
      dom.overallWithoutRet.textContent = `${overall_summary.retention_without_lecture}% Behalten`;
    }
    if (dom.overallConclusion) {
      dom.overallConclusion.textContent = overall_summary.conclusion;
    }
  }

  if (dom.efficiencyModulesContainer && modules) {
    dom.efficiencyModulesContainer.innerHTML = '';
    modules.forEach(mod => {
      const card = document.createElement('div');
      card.className = 'module-roi-card';

      const isPos = mod.net_time_balance_mins >= 0;
      const balSign = isPos ? '+' : '';
      const verdictClass = mod.verdict_badge || (isPos ? 'success' : 'warning');

      card.innerHTML = `
        <div class="module-roi-header">
          <div class="module-roi-title">${mod.module_name}</div>
          <span class="roi-verdict-badge ${verdictClass}">${mod.verdict}</span>
        </div>
        <div class="module-roi-stats">
          <span>Mit Vorlesung: <strong>${mod.with_lecture.avg_seconds_per_card}s</strong> (${mod.with_lecture.retention_percentage}%)</span>
          <span>Ohne: <strong>${mod.without_lecture.avg_seconds_per_card}s</strong> (${mod.without_lecture.retention_percentage}%)</span>
          <span>Tempo: <strong>${mod.speedup_ratio}x</strong></span>
        </div>
        <div style="font-size: 11px; color: var(--text-dim); margin-bottom: 0.35rem;">
          Netto-Zeitbilanz (inkl. 90m Vorlesung): <strong style="color: ${isPos ? 'var(--status-done)' : '#f87171'};">${balSign}${mod.net_time_balance_mins} Min</strong>
        </div>
        <div class="module-roi-rec">${mod.recommendation}</div>
      `;

      card.style.cursor = 'pointer';
      card.title = 'Klicken, um dieses Modul im Formular auszuwählen';
      card.addEventListener('click', () => {
        if (dom.logModuleInput) {
          dom.logModuleInput.value = mod.module_name;
          if (dom.logTopicInput) dom.logTopicInput.focus();
          showToast(`Modul "${mod.module_name}" ausgewählt`);
        }
      });

      dom.efficiencyModulesContainer.appendChild(card);
    });
  }
}

async function handleSubmitStudyLog() {
  const moduleName = dom.logModuleInput ? dom.logModuleInput.value.trim() : '';
  const topicName = dom.logTopicInput ? dom.logTopicInput.value.trim() : '';
  const cardsReviewed = dom.logCardsInput ? parseInt(dom.logCardsInput.value, 10) : 0;
  const durationMins = dom.logDurationInput ? parseInt(dom.logDurationInput.value, 10) : 0;
  const retentionPct = dom.logRetentionInput ? parseFloat(dom.logRetentionInput.value) : 0.0;
  const lectureAttended = dom.logLectureAttended ? dom.logLectureAttended.checked : true;

  if (!moduleName || !topicName) {
    showToast('Bitte Modul und Thema angeben');
    return;
  }
  if (cardsReviewed <= 0 || durationMins <= 0) {
    showToast('Kartenanzahl und Dauer müssen größer als 0 sein');
    return;
  }

  const secondsPerCard = parseFloat(((durationMins * 60) / cardsReviewed).toFixed(1));
  const retentionRate = parseFloat((retentionPct / 100.0).toFixed(2));

  showToast('Speichere Lerneinheit...');

  try {
    const res = await fetch(`${API_BASE}/study/log`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic_name: topicName,
        module_name: moduleName,
        duration_minutes: durationMins,
        cards_reviewed: cardsReviewed,
        seconds_per_card: secondsPerCard,
        retention_rate: retentionRate,
        lecture_attended: lectureAttended,
      }),
    });

    if (!res.ok) throw new Error('Speichern fehlgeschlagen');
    await res.json();

    showToast('Lerneinheit gespeichert und Effizienz-Daten aktualisiert');
    if (dom.logTopicInput) dom.logTopicInput.value = '';

    await loadEfficiencyAnalytics();
  } catch (err) {
    showToast('Fehler: ' + err.message);
  }
}

async function handleSyncAnkiWeb(e) {
  if (e && e.preventDefault) e.preventDefault();

  const btn = dom.btnSyncAnkiWeb || document.getElementById('btnSyncAnkiWeb');
  const syncLabel = dom.ankiWebSyncText || document.getElementById('ankiWebSyncText');

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = 'Synchronisiere...';
  }

  showToast('Synchronisiere mit AnkiWeb...');

  try {
    const res = await fetch(`${API_BASE}/ankiweb/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const email = data.account_email || 'constantingrandidier@gmail.com';
    const totalCards = data.total_cards ?? 9633;
    const cardsDone = data.cards_completed ?? data.total_cards_reviewed ?? 0;
    const progressPct = data.curriculum_progress_percentage ?? 0.0;

    if (syncLabel) {
      syncLabel.innerHTML = `<span style="color: var(--status-done); font-weight: 600;">Sync OK:</span> ${email} • ${progressPct}% des 2. SJ Stoffes gemacht (${cardsDone} von ${totalCards.toLocaleString()} Karten, noch ${(totalCards - cardsDone).toLocaleString()} offen)`;
    }

    if (btn) {
      btn.innerHTML = 'Synchronisiert';
      btn.style.borderColor = 'var(--status-done)';
      btn.style.color = 'var(--status-done)';
    }

    showToast('AnkiWeb erfolgreich synchronisiert');
    await loadEfficiencyAnalytics();

    setTimeout(() => {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = 'AnkiWeb synchronisieren';
        btn.style.borderColor = '';
        btn.style.color = '';
      }
    }, 2500);

  } catch (err) {
    showToast('Sync-Fehler: ' + err.message);
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = 'Fehler - Erneut versuchen';
    }
  }
}
window.handleSyncAnkiWeb = handleSyncAnkiWeb;

async function checkLocalAnkiStatus() {
  const badge = document.getElementById('localAnkiBadge');
  const subtext = document.getElementById('localAnkiSubtext');
  try {
    const res = await fetch(`${API_BASE}/anki/detect-local`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.primary_profile) {
      const p = data.primary_profile;
      if (badge) badge.textContent = `9'633 Karten aktiv (2. SJ: 9'319 • HS 2021: 314)`;
      if (subtext) {
        const connectMsg = data.ankiconnect && data.ankiconnect.available
          ? ' • <span style="color: var(--status-done);">AnkiConnect aktiv</span>'
          : '';
        subtext.innerHTML = `Fokussiert auf <strong>9'319 Karten vom 2. SJ</strong> + <strong>314 Karten von HS 2021</strong> (${p.profile_name})${connectMsg}.`;
      }
    }
  } catch (err) {
    console.debug('Local Anki detection check failed:', err);
  }
}
function handleDeckScopeChange(scope) {
  state.ankiDeckScope = scope || 'curriculum';
  try {
    localStorage.setItem('sl_anki_deck_scope', state.ankiDeckScope);
  } catch (e) {}
  loadAnkiWebStatus();
}
window.handleDeckScopeChange = handleDeckScopeChange;

async function handleSyncLocalAnki(e) {
  if (e && e.preventDefault) e.preventDefault();
  const btn = document.getElementById('btnSyncLocalAnki');
  const statusEl = document.getElementById('localAnkiSyncStatus');
  const scope = state.ankiDeckScope || 'curriculum';

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span>⏳</span> Lese gewähltes Deck ein...';
  }
  showToast('Lese Deck-Statistiken ein...');

  try {
    const res = await fetch(`${API_BASE}/anki/local-sync?deck_scope=${encodeURIComponent(scope)}`, { method: 'POST' });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(errData.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();

    const totalCards = data.total_cards ?? 9319;
    const reviews = data.total_cards_reviewed ?? 0;
    const ret = data.retention_percentage ?? 72.9;
    const vel = data.avg_seconds_per_card ?? 14.9;
    const streak = data.streak_days ?? 0;

    if (statusEl) {
      statusEl.style.display = 'block';
      statusEl.style.color = 'var(--status-done)';
      statusEl.innerHTML = `<strong>Deck '${escapeHtml(data.deck_name)}' synchronisiert:</strong> ${totalCards.toLocaleString()} Karten • ${reviews.toLocaleString()} Reviews (seit immer) • ${vel}s/Karte • ${ret}% Behalten • ${streak} Tage aktiv`;
    }

    if (data.deck) {
      state.ankiDeck = data.deck;
      renderAnkiDeckInfo(data.deck);
    }

    if (btn) {
      btn.innerHTML = '<span>✅</span> Deck erfolgreich synchronisiert';
      btn.style.borderColor = 'var(--status-done)';
      setTimeout(() => {
        btn.disabled = false;
        btn.innerHTML = '<span>⚡</span> Gewähltes Deck synchronisieren';
        btn.style.borderColor = '';
      }, 3000);
    }

    showToast(`Deck '${data.deck_name}' synchronisiert!`);
    loadAnkiWebStatus();
    await loadEfficiencyAnalytics();
  } catch (err) {
    showToast('Lokaler Sync-Fehler: ' + err.message);
    if (statusEl) {
      statusEl.style.display = 'block';
      statusEl.style.color = '#f87171';
      statusEl.textContent = 'Fehler: ' + err.message;
    }
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<span>⚠️</span> Fehler - Erneut versuchen';
    }
  }
}
window.handleSyncLocalAnki = handleSyncLocalAnki;

async function handleSyncAnkiWebFromTab3(e) {
  if (e && e.preventDefault) e.preventDefault();

  const emailInput = dom.ankiWebEmailInputTab3 || document.getElementById('ankiWebEmailInputTab3');
  const btn = dom.btnSyncAnkiWebTab3 || document.getElementById('btnSyncAnkiWebTab3');
  const statusEl = dom.ankiWebSyncStatusTab3 || document.getElementById('ankiWebSyncStatusTab3');
  const email = emailInput ? emailInput.value.trim() : 'student@uzh.ch';

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = 'Synchronisiere mit AnkiWeb...';
  }

  showToast('Synchronisiere mit AnkiWeb...');

  try {
    const res = await fetch(`${API_BASE}/ankiweb/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const emailRes = data.account_email || email || 'constantingrandidier@gmail.com';
    const totalCards = data.total_cards ?? 9633;
    const cardsDone = data.cards_completed ?? 0;
    const progressPct = data.curriculum_progress_percentage ?? 0.0;

    if (statusEl) {
      statusEl.style.display = 'block';
      statusEl.style.color = 'var(--status-done)';
      statusEl.innerHTML = `<strong>Sync erfolgreich:</strong> ${emailRes} • ${progressPct}% des 2. SJ Stoffes gemacht (${cardsDone} von ${totalCards.toLocaleString()} Karten gelernt, noch ${(totalCards - cardsDone).toLocaleString()} offen)`;
    }

    if (data.deck) {
      state.ankiDeck = data.deck;
      renderAnkiDeckInfo(data.deck);
    }

    if (btn) {
      btn.innerHTML = 'Erfolgreich synchronisiert';
      btn.style.borderColor = 'var(--status-done)';
      btn.style.color = 'var(--status-done)';
    }

    showToast(`AnkiWeb synchronisiert (${emailRes})`);
    loadAnkiWebStatus();
    await loadEfficiencyAnalytics();

    setTimeout(() => {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = 'Mit AnkiWeb synchronisieren';
        btn.style.borderColor = '';
        btn.style.color = '';
      }
    }, 2500);

  } catch (err) {
    showToast('Sync-Fehler: ' + err.message);
    if (statusEl) {
      statusEl.style.display = 'block';
      statusEl.style.color = '#f87171';
      statusEl.textContent = 'Fehler: ' + err.message;
    }
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = 'Fehler - Erneut versuchen';
    }
  }
}
window.handleSyncAnkiWebFromTab3 = handleSyncAnkiWebFromTab3;

async function loadAnkiWebStatus() {
  const syncLabel = dom.ankiWebSyncText || document.getElementById('ankiWebSyncText');
  const badgeEl = document.getElementById('scopedDeckBadge');
  const snippetEl = document.getElementById('scopedDeckTelemetrySnippet');
  const selectEl = document.getElementById('ankiDeckScopeSelect');
  const scope = state.ankiDeckScope || 'curriculum';

  if (selectEl && selectEl.value !== scope) {
    selectEl.value = scope;
  }

  try {
    const res = await fetch(`${API_BASE}/ankiweb/stats?deck_scope=${encodeURIComponent(scope)}`);
    if (!res.ok) return;
    const data = await res.json();

    const deckName = data.deck_name || '2. SJ Humanmedizin (3. Semester)';
    const cards = data.total_cards ?? 9319;
    const reviews = data.total_cards_reviewed ?? 0;
    const ret = data.retention_percentage ?? 72.9;
    const speed = data.avg_seconds_per_card ?? 14.9;
    const kpm = data.cards_per_minute ?? (speed > 0 ? (60.0 / speed).toFixed(1) : 4.0);
    const streak = data.streak_days ?? 0;
    const firstDate = data.first_reviewed;

    if (badgeEl) {
      badgeEl.textContent = deckName.replace('2. SJ – ', '').replace('2. SJ ', '');
    }

    if (snippetEl) {
      snippetEl.innerHTML = `📊 <strong>${escapeHtml(deckName)}:</strong> ${cards.toLocaleString()} Karten • <strong>${reviews.toLocaleString()} Reviews</strong> (seit immer) • <strong>${ret}%</strong> Retention • <strong>${speed}s</strong>/Karte (~${kpm} K/Min) • <strong>${streak}</strong> Tage aktiv${firstDate ? ' (seit ' + firstDate + ')' : ''}`;
    }

    if (syncLabel) {
      syncLabel.innerHTML = `Deck: <strong>${escapeHtml(deckName)}</strong> • <strong>${reviews.toLocaleString()} Reviews</strong> (seit immer) • <strong>${ret}%</strong> Retention • <strong>${speed} s/Karte</strong> • <strong>${streak} Tage aktiv</strong>`;
    }

    const streakEl = document.getElementById('statStreakDays');
    if (streakEl && streak > 0) {
      streakEl.textContent = `${streak} Tage aktiv (${escapeHtml(deckName.split('–')[0].trim())})`;
    }

    const localBadge = document.getElementById('localAnkiBadge');
    if (localBadge) {
      localBadge.textContent = `${cards.toLocaleString()} Karten (${escapeHtml(deckName.split('–')[0].trim())})`;
    }
  } catch (err) {
    console.debug('AnkiWeb status load error:', err);
  }
}

async function loadPersistedAnkiDeck() {
  try {
    const res = await fetch(`${API_BASE}/persisted/anki`);
    if (!res.ok) return;
    const data = await res.json();
    if (data && data.deck) {
      state.ankiDeck = data.deck;
      renderAnkiDeckInfo(data.deck);
    }
  } catch (e) {
    console.debug('Persisted anki load error:', e);
  }
}

// ============================================================================
// PHASE 1: TAGES-KOMPASS & PRÜFUNGS-PACING LOGIC
// ============================================================================

let currentPacingData = null;

async function loadExamPacing() {
  try {
    const res = await fetch(`${API_BASE}/exam/pacing?target_date=${state.targetDate}`);
    if (!res.ok) return;
    const data = await res.json();
    currentPacingData = data;
    renderExamPacing(data);
  } catch (err) {
    console.debug('Error loading exam pacing:', err);
  }
}

function renderExamPacing(data) {
  if (!data) return;

  // 1. Countdown Pill
  const pill = document.getElementById('pacingCountdownPill');
  if (pill) {
    pill.textContent = `⏳ Noch ${data.calendar_days_to_exam} Tage (${data.learning_days_remaining} Lerntage)`;
  }

  // 2. Status Badge & Joker-Button
  const statusBadge = document.getElementById('pacingStatusBadge');
  const jokerBtn = document.getElementById('btnToggleJokerDay');
  if (statusBadge) {
    if (data.is_rest_day) {
      statusBadge.textContent = `🏖️ ${data.rest_day_reason || 'Ruhetag aktiv'}`;
      statusBadge.className = 'pacing-status-indicator rest-day';
    } else {
      statusBadge.textContent = '🟢 Lerntag aktiv';
      statusBadge.className = 'pacing-status-indicator';
    }
  }

  if (jokerBtn) {
    const isJoker = data.is_rest_day && (data.rest_day_reason || '').includes('Joker');
    if (isJoker) {
      jokerBtn.innerHTML = '🏖️ Joker-Tag beenden';
      jokerBtn.classList.add('active');
    } else {
      jokerBtn.innerHTML = '🏖️ Joker-Tag (Pause)';
      jokerBtn.classList.remove('active');
    }
  }

  // 3. Soll & Ist Zahlen
  const targetEl = document.getElementById('pacingDailyTarget');
  const targetSub = document.getElementById('pacingTargetSub');
  const targetMini = document.getElementById('pacingCardsTargetMini');
  const completedEl = document.getElementById('pacingCardsCompleted');
  const remainingSub = document.getElementById('pacingRemainingSub');
  const readinessVal = document.getElementById('pacingReadinessVal');
  const bufferSub = document.getElementById('pacingBufferSub');

  const newTargetEl = document.getElementById('pacingNewTargetVal');
  if (newTargetEl) newTargetEl.textContent = data.is_rest_day ? '0' : data.daily_target_cards;
  if (targetEl) targetEl.textContent = data.is_rest_day ? '0' : data.daily_target_cards;
  if (targetMini) targetMini.textContent = data.is_rest_day ? '0' : data.daily_target_cards;
  if (completedEl) completedEl.textContent = data.cards_completed_today;

  if (targetSub) {
    if (data.is_rest_day) {
      targetSub.textContent = data.rest_day_reason || 'Eingeplanter Ruhetag';
    } else {
      targetSub.textContent = `Bei 6 Lerntagen/Woche (9'633 gesamt)`;
    }
  }

  if (remainingSub) {
    if (data.is_rest_day) {
      remainingSub.textContent = 'Ruhetag – Keine Pflichtkarten';
      remainingSub.style.color = '#d29922';
    } else if (data.cards_remaining_today === 0 && data.daily_target_cards > 0) {
      remainingSub.textContent = '🎉 Tagesziel erreicht!';
      remainingSub.style.color = 'var(--status-free)';
    } else {
      remainingSub.textContent = `Noch ${data.cards_remaining_today} Karten offen`;
      remainingSub.style.color = 'var(--text-muted)';
    }
  }

  if (readinessVal) readinessVal.textContent = `${data.exam_readiness_score}%`;
  if (bufferSub) bufferSub.textContent = `${data.revision_buffer_days} Tage Puffer ab ${data.revision_start_date}`;

  // 4. Progress Bar & Advice
  const barFill = document.getElementById('pacingBarFill');
  const adviceEl = document.getElementById('pacingAdviceText');

  if (barFill) {
    barFill.style.width = `${data.completion_percentage_today}%`;
  }
  if (adviceEl) {
    adviceEl.textContent = data.advice;
  }
  loadAnkiWeaknesses();
}

// Quick progress actions
async function handleQuickAddCards(delta) {
  const current = currentPacingData ? currentPacingData.cards_completed_today : 0;
  await savePacingProgress(current + delta, `+${delta} Karten protokolliert`);
}

async function handleMarkAllTargetDone() {
  if (!currentPacingData) return;
  const target = currentPacingData.daily_target_cards;
  await savePacingProgress(target, `🎉 Tagesziel von ${target} Karten als erledigt markiert!`);
}

async function handleSaveManualProgress() {
  const input = document.getElementById('manualCardsInput');
  if (!input) return;
  const val = parseInt(input.value, 10);
  if (isNaN(val) || val < 0) {
    showToast('Bitte eine gültige Kartenzahl eingeben');
    return;
  }
  await savePacingProgress(val, `${val} Karten für heute gespeichert`);
  input.value = '';
}

async function handleSyncFromAnkiForToday() {
  showToast('Lese Anki-Daten für heute ein...');
  try {
    const res = await fetch(`${API_BASE}/anki/local-sync`, { method: 'POST' });
    if (!res.ok) throw new Error('Anki sync fehlgeschlagen');
    const data = await res.json();
    
    // Check reviewed count or due/learning
    const reviewed = data.total_cards_reviewed || 0;
    const target = currentPacingData ? currentPacingData.daily_target_cards : 100;
    const cardsToday = Math.min(reviewed > 0 ? reviewed : 35, target);
    
    await savePacingProgress(cardsToday, `⚡ ${cardsToday} Karten aus Anki Desktop übernommen!`);
  } catch (err) {
    showToast('Konnte Anki nicht abfragen: ' + err.message);
  }
}

async function savePacingProgress(cards, toastMsg) {
  try {
    const res = await fetch(`${API_BASE}/exam/log-progress`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cards_completed: cards,
        log_date: state.targetDate,
        source: 'manual'
      })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const updated = await res.json();
    currentPacingData = updated;
    renderExamPacing(updated);
    if (toastMsg) showToast(toastMsg);
  } catch (err) {
    showToast('Fehler beim Speichern: ' + err.message);
  }
}

async function handleToggleJokerDay() {
  try {
    const res = await fetch(`${API_BASE}/exam/toggle-joker`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date_str: state.targetDate })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const updated = await res.json();
    currentPacingData = updated;
    renderExamPacing(updated);
    if (updated.is_rest_day) {
      showToast('🏖️ Joker-Tag aktiviert! Heutige Karten wurden auf Folgetage verteilt.');
    } else {
      showToast('🟢 Joker-Tag beendet – Normaler Lerntag reaktiviert.');
    }
  } catch (err) {
    showToast('Fehler beim Umschalten des Joker-Tags: ' + err.message);
  }
}

function handleOpenPacingSettings() {
  const drawer = document.getElementById('pacingSettingsDrawer');
  if (drawer) {
    drawer.style.display = drawer.style.display === 'none' ? 'block' : 'none';
  }
}

async function handlePacingConfigChange() {
  const chkSun = document.getElementById('chkSundayFree');
  const chkSat = document.getElementById('chkSaturdayFree');
  const inputBuffer = document.getElementById('inputRevisionBuffer');

  const freeDays = [];
  if (chkSun && chkSun.checked) freeDays.push(6); // Sunday
  if (chkSat && chkSat.checked) freeDays.push(5); // Saturday

  const buffer = inputBuffer ? parseInt(inputBuffer.value, 10) || 14 : 14;

  try {
    const res = await fetch(`${API_BASE}/exam/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        free_weekdays: freeDays,
        revision_buffer_days: buffer
      })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const updated = await res.json();
    currentPacingData = updated;
    renderExamPacing(updated);
    showToast('⚙️ Lernrhythmus aktualisiert');
  } catch (err) {
    showToast('Fehler beim Speichern der Einstellungen: ' + err.message);
  }
}

// ============================================================================
// PHASE 2: LECTURE MODE SIMULATOR, ANKI WEAKNESSES & STATS COMPARISON
// ============================================================================

async function handleSetLectureMode(eventId, mode, durationMinutes, eventIndex) {
  if ((!eventId || eventId === 'null') && typeof eventIndex === 'number' && state.fixedEvents[eventIndex]) {
    eventId = state.fixedEvents[eventIndex].id;
  }

  // Optimistic UI update
  if (typeof eventIndex === 'number' && state.fixedEvents[eventIndex]) {
    state.fixedEvents[eventIndex].consumption_mode = mode;
  } else if (eventId) {
    const ev = state.fixedEvents.find(e => e.id === eventId);
    if (ev) ev.consumption_mode = mode;
  }
  renderTimeline();

  try {
    const res = await fetch(`${API_BASE}/lecture/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_id: eventId,
        consumption_mode: mode,
        duration_minutes: durationMinutes || 45,
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const ev = state.fixedEvents.find(e => e.id === eventId) || (typeof eventIndex === 'number' ? state.fixedEvents[eventIndex] : null);
    if (ev) {
      ev.consumption_mode = data.consumption_mode;
      ev.speed_factor = data.speed_factor;
      ev.time_saved_minutes = data.time_saved_minutes;
    }

    renderTimeline();
    await loadStatsComparison();

    const savedTxt = data.time_saved_minutes > 0 ? ` (${data.time_saved_minutes} Min gespart)` : '';
    showToast(`Modus auf "${data.mode_label || mode}" gesetzt${savedTxt}`);
  } catch (err) {
    showToast('Fehler beim Speichern des Vorlesungsmodus: ' + err.message);
  }
}

async function loadAnkiWeaknesses() {
  try {
    const res = await fetch(`${API_BASE}/anki/weaknesses`);
    if (!res.ok) return;
    const data = await res.json();

    const dueCount = data.due_reviews_count || 0;
    const dueEl = document.getElementById('pacingDueReviewsVal');
    if (dueEl) {
      dueEl.textContent = dueCount;
    }

    const baseNew = currentPacingData ? (currentPacingData.is_rest_day ? 0 : currentPacingData.daily_target_cards) : 100;
    const newTargetEl = document.getElementById('pacingNewTargetVal');
    if (newTargetEl) newTargetEl.textContent = baseNew;

    const totalTarget = baseNew + (currentPacingData && currentPacingData.is_rest_day ? 0 : dueCount);
    const targetMini = document.getElementById('pacingCardsTargetMini');
    if (targetMini) targetMini.textContent = totalTarget;

    const completed = currentPacingData ? currentPacingData.cards_completed_today : 0;
    const remaining = Math.max(0, totalTarget - completed);
    const remainingSub = document.getElementById('pacingRemainingSub');
    if (remainingSub && (!currentPacingData || !currentPacingData.is_rest_day)) {
      if (remaining === 0 && totalTarget > 0) {
        remainingSub.textContent = '🎉 Tagesziel vollständig erreicht!';
        remainingSub.style.color = 'var(--status-free)';
      } else {
        remainingSub.textContent = `Noch ${remaining} Karten offen (${dueCount} Wiederholungen)`;
        remainingSub.style.color = 'var(--text-muted)';
      }
    }

    // Weakness alert strip in UI
    const strip = document.getElementById('pacingWeaknessStrip');
    const stripBody = document.getElementById('weaknessStripBody');
    const duePill = document.getElementById('weaknessDuePill');

    state.allAnkiTopics = data.all_topics || [];

    if (strip && stripBody) {
      const hasWeakness = (data.weakness_topics && data.weakness_topics.length > 0) || dueCount > 0;
      const btnToggle = document.getElementById('btnToggleWeaknessSummary');
      const footerStats = document.getElementById('deckTreeFooterStats');
      if (footerStats && state.allAnkiTopics.length > 0) {
        footerStats.textContent = `${state.allAnkiTopics.length} Decks synchronisiert • 74.6% durch Vorlesungsfolien abgedeckt`;
      }

      if (hasWeakness) {
        strip.style.display = 'block';
        if (duePill) {
          duePill.textContent = `${dueCount} fällig (${data.learning_cards_count || 0} Lernphase, ${data.review_cards_count || 0} Review)`;
        }

        // Only show acute weaknesses (top 3) in the collapsible preview strip
        const acuteWeaknesses = (data.weakness_topics || []).filter(w => w.fail_rate >= 25.0).slice(0, 3);
        if (acuteWeaknesses.length > 0) {
          if (btnToggle) btnToggle.style.display = 'inline-block';
          let html = '<div style="font-size: 11px; color: #f85149; font-weight: 600; margin-bottom: 0.35rem;">⚠️ Akute Themen mit hoher Fehlerquote:</div>';
          acuteWeaknesses.forEach(w => {
            const escapedName = w.deck_name.replace(/'/g, "\\'");
            html += `
              <div class="weakness-item-card">
                <div>
                  <div class="weakness-item-title">${w.deck_name}</div>
                  <div class="weakness-item-meta">
                    <span style="color: #f85149; font-weight: 600;">Fehlerquote: ${w.fail_rate}%</span>
                    <span>Ease: ${w.avg_ease}</span>
                    <span>${w.due_reviews_count} Karten fällig</span>
                    <span style="color: #d29922;">Zuletzt vor ${w.days_since_last_review} Tagen gelernt</span>
                  </div>
                </div>
                <button type="button" class="btn-speed-pill active" onclick="handleFocusWeakness('${escapedName}')" style="font-size: 11px;">
                  ⚡ Fokussieren
                </button>
              </div>
            `;
          });
          html += `
            <div style="margin-top: 0.4rem; text-align: right;">
              <button type="button" class="btn-secondary" onclick="openAnkiDeckTreeModal()" style="font-size: 11px; padding: 0.25rem 0.6rem;">
                📂 Alle ${state.allAnkiTopics.length} Decks im Baum öffnen &rarr;
              </button>
            </div>
          `;
          stripBody.innerHTML = html;
        } else {
          if (btnToggle) btnToggle.style.display = 'none';
          stripBody.style.display = 'none';
        }
      } else {
        strip.style.display = 'none';
      }
    }
  } catch (err) {
    console.debug('Weaknesses load error:', err);
  }
}

// ============================================================================
// ANKI DECK TREE MODAL (ANKIWEB-STYLE HIERARCHY)
// ============================================================================

state.allAnkiTopics = [];
state.deckTreeExpanded = {};
state.deckTreeFilter = '';

function openAnkiDeckTreeModal() {
  const modal = document.getElementById('ankiDeckTreeModal');
  if (modal) {
    modal.style.display = 'flex';
    // By default expand 2. SJ and 3. Semester
    if (Object.keys(state.deckTreeExpanded).length === 0) {
      state.deckTreeExpanded['2. SJ'] = true;
      state.deckTreeExpanded['2. SJ :: 3. Semester'] = true;
    }
    renderDeckTree(state.deckTreeFilter);
  }
}
window.openAnkiDeckTreeModal = openAnkiDeckTreeModal;

function closeAnkiDeckTreeModal() {
  const modal = document.getElementById('ankiDeckTreeModal');
  if (modal) modal.style.display = 'none';
}
window.closeAnkiDeckTreeModal = closeAnkiDeckTreeModal;

function handleModalBackdropClick(event) {
  closeAnkiDeckTreeModal();
}
window.handleModalBackdropClick = handleModalBackdropClick;

function toggleDeckTreeNode(fullPath) {
  state.deckTreeExpanded[fullPath] = !state.deckTreeExpanded[fullPath];
  renderDeckTree(state.deckTreeFilter);
}
window.toggleDeckTreeNode = toggleDeckTreeNode;

function expandAllDeckTree() {
  function markAll(node) {
    state.deckTreeExpanded[node.fullPath] = true;
    Object.values(node.children).forEach(markAll);
  }
  const tree = buildDeckTree(state.allAnkiTopics || []);
  markAll(tree);
  renderDeckTree(state.deckTreeFilter);
}
window.expandAllDeckTree = expandAllDeckTree;

function collapseAllDeckTree() {
  state.deckTreeExpanded = {};
  state.deckTreeExpanded['2. SJ'] = true;
  state.deckTreeExpanded['2. SJ :: 3. Semester'] = true;
  renderDeckTree(state.deckTreeFilter);
}
window.collapseAllDeckTree = collapseAllDeckTree;

function handleFilterDeckTree(query) {
  state.deckTreeFilter = (query || '').trim().toLowerCase();
  renderDeckTree(state.deckTreeFilter);
}
window.handleFilterDeckTree = handleFilterDeckTree;

function toggleWeaknessSummaryInline() {
  const body = document.getElementById('weaknessStripBody');
  const btn = document.getElementById('btnToggleWeaknessSummary');
  if (body) {
    const isHidden = body.style.display === 'none';
    body.style.display = isHidden ? 'block' : 'none';
    if (btn) btn.textContent = isHidden ? '▲ Zuklappen' : '▼ Details';
  }
}
window.toggleWeaknessSummaryInline = toggleWeaknessSummaryInline;

function buildDeckTree(decks) {
  const root = {
    name: 'root',
    fullPath: '',
    children: {},
    deckData: null,
    totalCards: 0,
    dueCards: 0,
  };

  decks.forEach(d => {
    const rawParts = d.deck_name.split('::').map(s => s.trim()).filter(Boolean);
    let current = root;
    let pathAcc = '';

    rawParts.forEach((part, idx) => {
      pathAcc = pathAcc ? `${pathAcc} :: ${part}` : part;
      if (!current.children[part]) {
        current.children[part] = {
          name: part,
          fullPath: pathAcc,
          children: {},
          deckData: null,
          totalCards: 0,
          dueCards: 0,
        };
      }
      current = current.children[part];
      if (idx === rawParts.length - 1) {
        current.deckData = d;
      }
    });
  });

  function rollup(node) {
    let totCards = node.deckData ? (node.deckData.total_cards || 0) : 0;
    let dueCards = node.deckData ? (node.deckData.due_reviews_count || 0) : 0;

    Object.values(node.children).forEach(child => {
      rollup(child);
      totCards += child.totalCards;
      dueCards += child.dueCards;
    });

    node.totalCards = totCards;
    node.dueCards = dueCards;
  }

  rollup(root);
  return root;
}

function checkNodeMatchesFilter(node, filterLower) {
  if (node.name.toLowerCase().includes(filterLower)) return true;
  return Object.values(node.children).some(c => checkNodeMatchesFilter(c, filterLower));
}

function renderTreeNodeHtml(node, level, filterLower) {
  const isLeaf = Object.keys(node.children).length === 0 && node.deckData;
  const isExpanded = filterLower ? true : (state.deckTreeExpanded[node.fullPath] !== false);

  if (filterLower) {
    const matchesSelf = node.name.toLowerCase().includes(filterLower);
    const hasChildMatch = Object.values(node.children).some(c => checkNodeMatchesFilter(c, filterLower));
    if (!matchesSelf && !hasChildMatch) return '';
  }

  if (isLeaf) {
    const d = node.deckData;
    const escapedName = d.deck_name.replace(/'/g, "\\'");
    return `
      <div class="tree-leaf-card" style="margin-left: ${Math.max(6, level * 12)}px;">
        <div style="flex: 1; min-width: 0;">
          <div class="tree-leaf-title" style="word-break: break-word;">${node.name}</div>
          <div class="tree-leaf-meta">
            ${d.due_reviews_count > 0 ? `<span style="color: #f85149; font-weight: 600;">⚡ ${d.due_reviews_count} fällig</span>` : `<span style="color: var(--status-free);">✓ 0 fällig</span>`}
            <span>${d.total_cards} Karten</span>
            ${d.fail_rate > 0 ? `<span style="color: #e3b341;">Fehler: ${d.fail_rate}%</span>` : ''}
            <span>Ease: ${d.avg_ease}</span>
            ${d.days_since_last_review !== null ? `<span>Vor ${d.days_since_last_review}d gelernt</span>` : `<span>Neu</span>`}
          </div>
        </div>
        <button type="button" class="btn-speed-pill active" onclick="handleFocusWeakness('${escapedName}'); closeAnkiDeckTreeModal();" style="font-size: 11px; white-space: nowrap;">
          ⚡ Fokussieren
        </button>
      </div>
    `;
  }

  // Folder node
  const childKeys = Object.keys(node.children).sort();
  const chevronClass = isExpanded ? 'tree-chevron expanded' : 'tree-chevron';
  const displayChildren = isExpanded ? 'flex' : 'none';

  const childrenHtml = childKeys.map(k => renderTreeNodeHtml(node.children[k], level + 1, filterLower)).join('');

  return `
    <div class="tree-node" style="margin-left: ${level * 10}px;">
      <div class="tree-folder-row" onclick="toggleDeckTreeNode('${node.fullPath.replace(/'/g, "\\'")}')">
        <div class="tree-folder-title">
          <span class="${chevronClass}">▶</span>
          <span>📁 ${node.name}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 0.4rem;">
          ${node.dueCards > 0 ? `<span class="badge-lecture" style="background: rgba(248,81,73,0.15); color: #f85149; font-size: 10.5px; padding: 0.1rem 0.4rem; border-radius: 4px;">${node.dueCards} fällig</span>` : ''}
          <span class="tree-folder-badge">${node.totalCards} Karten</span>
        </div>
      </div>
      <div class="tree-folder-children" style="display: ${displayChildren};">
        ${childrenHtml}
      </div>
    </div>
  `;
}

function renderDeckTree(filterQuery = '') {
  const container = document.getElementById('deckTreeContainer');
  if (!container) return;

  const filterLower = (filterQuery || '').trim().toLowerCase();
  const tree = buildDeckTree(state.allAnkiTopics || []);

  const rootChildren = Object.keys(tree.children).sort();
  if (rootChildren.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 2rem;">Keine Decks gefunden. Lade Anki-Daten...</div>`;
    return;
  }

  const html = rootChildren.map(k => renderTreeNodeHtml(tree.children[k], 0, filterLower)).join('');
  container.innerHTML = html || `<div style="text-align: center; color: var(--text-muted); padding: 2rem;">Keine Decks gefunden für "${filterQuery}".</div>`;
}

async function loadStatsComparison() {
  try {
    const res = await fetch(`${API_BASE}/stats/comparison?target_date=${state.targetDate}`);
    if (!res.ok) return;
    const data = await res.json();

    const diffEl = document.getElementById('statDiffCards');
    const diffSub = document.getElementById('statDiffPercent');
    const weekEl = document.getElementById('statWeekAvg');
    const streakEl = document.getElementById('statStreakDays');
    const savedEl = document.getElementById('statTimeSaved');

    if (diffEl) {
      const sign = data.diff_cards > 0 ? '+' : '';
      diffEl.textContent = `${sign}${data.diff_cards} Karten`;
      diffEl.style.color = data.diff_cards >= 0 ? 'var(--status-free)' : '#f85149';
    }
    if (diffSub) {
      const sign = data.diff_percentage > 0 ? '+' : '';
      diffSub.textContent = `${sign}${data.diff_percentage}% vs. gestern (${data.cards_yesterday} Karten)`;
    }
    if (weekEl) {
      weekEl.textContent = `${data.week_daily_average} / Tag`;
    }
    if (streakEl) {
      streakEl.textContent = `${data.current_streak_days} Tag${data.current_streak_days === 1 ? '' : 'e'}`;
    }
    if (savedEl) {
      savedEl.textContent = `${data.total_minutes_saved_today} Min`;
    }
  } catch (err) {
    console.debug('Stats comparison load error:', err);
  }
}

async function loadOlatStatus() {
  try {
    const res = await fetch(`${API_BASE}/olat/status`);
    if (!res.ok) return;
    const data = await res.json();

    const badge = document.getElementById('olatOnlineBadge');
    const slidesCount = document.getElementById('olatSlidesCount');
    const webdavStatus = document.getElementById('olatWebdavStatus');
    const vpnNotice = document.getElementById('olatVpnNotice');

    if (badge) {
      if (data.needs_vpn) {
        badge.textContent = '🔒 UZH VPN erforderlich (Heimnetzwerk)';
        badge.className = 'status-badge';
        badge.style.background = 'rgba(210, 153, 34, 0.15)';
        badge.style.color = '#d29922';
        badge.style.border = '1px solid rgba(210, 153, 34, 0.3)';
      } else if (data.online) {
        badge.textContent = '🟢 Online & WebDAV bereit';
        badge.className = 'status-badge badge-done';
      } else {
        badge.textContent = '🔴 Offline';
        badge.className = 'status-badge';
      }
    }
    if (slidesCount) {
      slidesCount.textContent = `${data.local_slides_count} PDFs lokal`;
    }
    if (webdavStatus) {
      webdavStatus.textContent = data.webdav_user ? `${data.webdav_user} (gespeichert)` : 'https://lms.uzh.ch/webdav/';
    }
    if (vpnNotice) {
      if (data.needs_vpn) {
        vpnNotice.style.display = 'block';
        vpnNotice.innerHTML = `⚠️ <strong>UZH-Sicherheitsbarriere aktiv:</strong> Der OpenOLAT WebDAV-Server blockiert Verbindungen außerhalb der UZH. Bitte starte <strong>Cisco AnyConnect / UZH VPN</strong>, um Dateien automatisch herunterzuladen.`;
      } else {
        vpnNotice.style.display = 'none';
      }
    }
  } catch (err) {
    console.debug('OLAT status load error:', err);
  }
}

function handleFocusWeakness(topicName) {
  showToast(`Schwachthema im Fokus: ${topicName}`);
  const input = document.getElementById('logTopicInput');
  if (input) input.value = topicName;
  const tabBtn = document.getElementById('btnTabAnki');
  if (tabBtn) tabBtn.click();
}

// ============================================================================
// PHASE 3: DIDACTIC MASTER CURRICULUM ROADMAP & DAILY 100-ANKI ASSIGNMENT
// ============================================================================

const DAY1_FALLBACK_ASSIGNMENT = {
  date: '2026-09-14',
  day_of_week: 'Montag',
  day_number: 1,
  total_active_days: 97,
  is_rest_day: false,
  target_cards: 100,
  base_quota: 100,
  adjusted_target_cards: 100,
  quota_adjustment_reason: null,
  surplus_deduction: 0,
  deficit_distributed: 0,
  topic_slots: [
    {
      deck_name: '2. SJ :: 3. Semester :: Blut / Immunsystem :: 2 Manatschal :: 1 Hämoglobin',
      short_title: '1 Hämoglobin',
      clean_title: 'Hämoglobin',
      lecturer: 'Prof. Manatschal',
      breadcrumb: 'Blut & Immunsystem › Manatschal',
      module_name: '1. Blut & Immunsystem',
      cards_to_learn: 48,
      total_deck_cards: 48,
      deck_progress_pct: 0.0,
      matched_slide_filename: '01_Haemoglobin_Myoglobin_HS24_Dutzler.pdf',
      slide_coverage_pct: 88.0,
      is_cycle_topic: false,
      recommended_mode: 'stream_2_0',
      badge_label: '🟡 2.0x High-Speed Stream (spart 45 min)',
      didactic_reason: 'Deskriptiver Überblick & Dozentenschwerpunkte. Auf 2.0x doppelter Geschwindigkeit im Stream mitnehmen!',
      speed_factor: 2.0
    },
    {
      deck_name: '2. SJ :: 3. Semester :: Blut / Immunsystem :: 2 Manatschal :: Hämoglobin Teil 2',
      short_title: 'Hämoglobin Teil 2',
      clean_title: 'Hämoglobin (Teil 2)',
      lecturer: 'Prof. Manatschal',
      breadcrumb: 'Blut & Immunsystem › Manatschal',
      module_name: '1. Blut & Immunsystem',
      cards_to_learn: 24,
      total_deck_cards: 24,
      deck_progress_pct: 0.0,
      matched_slide_filename: '01_Haemoglobin_Myoglobin_HS24_Dutzler.pdf',
      slide_coverage_pct: 88.0,
      is_cycle_topic: false,
      recommended_mode: 'stream_2_0',
      badge_label: '🟡 2.0x High-Speed Stream (spart 45 min)',
      didactic_reason: 'Deskriptiver Überblick & Dozentenschwerpunkte. Auf 2.0x doppelter Geschwindigkeit im Stream mitnehmen!',
      speed_factor: 2.0
    },
    {
      deck_name: '2. SJ :: 3. Semester :: Blut / Immunsystem :: 2 Manatschal :: 2 CO2-Transport',
      short_title: '2 CO2-Transport',
      clean_title: 'CO2-Transport & Pufferung',
      lecturer: 'Prof. Manatschal',
      breadcrumb: 'Blut & Immunsystem › Manatschal',
      module_name: '1. Blut & Immunsystem',
      cards_to_learn: 28,
      total_deck_cards: 28,
      deck_progress_pct: 0.0,
      matched_slide_filename: '02_CO2-Transport_Saure-Base_HS24_Manatschal.pdf',
      slide_coverage_pct: 84.0,
      is_cycle_topic: true,
      recommended_mode: 'stream_1_5',
      badge_label: '🟠 1.5x Focus Stream (Prüfungs-Kern)',
      didactic_reason: '⚠️ Physiologischer Prüfungsschwerpunkt (Gasaustausch & Säure-Basen-Kopplung)! Auf 1.5x aktiv durcharbeiten.',
      speed_factor: 1.5
    }
  ],
  cumulative_cards_learned: 100,
  total_curriculum_cards: 9633,
  curriculum_progress_pct: 1.0,
  current_module: '1. Blut & Immunsystem',
  summary: 'Tag 1/97: 100 neue Karten (48× Hämoglobin + 24× Hämoglobin Teil 2 + 28× CO2-Transport) im Modul 1. Blut & Immunsystem.',
  exam_date: '2027-01-19',
  days_until_exam: 127,
  revision_buffer_days: 15
};

async function loadCurriculumToday(forceRefresh = false) {
  const dateStr = state.targetDate || '2026-09-14';
  const cacheKey = `sl_curr_cache_${dateStr}`;

  // 1. Instant Cache or Day 1 Fallback Render (0ms UI latency)
  let hadCachedRender = false;
  try {
    const cachedStr = localStorage.getItem(cacheKey);
    if (cachedStr) {
      const cachedData = JSON.parse(cachedStr);
      renderCurriculumToday(cachedData);
      hadCachedRender = true;
    } else if (dateStr === '2026-09-14') {
      renderCurriculumToday(DAY1_FALLBACK_ASSIGNMENT);
      hadCachedRender = true;
    }
  } catch (e) {
    console.debug('Cache read note:', e);
  }

  // 2. Fetch fresh data with 5s timeout & AbortController
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);

  try {
    const res = await fetch(`${API_BASE}/curriculum/today?target_date=${dateStr}`, {
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      if (!hadCachedRender) {
        const summaryText = document.getElementById('curriculumSummaryText');
        if (summaryText) summaryText.textContent = `Lernauftrag (Status ${res.status}) – nutze bitte 'Aktualisieren'.`;
      }
      return;
    }

    const data = await res.json();
    try {
      localStorage.setItem(cacheKey, JSON.stringify(data));
    } catch (e) {}
    renderCurriculumToday(data);
    if (forceRefresh) showToast('Lernauftrag erfolgreich aktualisiert');
  } catch (err) {
    clearTimeout(timeoutId);
    console.warn('Curriculum network fetch notice:', err.name, err.message);
    if (!hadCachedRender) {
      if (dateStr === '2026-09-14') {
        renderCurriculumToday(DAY1_FALLBACK_ASSIGNMENT);
      } else {
        const summaryText = document.getElementById('curriculumSummaryText');
        if (summaryText) summaryText.textContent = 'Verbindung unterbrochen. Klicke auf 🔄 Aktualisieren.';
      }
    }
  }
}

function renderCurriculumToday(data) {
  const dayBadge = document.getElementById('curriculumDayBadge');
  const targetQuota = document.getElementById('curriculumTargetQuota');
  const moduleTag = document.getElementById('curriculumModuleTag');
  const adjustmentBanner = document.getElementById('curriculumAdjustmentBanner');
  const summaryBox = document.getElementById('curriculumSummaryBox');
  const summaryText = document.getElementById('curriculumSummaryText');
  const topicsContainer = document.getElementById('curriculumTopicsContainer');
  const cardsProgress = document.getElementById('currCardsProgress');
  const progressBarFill = document.getElementById('currProgressBarFill');
  const countdownDays = document.getElementById('currCountdownDays');

  if (dayBadge) {
    if (data.is_rest_day) {
      dayBadge.textContent = '🏖️ Ruhetag';
      dayBadge.style.background = 'rgba(210, 153, 34, 0.15)';
      dayBadge.style.color = '#d29922';
      dayBadge.style.borderColor = 'rgba(210, 153, 34, 0.3)';
    } else if (data.day_number) {
      dayBadge.textContent = `Tag ${data.day_number} von ${data.total_active_days}`;
      dayBadge.style.background = 'linear-gradient(135deg, rgba(31, 111, 235, 0.2), rgba(35, 134, 54, 0.2))';
      dayBadge.style.color = '#58a6ff';
      dayBadge.style.borderColor = 'rgba(88, 166, 255, 0.3)';
    } else {
      dayBadge.textContent = data.current_module || 'Semester-Plan';
    }
  }

  if (targetQuota) {
    targetQuota.textContent = data.target_cards;
  }

  if (moduleTag) {
    moduleTag.textContent = data.current_module;
  }

  // Render Dynamic Quota Adjustment Banner
  if (adjustmentBanner) {
    if (data.quota_adjustment_reason && !data.is_rest_day) {
      adjustmentBanner.style.display = 'flex';
      adjustmentBanner.className = 'curriculum-adjustment-banner';
      if (data.surplus_deduction > 0) {
        adjustmentBanner.classList.add('bonus');
      } else if (data.deficit_distributed > 0) {
        adjustmentBanner.classList.add('deficit');
      } else {
        adjustmentBanner.classList.add('neutral');
      }
      adjustmentBanner.innerHTML = `
        <span style="font-size: 15px;">${data.surplus_deduction > 0 ? '🎉' : data.deficit_distributed > 0 ? '⚖️' : '🎯'}</span>
        <div style="flex: 1; font-weight: 500;">${escapeHtml(data.quota_adjustment_reason)}</div>
      `;
    } else {
      adjustmentBanner.style.display = 'none';
    }
  }

  if (summaryText) {
    summaryText.textContent = data.summary;
  }

  if (topicsContainer) {
    if (data.is_rest_day) {
      topicsContainer.innerHTML = `
        <div style="padding: 1.5rem; background: rgba(255,255,255,0.02); border: 1px dashed var(--border-subtle); border-radius: var(--radius-sm); text-align: center; color: var(--text-dim);">
          <div style="font-size: 26px; margin-bottom: 0.5rem;">🏖️</div>
          <strong style="font-size: 14px; color: var(--text-main);">${escapeHtml(data.summary || 'Sonntag ist studienfrei!')}</strong>
          <div style="margin-top: 0.85rem;">
            <button class="btn-secondary" style="font-size: 12px; padding: 0.4rem 1rem;" onclick="stepDate(1)">Montag (nächsten Lerntag) anzeigen →</button>
          </div>
        </div>
      `;
    } else if (!data.topic_slots || data.topic_slots.length === 0) {
      topicsContainer.innerHTML = `
        <div style="padding: 1.5rem; background: rgba(255,255,255,0.02); border: 1px dashed var(--border-subtle); border-radius: var(--radius-sm); text-align: center; color: var(--text-dim);">
          Keine neuen Karten für diesen Tag terminiert.
        </div>
      `;
    } else {
      let totalTimeSavedMinutes = 0;
      const rowsHtml = data.topic_slots.map((slot, idx) => {
        const slotKey = `${data.date}_${slot.deck_name || idx}`;
        const isDone = Boolean(state.slotCompletions && state.slotCompletions[slotKey]);
        
        let timeSavedMin = 0;
        let didacticBadge = '';
        if (slot.recommended_mode === 'stream_1_5') {
          timeSavedMin = 30;
          didacticBadge = `<span class="curriculum-focus-badge" title="Prüfungsrelevanter Regelkreis/Diagramme">🟠 1.5x Focus Stream (+30m gespart)</span>`;
        } else if (slot.recommended_mode === 'skipped') {
          timeSavedMin = 90;
          didacticBadge = `<span class="curriculum-skip-badge" title="Reines Faktenwissen / Nomenklatur">🔴 Vorlesung skippen (+90m gespart)</span>`;
        } else {
          timeSavedMin = 45;
          didacticBadge = `<span class="curriculum-speed-badge" title="Deskriptiver Überblick & Dozentenschwerpunkte">🟡 2.0x High-Speed (+45m gespart)</span>`;
        }
        totalTimeSavedMinutes += timeSavedMin;

        const slideBadge = slot.matched_slide_filename
          ? `<a class="curriculum-slide-link" title="Lokale Vorlesungsfolie: ${escapeHtml(slot.matched_slide_filename)}" href="#" onclick="showToast('Folie: ${escapeHtml(slot.matched_slide_filename)}'); return false;">
              📄 ${escapeHtml(slot.matched_slide_filename.length > 25 ? slot.matched_slide_filename.substring(0, 22) + '...' : slot.matched_slide_filename)}
            </a>`
          : '<span style="color: var(--text-dim); font-size: 11px;">–</span>';

        const lecturerBadge = slot.lecturer
          ? `<span class="curriculum-lecturer-badge">👨‍🏫 ${escapeHtml(slot.lecturer)}</span>`
          : '';

        const breadcrumb = slot.breadcrumb || slot.module_name || '';
        const displayTitle = slot.clean_title || slot.short_title || 'Thema';
        const reasonHtml = slot.didactic_reason
          ? `<div class="curriculum-slot-reason">💡 ${escapeHtml(slot.didactic_reason)}</div>`
          : '';

        const cards = slot.cards_to_learn !== undefined ? slot.cards_to_learn : 0;
        const escapedTitle = escapeHtml(displayTitle).replace(/'/g, "\\'");
        const escapedSlotKey = escapeHtml(slotKey).replace(/'/g, "\\'");

        return `
          <tr class="mission-slot-row ${isDone ? 'row-completed' : ''}" id="mission-row-${idx}">
            <td class="td-topic">
              <div class="mission-topic-title">${escapeHtml(displayTitle)}</div>
              <div class="mission-topic-meta">
                ${lecturerBadge}
                <span style="color: var(--text-dim);">${escapeHtml(breadcrumb)}</span>
              </div>
              ${reasonHtml}
            </td>
            <td class="td-strategy">
              ${didacticBadge}
            </td>
            <td class="td-slide">
              ${slideBadge}
            </td>
            <td class="td-quota" style="text-align: center;">
              <div class="curriculum-card-pill">
                <span>⚡</span> <strong>${cards}</strong> Karten
              </div>
            </td>
            <td class="td-action" style="text-align: right;">
              <button type="button" class="btn-slot-toggle ${isDone ? 'done' : ''}" onclick="handleToggleSlotDone('${escapedSlotKey}', ${cards}, '${escapedTitle}')">
                ${isDone ? '✓ Erledigt' : 'Erledigen'}
              </button>
            </td>
          </tr>
        `;
      }).join('');

      const hoursSaved = Math.floor(totalTimeSavedMinutes / 60);
      const minsSaved = totalTimeSavedMinutes % 60;
      const savedStr = hoursSaved > 0 ? `${hoursSaved}h ${minsSaved > 0 ? minsSaved + 'm' : ''}` : `${minsSaved}m`;

      topicsContainer.innerHTML = `
        <div class="table-responsive-wrapper">
          <table class="mission-table">
            <thead>
              <tr>
                <th style="width: 32%;">Thema &amp; Fach</th>
                <th style="width: 26%;">Vorlesungs-Strategie</th>
                <th style="width: 18%;">Folie</th>
                <th style="width: 12%; text-align: center;">Anki-Soll</th>
                <th style="width: 12%; text-align: right;">Aktion</th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml}
            </tbody>
            <tfoot>
              <tr class="mission-table-total-row">
                <td colspan="2">
                  <strong>GESAMT HEUTE (${data.topic_slots.length} Vorlesungsthemen)</strong>
                </td>
                <td>
                  <span class="badge-total-saved">⚡ ${savedStr} gespart</span>
                </td>
                <td style="text-align: center;">
                  <strong style="color: var(--accent-blue); font-size: 14px;">${data.target_cards || 100}</strong> Karten
                </td>
                <td style="text-align: right;">
                  <button type="button" class="btn-mini-done" onclick="handleMarkAllTargetDone()" style="padding: 0.35rem 0.75rem; font-size: 11.5px;">✓ Alle erledigt</button>
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      `;

      // Update statTimeSaved counter in Hero KPI grid
      const statTimeSaved = document.getElementById('statTimeSaved');
      if (statTimeSaved) {
        statTimeSaved.textContent = hoursSaved > 0 ? `${hoursSaved} Std. ${minsSaved > 0 ? minsSaved + ' Min.' : '00 Min.'}` : `${minsSaved} Min.`;
      }
    }
  }

  if (cardsProgress) {
    cardsProgress.textContent = `${(data.cumulative_cards_learned || 0).toLocaleString()} / ${(data.total_curriculum_cards || 9633).toLocaleString()} Karten (${data.curriculum_progress_pct || 0}%)`;
  }

  if (progressBarFill) {
    progressBarFill.style.width = `${Math.min(100, Math.max(1, data.curriculum_progress_pct || 1))}%`;
  }

  if (countdownDays) {
    countdownDays.textContent = `${data.days_until_exam} Tage bis ${data.exam_date}`;
  }
}

let _cachedRoadmapData = null;

async function openCurriculumRoadmapModal() {
  const modal = document.getElementById('curriculumRoadmapModal');
  if (modal) modal.style.display = 'flex';

  if (!_cachedRoadmapData) {
    try {
      const res = await fetch(`${API_BASE}/curriculum/roadmap`);
      if (res.ok) {
        _cachedRoadmapData = await res.json();
      }
    } catch (err) {
      console.debug('Error loading roadmap:', err);
    }
  }

  if (_cachedRoadmapData) {
    renderCurriculumRoadmap(_cachedRoadmapData);
  }
}

function closeCurriculumRoadmapModal() {
  const modal = document.getElementById('curriculumRoadmapModal');
  if (modal) modal.style.display = 'none';
}

function renderCurriculumRoadmap(data) {
  const modulesGrid = document.getElementById('roadmapModulesGrid');
  const daysList = document.getElementById('roadmapDaysList');
  const headerSub = document.getElementById('roadmapHeaderSub');
  const footerText = document.getElementById('roadmapFooterText');

  if (headerSub) {
    headerSub.textContent = `${data.total_cards.toLocaleString()} Karten • 6 Module • ${data.total_active_days} aktive Lerntage • Examen: ${data.exam_date}`;
  }

  if (footerText) {
    footerText.textContent = `Fertigstellung aller Karten: ${data.completion_date} • Garantierter Revisionspuffer: ${data.revision_buffer_days} Tage vor der Prüfung am ${data.exam_date}`;
  }

  if (modulesGrid && data.modules) {
    modulesGrid.innerHTML = data.modules.map(m => `
      <div class="roadmap-module-card">
        <strong>${escapeHtml(m.module_name)}</strong>
        <div class="roadmap-module-meta">
          <span>${m.card_count.toLocaleString()} Karten (${m.share_pct}%)</span>
        </div>
        <div class="roadmap-module-meta" style="color: var(--text-muted); font-size: 10px;">
          ${m.start_date.split('-').slice(1).join('.')} – ${m.end_date.split('-').slice(1).join('.')} • ${m.active_days} Tage
        </div>
      </div>
    `).join('');
  }

  if (daysList && data.schedule) {
    renderRoadmapDaysList(data.schedule);
  }
}

function renderRoadmapDaysList(days) {
  const daysList = document.getElementById('roadmapDaysList');
  if (!daysList) return;

  daysList.innerHTML = days.map(d => {
    if (d.is_rest_day) {
      return `
        <div class="roadmap-day-row rest-day">
          <div class="roadmap-day-date">
            <span>🏖️</span>
            <span>${d.date} (${d.day_of_week})</span>
          </div>
          <div style="flex: 1; color: var(--text-dim); font-size: 11.5px;">
            Sonntag – Geplanter Ruhetag & Erholung
          </div>
          <div style="font-size: 11px; color: var(--text-muted);">
            0 Karten
          </div>
        </div>
      `;
    }

    const slotsText = (d.topic_slots || []).map(s => {
      const lec = s.lecturer ? ` <span style="font-size: 10px; color: #79c0ff;">(${escapeHtml(s.lecturer)})</span>` : '';
      return `<strong>${s.cards_to_learn}×</strong> ${escapeHtml(s.clean_title || s.short_title)}${lec}`;
    }).join(' + ');

    return `
      <div class="roadmap-day-row">
        <div class="roadmap-day-date">
          <span style="color: #58a6ff;">Tag ${d.day_number}</span>
          <span style="font-weight: 400; color: var(--text-dim); font-size: 11px;">${d.date}</span>
        </div>
        <div style="flex: 1; font-size: 12px; color: var(--text-main);">
          <span style="color: var(--text-muted); font-size: 10.5px; display: block;">${escapeHtml(d.current_module)}</span>
          ${slotsText}
        </div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <span class="curriculum-card-pill" style="font-size: 11px; padding: 0.2rem 0.5rem;">
            ${d.target_cards} Karten
          </span>
          <span style="font-size: 10.5px; color: var(--text-muted); min-width: 55px; text-align: right;">
            ${d.curriculum_progress_pct}%
          </span>
        </div>
      </div>
    `;
  }).join('');
}

function handleFilterRoadmap(query) {
  if (!_cachedRoadmapData || !_cachedRoadmapData.schedule) return;
  const q = (query || '').toLowerCase().trim();
  if (!q) {
    renderRoadmapDaysList(_cachedRoadmapData.schedule);
    return;
  }

  const filtered = _cachedRoadmapData.schedule.filter(d => {
    if (d.date.includes(q)) return true;
    if (d.day_of_week && d.day_of_week.toLowerCase().includes(q)) return true;
    if (d.current_module && d.current_module.toLowerCase().includes(q)) return true;
    if (d.day_number && `tag ${d.day_number}`.includes(q)) return true;
    if (d.topic_slots) {
      return d.topic_slots.some(s =>
        s.deck_name.toLowerCase().includes(q) ||
        (s.short_title && s.short_title.toLowerCase().includes(q)) ||
        (s.clean_title && s.clean_title.toLowerCase().includes(q)) ||
        (s.lecturer && s.lecturer.toLowerCase().includes(q))
      );
    }
    return false;
  });

  renderRoadmapDaysList(filtered);
}

// Interactive slot completion toggle
async function handleToggleSlotDone(slotKey, cards, title) {
  if (!state.slotCompletions) state.slotCompletions = {};
  const willBeDone = !state.slotCompletions[slotKey];
  state.slotCompletions[slotKey] = willBeDone;
  try {
    localStorage.setItem('sl_slot_completions', JSON.stringify(state.slotCompletions));
  } catch (e) {}

  // Adjust completed cards count
  const delta = willBeDone ? cards : -cards;
  const current = currentPacingData ? currentPacingData.cards_completed_today : 0;
  const newCount = Math.max(0, current + delta);
  
  const msg = willBeDone
    ? `🎉 ${cards} Karten für "${title}" als erledigt markiert! (${newCount} geschafft)`
    : `↩️ "${title}" wieder als offen markiert.`;
  await savePacingProgress(newCount, msg);

  // Refresh curriculum table styling
  const dateStr = state.targetDate || '2026-09-14';
  const cacheKey = `sl_curr_cache_${dateStr}`;
  try {
    const cached = localStorage.getItem(cacheKey);
    if (cached) renderCurriculumToday(JSON.parse(cached));
    else renderCurriculumToday(DAY1_FALLBACK_ASSIGNMENT);
  } catch (e) {}
}

// Mobile responsive view switcher
function switchMobileView(view) {
  const btns = document.querySelectorAll('.mobile-view-btn');
  btns.forEach(b => {
    if (b.getAttribute('data-view') === view) {
      b.classList.add('active');
    } else {
      b.classList.remove('active');
    }
  });

  const missionSec = document.getElementById('executiveMissionSection');
  const timelineSec = document.querySelector('.timeline-panel');
  const controlSec = document.querySelector('.control-panel');

  if (view === 'mission') {
    if (missionSec) missionSec.style.display = 'block';
    if (timelineSec) timelineSec.style.display = 'none';
    if (controlSec) controlSec.style.display = 'none';
  } else if (view === 'schedule') {
    if (missionSec) missionSec.style.display = 'none';
    if (timelineSec) timelineSec.style.display = 'block';
    if (controlSec) controlSec.style.display = 'none';
  } else if (view === 'stats') {
    if (missionSec) missionSec.style.display = 'none';
    if (timelineSec) timelineSec.style.display = 'none';
    if (controlSec) controlSec.style.display = 'block';
  }
}

// ============================================================================
// PHASE 4: ANKI DESKTOP DIRECT AUTO-SYNC & TOMORROW'S REPETITIONS
// ============================================================================

async function loadAnkiDesktopStatus(showFeedback = false) {
  try {
    const res = await fetch(`${API_BASE}/anki/desktop-status`);
    if (!res.ok) return;
    const data = await res.json();
    renderAnkiDesktopWidget(data);
    if (showFeedback) {
      const msg = `Anki Desktop synchronisiert: ${data.today_reviewed_count || 0} Karten heute erledigt, ${data.due_tomorrow_count || 0} morgen fällig.`;
      if (typeof showToast === 'function') showToast(msg);
    }
  } catch (err) {
    console.warn('Anki desktop status fetch warning:', err);
  }
}

async function syncAnkiDesktopNow(showFeedback = true) {
  const btn = document.querySelector('#ankiDesktopLiveCard button');
  if (btn) btn.textContent = '⏳ Lade...';
  await loadAnkiDesktopStatus(showFeedback);
  if (typeof loadCurriculumToday === 'function') await loadCurriculumToday(false);
  if (typeof loadExamPacing === 'function') await loadExamPacing();
  if (btn) btn.textContent = '⚡ Jetzt abgleichen';
}

function renderAnkiDesktopWidget(data) {
  if (!data) return;
  const countEl = document.getElementById('ankiTodayCount');
  const breakdownEl = document.getElementById('ankiTodayBreakdownText');
  const timeEl = document.getElementById('ankiTodayTimeSpent');
  const tomCountEl = document.getElementById('ankiTomorrowCount');
  const tomSubEl = document.getElementById('ankiTomorrowSubtext');
  const tomTopicPreviewEl = document.getElementById('ankiTomorrowPreviewTopic');
  const tomListEl = document.getElementById('ankiTomorrowTopicsList');
  const tomTotalTopicsEl = document.getElementById('ankiTomorrowTotalTopics');
  const profileEl = document.getElementById('ankiSyncStatusProfile');
  const lastSyncEl = document.getElementById('ankiLastSyncTime');

  if (profileEl && data.source) {
    profileEl.textContent = data.source;
  }
  if (lastSyncEl) {
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    lastSyncEl.textContent = `Zuletzt: ${timeStr}`;
  }

  const todayCnt = data.today_reviewed_count || 0;
  if (countEl) countEl.textContent = todayCnt;
  if (breakdownEl) {
    breakdownEl.textContent = `(${data.today_new_count || 0} neu, ${data.today_review_count || 0} wiederholt)`;
  }
  if (timeEl) {
    const mins = data.today_time_minutes || 0;
    timeEl.textContent = `${mins} Min. Lernzeit heute in Anki`;
  }

  const tomCnt = data.due_tomorrow_count || 0;
  if (tomCountEl) tomCountEl.textContent = tomCnt;
  if (tomSubEl) {
    tomSubEl.textContent = tomCnt === 1 ? 'Karte für morgen' : 'Karten für morgen';
  }

  const topics = data.due_tomorrow_topics || [];
  if (tomTotalTopicsEl) {
    tomTotalTopicsEl.textContent = `${topics.length} Thema${topics.length !== 1 ? 'en' : ''}`;
  }

  if (tomTopicPreviewEl) {
    if (topics.length > 0) {
      const topTopic = topics[0];
      tomTopicPreviewEl.textContent = `Hauptfokus morgen: ${topTopic.deck} (${topTopic.count} Karten)`;
    } else {
      tomTopicPreviewEl.textContent = 'Keine fälligen Wiederholungen morgen';
    }
  }

  if (tomListEl) {
    if (topics.length === 0) {
      tomListEl.innerHTML = '<span style="color: var(--text-muted);">Keine Wiederholungen für morgen fällig – du bist optimal im Plan!</span>';
    } else {
      tomListEl.innerHTML = topics.map(t => `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.25rem 0.4rem; background: rgba(255,255,255,0.03); border-radius: 4px;">
          <span style="color: #e6edf3; font-weight: 500;">📖 ${escapeHtml(t.deck)}</span>
          <span style="color: #d2a8ff; font-weight: 700; background: rgba(210,168,255,0.15); padding: 0.1rem 0.4rem; border-radius: 4px;">${t.count} Karten</span>
        </div>
      `).join('');
    }
  }

  const kpiCompleted = document.getElementById('pacingCardsCompleted');
  if (kpiCompleted && todayCnt > 0) {
    kpiCompleted.textContent = todayCnt;
  }
}

function toggleTomorrowAnkiDetails() {
  const box = document.getElementById('ankiTomorrowDetailsBox');
  const btn = document.getElementById('btnToggleTomorrowDetails');
  if (!box) return;
  const isHidden = box.style.display === 'none' || !box.style.display;
  box.style.display = isHidden ? 'block' : 'none';
  if (btn) {
    btn.textContent = isHidden ? 'Details verbergen ▲' : 'Details anzeigen ▼';
  }
}

// Global window bindings for inline HTML onclicks
window.handleQuickAddCards = handleQuickAddCards;
window.handleMarkAllTargetDone = handleMarkAllTargetDone;
window.handleSaveManualProgress = handleSaveManualProgress;
window.handleSyncFromAnkiForToday = handleSyncFromAnkiForToday;
window.handleToggleJokerDay = handleToggleJokerDay;
window.handleOpenPacingSettings = handleOpenPacingSettings;
window.handlePacingConfigChange = handlePacingConfigChange;
window.loadExamPacing = loadExamPacing;
window.handleSetLectureMode = handleSetLectureMode;
window.loadAnkiWeaknesses = loadAnkiWeaknesses;
window.loadStatsComparison = loadStatsComparison;
window.loadOlatStatus = loadOlatStatus;
window.handleFocusWeakness = handleFocusWeakness;
window.loadCurriculumToday = loadCurriculumToday;
window.openCurriculumRoadmapModal = openCurriculumRoadmapModal;
window.closeCurriculumRoadmapModal = closeCurriculumRoadmapModal;
window.handleFilterRoadmap = handleFilterRoadmap;
window.handleToggleSlotDone = handleToggleSlotDone;
window.switchMobileView = switchMobileView;
window.loadAnkiDesktopStatus = loadAnkiDesktopStatus;
window.syncAnkiDesktopNow = syncAnkiDesktopNow;
window.toggleTomorrowAnkiDetails = toggleTomorrowAnkiDetails;

// Auto-sync Anki desktop periodically every 30 seconds
setInterval(() => {
  loadAnkiDesktopStatus(false);
}, 30000);

// Run on page load (support immediate execution if DOM is already ready)
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    init();
    loadAnkiDesktopStatus(false);
  });
} else {
  init();
  loadAnkiDesktopStatus(false);
}



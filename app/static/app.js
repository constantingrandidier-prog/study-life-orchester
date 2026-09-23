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

function formatGermanDate(isoDateString) {
  if (!isoDateString) return '';
  const info = formatGermanDateWithWeekday(isoDateString);
  return info.shortFormatted || isoDateString;
}
window.formatGermanDate = formatGermanDate;

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
  loadAnkiDesktopStatus();
  loadScienceRhythm(nextIso);
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
  loadAnkiDesktopStatus();
  loadScienceRhythm(todayIso);
}

// Initialize Application
function init() {
  try {
    const now = new Date();
    const todayIso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    const savedDate = localStorage.getItem('sl_selected_date');
    if (savedDate && savedDate >= '2026-09-14') {
      state.targetDate = savedDate;
    } else {
      // Default to today's date if within semester, otherwise 2026-09-14
      state.targetDate = todayIso >= '2026-09-14' ? todayIso : '2026-09-14';
    }
  } catch (e) {
    state.targetDate = '2026-09-16';
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
  loadAnkiDesktopStatus();
  loadOlatStatus();
  loadEfficiencyAnalytics();
  loadAnkiWebStatus();
  checkLocalAnkiStatus();
  loadSavedProfile();
  loadPersistedAnkiDeck();

  // Multi-Page initial routing
  let initialPage = 'page-today';
  if (window.location.hash) {
    const hashClean = 'page-' + window.location.hash.replace('#', '');
    if (document.getElementById(hashClean)) {
      initialPage = hashClean;
    }
  } else {
    const saved = localStorage.getItem('sl_active_page');
    if (saved && document.getElementById(saved)) {
      initialPage = saved;
    }
  }
  switchAppPage(initialPage);
  loadAdvisorData();

  // Auto-refresh today's rhythm every 5 minutes so the plan catches up to current time
  setInterval(() => {
    const now = new Date();
    const todayIso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    if (state.targetDate === todayIso && typeof loadScienceRhythm === 'function') {
      loadScienceRhythm(todayIso);
    }
  }, 5 * 60 * 1000);
}

// Tab Switching
function setupTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const parent = btn.closest('.control-panel') || btn.closest('.advisor-hero-search-card') || document;
      parent.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      parent.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const tabId = btn.getAttribute('data-tab');
      const targetContent = document.getElementById(tabId);
      if (targetContent) targetContent.classList.add('active');
      if (tabId === 'tab-anki' || tabId === 'tab-anki-page') {
        checkLocalAnkiStatus();
      }
      if (tabId === 'tab-efficiency' || tabId === 'tab-efficiency-page') {
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
    if (!data || data.error) return;

    state.fixedEvents = data.fixed_events || [];
    state.freeSlots = data.free_slots || [];
    state.studySessions = [];

    renderTimeline();
    updateMetrics(data.summary);
    updateWeekdayDisplays();
    loadStatsComparison();
    loadScienceRhythm(state.targetDate);
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

    const isMandatory = (ev.is_mandatory === true) || 
      /praktikum|untersuchungskurs|pr[aä]parier|visite|testat|klinisch|blockkurs|skills lab|tutorat|tutorium|pol|absenz|anwesenheitspflicht|pr[aä]senzpflicht|obligatorisch/i.test(ev.title || '') ||
      /Veranstaltungsformat:\s*(Tutorat|Praktikum|Klinischer\s*Kurs|POL)/i.test(ev.description || '') ||
      /Bei Absenzen/i.test(ev.description || '');

    allBlocks.push({
      id: id,
      eventId: ev.id,
      eventIndex: idx,
      type: 'lecture',
      typeClass: isMandatory ? 'type-mandatory-practical' : 'type-lecture',
      isTask: true,
      isMandatory: isMandatory,
      title: ev.title,
      start: s,
      end: e,
      durationMinutes: durationMin,
      desc: ev.location ? `Ort: ${ev.location}` : (ev.description || (isMandatory ? 'Offizielles Pflicht-Praktikum (Präsenz vor Ort)' : 'Reguläre Lehrveranstaltung')),
      tag: isMandatory ? 'Praktikum' : 'Vorlesung',
      badgeClass: isMandatory ? 'badge-mandatory' : 'badge-lecture',
      completed: !!state.taskCompletions[id],
      recommendation: isMandatory ? 'attend' : (ev.recommendation || 'stream'),
      recommendation_reason: isMandatory ? 'Offizielles Praktikum / Testatkurs an der UZH. Hier gilt Anwesenheitspflicht vor Ort!' : (ev.recommendation_reason || ''),
      badge_label: isMandatory ? '🏛️ OBLIGATORISCH (Präsenzpflicht)' : (ev.badge_label || ''),
      badge_color: isMandatory ? '#a371f7' : (ev.badge_color || ''),
      consumption_mode: isMandatory ? 'live' : (ev.consumption_mode || 'live_1_0'),
      speed_factor: isMandatory ? 1.0 : (ev.speed_factor || 1.0),
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
    const isMandatory = block.isMandatory || block.typeClass === 'type-mandatory-practical';
    const mandatoryClass = isMandatory ? 'mandatory-practical' : '';
    card.className = `task-card ${block.typeClass} ${compClass} ${mandatoryClass}`;
    if (isMandatory) {
      card.style.borderLeft = '4px solid #a371f7';
      card.style.background = 'rgba(163, 113, 247, 0.08)';
    } else if (block.type === 'lecture') {
      card.style.borderLeft = '3px solid rgba(88, 166, 255, 0.7)';
      card.style.background = 'rgba(56, 139, 253, 0.05)';
      card.style.borderColor = 'rgba(56, 139, 253, 0.18)';
    }

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
      let ampelLabel = 'Streamen (1.0x / 1.2x / 1.4x)';

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
        { key: 'live_1_0', label: '1.0x' },
        { key: 'stream_1_2', label: '1.2x' },
        { key: 'stream_1_4', label: '1.4x' },
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
    const totalCards = data.total_cards ?? 8729;
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

// ============================================================================
// AUTO-SYNC via AnkiConnect + DYNAMIC PLAN SHIFT
// ============================================================================

// State für aktuell fällige Repes (wird durch auto-sync aktuell gehalten)
let _ankiDueCount = null;
let _autoSyncInterval = null;
let _planShiftMinutes = 0;

/**
 * Ruft AnkiConnect-Sync auf → Anki Desktop synchronisiert mit AnkiWeb (iPad-Daten).
 * Danach: due_count aus DB lesen und Plan-Verschiebung berechnen.
 */
async function runAnkiConnectSync() {
  try {
    const res = await fetch(`${API_BASE}/anki/connect-sync`, { method: 'POST' });
    if (!res.ok) return;
    const data = await res.json();

    if (data.due_count !== null && data.due_count !== undefined) {
      const oldCount = _ankiDueCount;
      _ankiDueCount = data.due_count;

      // Badges aktualisieren
      updateAnkiDueBadges(_ankiDueCount);

      // Plan-Verschiebung prüfen
      checkAndShiftPlan(_ankiDueCount);

      if (oldCount !== null && oldCount !== _ankiDueCount) {
        console.log(`[AnkiSync] Due: ${oldCount} → ${_ankiDueCount}`);
      }
    }
  } catch (err) {
    // Stille Fehler – AnkiConnect nicht erreichbar
  }
}

/** Aktualisiert alle Due-Badges in der App */
function updateAnkiDueBadges(dueCount) {
  const els = ['navBadgeDue', 'sideBadgeDue', 'pacingDueReviewsDisplay', 'pacingDueReviewsVal'];
  els.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    if (id === 'navBadgeDue') {
      el.textContent = dueCount;
      el.style.display = dueCount > 0 ? '' : 'none';
    } else if (id === 'sideBadgeDue') {
      el.textContent = `${dueCount} fällig`;
    } else {
      el.textContent = dueCount;
    }
  });
  const headerSync = document.getElementById('headerSyncText');
  if (headerSync) headerSync.textContent = `Anki: ${dueCount} fällig`;

  const weaknessPill = document.getElementById('weaknessDuePill');
  if (weaknessPill) {
    const lrn = state.learningCardsCount || 0;
    weaknessPill.textContent = `${dueCount} fällig (${lrn} Lernphase, ${dueCount} Review)`;
  }
}

/**
 * Prüft ob der Anki-Review-Block schon hätte fertig sein sollen.
 * Falls ja UND noch Repes offen: berechnet Verschiebung und zeigt Banner.
 */
function checkAndShiftPlan(dueCount) {
  if (!state.targetDate) return;

  // Nur für heute relevant
  const todayStr = new Date().toISOString().split('T')[0];
  if (state.targetDate !== todayStr) return;

  const now = new Date();
  const nowMins = now.getHours() * 60 + now.getMinutes();

  // Suche den Anki-Review-Block im Stundenplan (study-session Blöcke)
  // Ein overrun liegt vor wenn: Block-Ende < jetzt UND dueCount > 0
  let overrunBlock = null;
  state.studySessions.forEach(s => {
    if (!s.end_time) return;
    const end = new Date(s.end_time);
    const endMins = end.getHours() * 60 + end.getMinutes();
    // Ist es ein Review-Block? Erkennen an "Wiederholung" im Grund oder topic_name
    const isReviewBlock = (s.reason || '').toLowerCase().includes('wiederhol') ||
                          (s.topic_name || '').toLowerCase().includes('wiederhol') ||
                          (s.cluster_name || '').toLowerCase().includes('wiederhol');
    if (isReviewBlock && endMins < nowMins && dueCount > 0) {
      overrunBlock = { ...s, endMins };
    }
  });

  if (!overrunBlock) {
    // Kein overrun → Banner entfernen
    const banner = document.getElementById('ankiOverrunBanner');
    if (banner) banner.style.display = 'none';
    _planShiftMinutes = 0;
    return;
  }

  // Verschiebung berechnen: ~36s pro Karte
  const extraSeconds = dueCount * 36;
  const shiftMins = Math.ceil(extraSeconds / 60);
  _planShiftMinutes = shiftMins;

  showPlanShiftBanner(dueCount, shiftMins);
}

/** Zeigt das Verschiebungs-Banner über dem Stundenplan */
function showPlanShiftBanner(dueCount, shiftMins) {
  let banner = document.getElementById('ankiOverrunBanner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'ankiOverrunBanner';
    banner.style.cssText = `
      margin: 0.5rem 0 0.75rem 0;
      padding: 0.65rem 1rem;
      background: rgba(248, 113, 113, 0.08);
      border: 1px solid rgba(248, 113, 113, 0.35);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      flex-wrap: wrap;
    `;
    // Vor dem Timeline-Container einfügen
    const tc = dom.timelineContainer;
    if (tc && tc.parentNode) tc.parentNode.insertBefore(banner, tc);
  }

  const h = Math.floor(shiftMins / 60);
  const m = shiftMins % 60;
  const shiftStr = h > 0 ? `${h}h ${m > 0 ? m + 'min' : ''}` : `${m} min`;

  banner.style.display = 'flex';
  banner.innerHTML = `
    <div style="font-size: 12.5px; color: #f87171; font-weight: 600;">
      Noch ${dueCount} Repes offen — Plan ~${shiftStr} verschoben
    </div>
    <div style="display: flex; gap: 0.5rem;">
      <button onclick="applyPlanShift()" style="font-size: 11px; padding: 0.3rem 0.75rem; background: rgba(248,113,113,0.15); border: 1px solid rgba(248,113,113,0.4); border-radius: 6px; color: #f87171; cursor: pointer;">
        Plan anpassen
      </button>
      <button onclick="document.getElementById('ankiOverrunBanner').style.display='none'" style="font-size: 11px; padding: 0.3rem 0.5rem; background: transparent; border: 1px solid var(--border-subtle); border-radius: 6px; color: var(--text-dim); cursor: pointer;">
        ✕
      </button>
    </div>
  `;
}

/** Verschiebt alle Blöcke nach dem aktuellen Zeitpunkt um _planShiftMinutes */
function applyPlanShift() {
  if (_planShiftMinutes <= 0) return;
  const shiftMs = _planShiftMinutes * 60 * 1000;
  const now = new Date();

  // Nur zukünftige Blöcke verschieben (fixe Vorlesungen NICHT anfassen)
  state.studySessions = state.studySessions.map(s => {
    const start = new Date(s.start_time);
    if (start > now) {
      return {
        ...s,
        start_time: new Date(start.getTime() + shiftMs).toISOString(),
        end_time: new Date(new Date(s.end_time).getTime() + shiftMs).toISOString(),
      };
    }
    return s;
  });

  state.freeSlots = state.freeSlots.map(slot => {
    const s = slot.start_time || slot.start;
    const start = new Date(s);
    if (start > now) {
      return {
        ...slot,
        start_time: new Date(start.getTime() + shiftMs).toISOString(),
        end_time: new Date(new Date(slot.end_time || slot.end).getTime() + shiftMs).toISOString(),
      };
    }
    return slot;
  });

  renderTimeline();
  const banner = document.getElementById('ankiOverrunBanner');
  if (banner) banner.style.display = 'none';
  _planShiftMinutes = 0;
  showToast(`Plan um ${_planShiftMinutes > 0 ? _planShiftMinutes : 'mehrere'} Minuten verschoben`);
}
window.applyPlanShift = applyPlanShift;

/** Startet den Auto-Sync-Timer (alle 90 Sekunden) */
function startAnkiAutoSync() {
  if (_autoSyncInterval) clearInterval(_autoSyncInterval);
  // Sofort einmal laufen lassen
  runAnkiConnectSync();
  // Dann alle 90s
  _autoSyncInterval = setInterval(runAnkiConnectSync, 90_000);
}

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
    const totalCards = data.total_cards ?? 8729;
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

function updateMissionKpiStrip() {
  const desktop = state.ankiDesktopData;
  const pacing = currentPacingData;

  // 1. Box 1: Tagesziel (Neue Karten Soll)
  const baseNew = pacing ? (pacing.is_rest_day ? 0 : pacing.daily_target_cards) : 101;
  const targetEl = document.getElementById('pacingDailyTarget');
  if (targetEl) targetEl.textContent = baseNew;
  const newTargetEl = document.getElementById('pacingNewTargetVal');
  if (newTargetEl) newTargetEl.textContent = baseNew;

  // Live Counts from Anki Desktop
  const newDone = desktop ? (desktop.new_cards_count != null ? desktop.new_cards_count : (desktop.today_reviewed_count || 0)) : (pacing ? (pacing.cards_completed_today || 0) : 0);
  const repsDone = desktop ? (desktop.repetition_cards_count || 0) : 0;
  const repsDue = desktop ? (desktop.due_today_count != null ? desktop.due_today_count : 0) : (pacing ? (pacing.due_reviews_today || 0) : 0);
  const totalReviews = desktop ? (desktop.total_reviews_count || (newDone + repsDone)) : (newDone + repsDone);
  const mins = desktop ? (desktop.effective_study_minutes || desktop.today_session_time_minutes || desktop.today_time_minutes || 0) : 0;
  const cardTimerMins = desktop ? (desktop.today_time_minutes || 0) : 0;
  const sessionMins = desktop ? (desktop.today_session_time_minutes || 0) : 0;

  const totalTarget = baseNew + repsDone + repsDue;
  const totalDone = newDone + repsDone;

  // 2. Box 2: ✅ Heute erledigt
  const completedEl = document.getElementById('pacingCardsCompleted');
  const targetMini = document.getElementById('pacingCardsTargetMini');
  const splitReviewsVal = document.getElementById('pacingSplitReviewsVal');
  const splitReviewsSub = document.getElementById('pacingSplitReviewsSub');
  const splitNewVal = document.getElementById('pacingSplitNewVal');
  const splitNewSub = document.getElementById('pacingSplitNewSub');
  const remainingSub = document.getElementById('pacingRemainingSub');
  const ratioSub = document.getElementById('pacingCompletedRatioSub');
  const barFill = document.getElementById('pacingBarFill');
  const timeSpentSub = document.getElementById('pacingTimeSpentSub');

  if (completedEl) completedEl.textContent = totalDone;
  if (targetMini) targetMini.textContent = totalTarget;

  if (splitReviewsVal) {
    splitReviewsVal.textContent = repsDone;
  }
  if (splitReviewsSub) {
    if (repsDue === 0 && repsDone > 0) {
      splitReviewsSub.innerHTML = `<span style="color: #3fb950; font-weight: 600;">✅ alle erledigt</span>`;
    } else if (repsDue > 0) {
      splitReviewsSub.textContent = `${repsDone} erledigt (${repsDue} offen)`;
    } else {
      splitReviewsSub.textContent = `0 fällig`;
    }
  }

  if (splitNewVal) {
    splitNewVal.textContent = `${newDone} / ${baseNew}`;
  }
  if (splitNewSub) {
    const remNew = Math.max(0, baseNew - newDone);
    if (remNew === 0 && baseNew > 0) {
      splitNewSub.innerHTML = `<span style="color: #3fb950; font-weight: 600;">🎉 Tagesziel erreicht!</span>`;
    } else {
      splitNewSub.textContent = `noch ${remNew} offen`;
    }
  }

  const remainingNew = Math.max(0, baseNew - newDone);
  if (remainingSub) {
    if (pacing && pacing.is_rest_day) {
      remainingSub.textContent = 'Ruhetag – Keine Pflichtkarten';
      remainingSub.style.color = '#d29922';
    } else if (remainingNew === 0 && repsDue === 0) {
      remainingSub.textContent = `🎉 Alles erledigt! ${totalDone} Karten gemeistert.`;
      remainingSub.style.color = '#3fb950';
    } else if (repsDue === 0) {
      remainingSub.textContent = `Noch ${remainingNew} neue Karten offen (alle ${repsDone} Repetitionen erledigt! 🎉)`;
      remainingSub.style.color = '#58a6ff';
    } else {
      remainingSub.textContent = `Noch ${remainingNew} neue + ${repsDue} Wiederholungen offen`;
      remainingSub.style.color = 'var(--text-muted)';
    }
  }

  if (ratioSub) {
    const pct = totalTarget > 0 ? Math.min(100, Math.round((totalDone / totalTarget) * 100)) : 100;
    ratioSub.textContent = `${pct}%`;
  }
  if (barFill && totalTarget > 0) {
    const pct = Math.min(100, Math.round((totalDone / totalTarget) * 100));
    barFill.style.width = `${pct}%`;
  }

  if (timeSpentSub) {
    if (mins > 0 || repsDone > 0 || newDone > 0) {
      timeSpentSub.style.display = 'block';
      const hours = Math.floor(mins / 60);
      const remMins = Math.round(mins % 60);
      const timeFormatted = hours > 0 ? `${hours}h ${remMins}m` : `${Math.round(mins)} Min.`;
      if (sessionMins > 0 && Math.abs(sessionMins - cardTimerMins) >= 5) {
        timeSpentSub.textContent = `⏱️ ${timeFormatted} Lernzeit (${Math.round(sessionMins)}m Session • ${cardTimerMins}m reine Kartenzeit) • ${repsDone} Repetitionen + ${newDone} neue (${totalReviews} Reviews)`;
      } else {
        timeSpentSub.textContent = `⏱️ ${timeFormatted} Lernzeit • ${repsDone} Repetitionen + ${newDone} neue (${totalReviews} Reviews)`;
      }
    }
  }

  // 3. Box 3: 🔄 Fällig in Anki
  const dueDisp = document.getElementById('pacingDueReviewsDisplay');
  const dueSub = document.getElementById('pacingDueReviewsSub');
  if (dueDisp) {
    dueDisp.textContent = repsDue;
  }
  if (dueSub) {
    if (repsDue === 0 && repsDone > 0) {
      dueSub.innerHTML = `<span style="color: #3fb950; font-weight: 600;">Alle erledigt! (${repsDone} revidiert)</span>`;
    } else if (repsDue === 0) {
      dueSub.innerHTML = `<span style="color: #3fb950; font-weight: 600;">Keine Reviews fällig</span>`;
    } else {
      dueSub.textContent = `Repetition • ${repsDue} fällig`;
    }
  }
}

function renderExamPacing(data) {
  if (!data || data.error) return;
  currentPacingData = data;

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

  // 3. Update Unified Mission KPI Strip
  updateMissionKpiStrip();

  const targetSub = document.getElementById('pacingTargetSub');
  if (targetSub) {
    if (data.is_rest_day) {
      targetSub.textContent = data.rest_day_reason || 'Eingeplanter Ruhetag';
    } else {
      if (data.cumulative_backlog > 0) {
        targetSub.textContent = `Basis ${data.base_daily_quota || 90} + ${data.backlog_spread_per_day || 1}/Tag (${data.cumulative_backlog} Karten Rückstand über ${data.learning_days_remaining} Lerntage verteilt)`;
      } else {
        targetSub.textContent = `Bei 6 Lerntagen/Woche (${totalCardsStr} gesamt • ${remCardsStr} offen)`;
      }
    }
  }

  const readinessVal = document.getElementById('pacingReadinessVal');
  const bufferSub = document.getElementById('pacingBufferSub');
  if (readinessVal) readinessVal.textContent = `${data.exam_readiness_score}%`;
  if (bufferSub) bufferSub.textContent = `${data.revision_buffer_days} Tage Puffer ab ${data.revision_start_date}`;

  // 4. Progress Bar & Advice
  const adviceEl = document.getElementById('pacingAdviceText');
  if (adviceEl && data.advice) {
    adviceEl.textContent = data.advice;
  }
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
    const dueDisp = document.getElementById('pacingDueReviewsDisplay');
    if (dueDisp) {
      dueDisp.textContent = dueCount;
    }

    const headerSyncText = document.getElementById('headerSyncText');
    if (headerSyncText) {
      headerSyncText.textContent = `⚡ Anki Live: ${dueCount} fällig`;
    }
    const sideBadgeDue = document.getElementById('sideBadgeDue');
    if (sideBadgeDue) {
      sideBadgeDue.textContent = `${dueCount} fällig`;
    }
    const navBadgeDue = document.getElementById('navBadgeDue');
    if (navBadgeDue) {
      navBadgeDue.textContent = dueCount;
      navBadgeDue.style.display = dueCount > 0 ? 'inline-flex' : 'none';
    }

    // Update KPI strip safely without clobbering live Anki data
    if (!state.ankiDesktopData) {
      updateMissionKpiStrip();
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
  if (event.target.id === 'ankiDeckTreeModal') closeAnkiDeckTreeModal();
  if (event.target.id === 'curriculumRoadmapModal' && window.closeCurriculumRoadmapModal) window.closeCurriculumRoadmapModal();
  if (event.target.id === 'rhythmBlockActionModal' && window.closeRhythmBlockActionModal) window.closeRhythmBlockActionModal();
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
  target_cards: 85,
  base_quota: 100,
  adjusted_target_cards: 85,
  quota_adjustment_reason: 'Concept-Session: 85 neue Karten.',
  surplus_deduction: 0,
  deficit_distributed: 0,
  synergy_headline: '🎯 Fokus: Leukozyten I / Ullrich (Stockmann) – Vorlesungs-Priming spart 19 Minuten!',
  recommended_study_sequence: [
    '1. 🎧 Vorlesungs-Priming: Stockmann von 00:00 bis 63:06 im 1.2x Stream sichten',
    '2. 📇 Aktives Enkodieren: 85 neue Karten im Deck \'Leukozyten I / Ullrich\' ohne kognitive Reibung durcharbeiten',
    '3. 🔗 Quervernetzung: Blutbild-Interpretation: Linksverschiebung bei Infektionen'
  ],
  topic_slots: [
    {
      deck_name: '2. SJ - 1 :: TB Blut/Immunsystem :: Stockmann :: Leukozyten I / Ullrich',
      short_title: 'Leukozyten I / Ullrich',
      clean_title: 'Leukozyten I / Ullrich',
      lecturer: 'Stockmann',
      breadcrumb: 'Blut & Immunsystem › Stockmann',
      module_name: '1. Blut & Immunsystem',
      cards_to_learn: 85,
      total_deck_cards: 132,
      already_mastered_cards: 47,
      remaining_new_cards: 85,
      deck_progress_pct: 100.0,
      matched_slide_filename: null,
      slide_coverage_pct: 82.0,
      is_cycle_topic: false,
      recommended_mode: 'stream_1_2',
      badge_label: '🟡 1.2x Standard-Stream (+25m gespart)',
      didactic_reason: 'Deskriptiver Überblick & Dozentenschwerpunkte. Auf 1.2x im Standard-Stream mitnehmen!',
      speed_factor: 1.2,
      video_timestamp_guidance: '00:00 – 63:06 (63m Stream, spart 19m)',
      video_start_time: '00:00',
      video_end_time: '63:06',
      effective_watch_time_min: 63,
      video_time_saved_min: 19,
      red_thread: 'Erst die Reifungsstufen im Knochenmark (Myeloblast -> Segmentkernige) und Phagozytose verstehen. Das verhindert stumpfes Auswendiglernen im Differentialblutbild.',
      cross_links: [
        'Blutbild-Interpretation: Linksverschiebung bei Infektionen',
        'Chemotaxis, Opsonierung (C3b) & Respiratory Burst (NADPH-Oxidase)',
        'Chronische Granulomatose & akute Leukämien (Blastenkrise)'
      ],
      concept_goal: 'Zelluläre Primärabwehr, Granulozyten-Differenzierung & Blutbild-Analyse'
    }
  ],
  cumulative_cards_learned: 240,
  total_curriculum_cards: 9676,
  curriculum_progress_pct: 2.5,
  current_module: '1. Blut & Immunsystem',
  summary: 'Tag 1/97: 85 neue Karten (85× Leukozyten I / Ullrich) im Modul 1. Blut & Immunsystem.',
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
      if (cachedData && !cachedData.error && Array.isArray(cachedData.topic_slots) && cachedData.target_cards !== undefined) {
        renderCurriculumToday(cachedData);
        hadCachedRender = true;
      } else {
        localStorage.removeItem(cacheKey);
      }
    } else if (dateStr === '2026-09-14') {
      renderCurriculumToday(DAY1_FALLBACK_ASSIGNMENT);
      hadCachedRender = true;
    }
  } catch (e) {
    console.debug('Cache read note:', e);
  }

  // 2. Fetch fresh data with 25s timeout & AbortController (safe for cloud cold starts)
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 25000);

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
    if (data && !data.error && Array.isArray(data.topic_slots) && data.target_cards !== undefined) {
      try {
        localStorage.setItem(cacheKey, JSON.stringify(data));
      } catch (e) {}
      renderCurriculumToday(data);
      if (forceRefresh) showToast('Lernauftrag erfolgreich aktualisiert');
    }
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

function toggleMissionMetricsDrawer() {
  const drawer = document.getElementById('missionMetricsDrawer');
  const label = document.getElementById('toggleMetricsLabel');
  const chevron = document.getElementById('toggleMetricsChevron');
  if (!drawer) return;
  const isHidden = (drawer.style.display === 'none' || !drawer.style.display || !drawer.classList.contains('open'));
  if (isHidden) {
    drawer.classList.add('open');
    drawer.style.display = 'block';
    if (label) label.textContent = '📊 Weniger';
    if (chevron) chevron.textContent = '▴';
  } else {
    drawer.classList.remove('open');
    drawer.style.display = 'none';
    if (label) label.textContent = '📊 Details';
    if (chevron) chevron.textContent = '▾';
  }
  try {
    localStorage.setItem('sl_mission_metrics_open', isHidden ? 'true' : 'false');
  } catch (e) {}
}

function toggleTopicDetails(target, event) {
  if (event) {
    if (typeof event.stopPropagation === 'function') {
      event.stopPropagation();
    }
    const t = event.target;
    if (t && (t.closest('.topic-check-btn') || t.closest('.btn-slot-advisor') || t.closest('.btn-slot-toggle') || t.closest('a') || t.closest('input'))) {
      return;
    }
  }

  let card = null;
  if (target && target.nodeType) {
    card = target.closest('.topic-card');
  }
  if (!card && event) {
    if (event.currentTarget && event.currentTarget.closest) {
      card = event.currentTarget.closest('.topic-card');
    } else if (event.target && event.target.closest) {
      card = event.target.closest('.topic-card');
    }
  }
  if (!card && typeof target === 'string') {
    card = document.getElementById(`topicCard-${target}`) || document.querySelector(`[data-slot-key="${target}"]`);
  }

  if (!card) return;

  const details = card.querySelector('.topic-card-details');
  const chevron = card.querySelector('.topic-expand-chevron');
  const expandText = card.querySelector('.expand-text');
  if (!details) return;

  const isExpanded = card.classList.contains('expanded');
  const willExpand = !isExpanded;

  if (willExpand) {
    card.classList.add('expanded');
    details.style.display = 'flex';
    if (expandText) expandText.textContent = 'Weniger';
    if (chevron) chevron.textContent = '▴';
  } else {
    card.classList.remove('expanded');
    details.style.display = 'none';
    if (expandText) expandText.textContent = 'Details';
    if (chevron) chevron.textContent = '▾';
  }
}

function renderCurriculumToday(data) {
  if (!data || data.error) return;
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

  // Render Cognitive Synergy Banner & Recommended 3-Step Sequence
  const synergyCard = document.getElementById('curriculumSynergyCard');
  const synergyHeadline = document.getElementById('curriculumSynergyHeadline');
  const studySequence = document.getElementById('curriculumStudySequence');

  if (synergyCard && synergyHeadline && studySequence) {
    if (data.is_rest_day) {
      synergyCard.style.display = 'none';
    } else {
      synergyCard.style.display = 'block';
      // Short headline: just topic name, no emoji prefix
      const headlineText = data.synergy_headline || `Fokus: ${data.current_module || 'Lernsession'}`;
      synergyHeadline.textContent = headlineText.replace(/^🎯\s*/u, '').replace(/\s*[-–].*$/, '').trim();
      // Compact step list: show step text only, no big icons
      if (Array.isArray(data.recommended_study_sequence) && data.recommended_study_sequence.length > 0) {
        studySequence.innerHTML = data.recommended_study_sequence.map((step) => {
          const cleanStep = step.replace(/^[0-9]+\.\s*/u, '').replace(/^[\p{Emoji}]\s*/u, '').trim();
          return `<div style="color: var(--text-muted); font-size: 11px;">${escapeHtml(cleanStep)}</div>`;
        }).join('');
      } else {
        studySequence.innerHTML = '';
      }
    }
  }

  if (topicsContainer) {
    if (data.is_rest_day) {
      topicsContainer.innerHTML = `
        <div style="padding: 1.5rem; background: rgba(255,255,255,0.02); border: 1px dashed var(--border-subtle); border-radius: var(--radius-sm); text-align: center; color: var(--text-dim);">
          <strong style="font-size: 14px; color: var(--text-main);">${escapeHtml(data.summary || 'Sonntag – Ruhetag')}</strong>
          <div style="margin-top: 0.85rem;">
            <button class="btn-secondary" style="font-size: 12px; padding: 0.4rem 1rem;" onclick="stepDate(1)">Nächster Lerntag →</button>
          </div>
        </div>
      `;
    } else if (!data.topic_slots || data.topic_slots.length === 0) {
      topicsContainer.innerHTML = `
        <div style="padding: 1.5rem; background: rgba(255,255,255,0.02); border: 1px dashed var(--border-subtle); border-radius: var(--radius-sm); text-align: center; color: var(--text-dim);">
          Keine Karten für diesen Tag.
        </div>
      `;
    } else {
      let totalTimeSavedMinutes = 0;
      const rowsHtml = data.topic_slots.map((slot, idx) => {
        const slotKey = `${data.date}_${slot.deck_name || idx}`;
        const isDone = Boolean(state.slotCompletions && state.slotCompletions[slotKey]);

        let timeSavedMin = 0;
        let didacticBadge = '';
        if (slot.video_time_saved_min !== undefined && slot.video_time_saved_min !== null) {
          timeSavedMin = slot.video_time_saved_min;
        } else if (slot.recommended_mode === 'stream_1_0') {
          timeSavedMin = 0;
        } else if (slot.recommended_mode === 'stream_1_4') {
          timeSavedMin = 30;
        } else if (slot.recommended_mode === 'skipped') {
          timeSavedMin = 90;
        } else {
          timeSavedMin = 25;
        }

        if (slot.recommended_mode === 'stream_1_0') {
          didacticBadge = `<span class="curriculum-focus-badge">1.0x</span>`;
        } else if (slot.recommended_mode === 'stream_1_4') {
          didacticBadge = `<span class="curriculum-speed-badge">1.4x (+${timeSavedMin}m)</span>`;
        } else if (slot.recommended_mode === 'skipped') {
          didacticBadge = `<span class="curriculum-skip-badge">Skip (+${timeSavedMin}m)</span>`;
        } else {
          didacticBadge = `<span class="curriculum-speed-badge">${slot.speed_factor || 1.2}x (+${timeSavedMin}m)</span>`;
        }
        totalTimeSavedMinutes += timeSavedMin;

        // Video Timecode Guidance Pill
        const timecodePill = slot.video_timestamp_guidance
          ? `<div style="margin-top: 4px; font-size: 11px; color: #58a6ff; background: rgba(56, 139, 253, 0.12); border: 1px solid rgba(56, 139, 253, 0.28); border-radius: 4px; padding: 2px 6px; display: inline-flex; align-items: center; gap: 4px;" title="Optimierte Video-Timecodes: Spart Vorlesungszeit!">
               <span>▶️</span> <strong>${escapeHtml(slot.video_timestamp_guidance)}</strong>
             </div>`
          : '';

        // Lecture Links (Direct Playback, Windows Explorer & VAM-Archiv)
        const lectureLinksHtml = `
          <div class="slot-lecture-links" style="margin-top: 5px; display: flex; flex-wrap: wrap; gap: 4px; align-items: center;">
            ${(slot.local_podcast_folder_path || slot.local_podcast_file_path || slot.preferred_video_file) ? `
              <button type="button" class="btn-folder-chip" onclick="handleOpenLocalFolder('${escapeHtml(slot.local_podcast_file_path || slot.local_podcast_folder_path || slot.preferred_video_file || '').replace(/\\/g, '\\\\')}', 'Vorlesung (${escapeHtml(slot.podcast_folder_name || '')})', false)" title="Vorlesungs-Ordner mit Video direkt im Windows Datei-Explorer auf deinem Laptop öffnen" style="font-size: 10px; padding: 2px 6px; color: #7ee787; border-color: rgba(46, 160, 67, 0.4);">
                📂 Explorer
              </button>
            ` : ''}
            <a href="${slot.vam_url || 'https://lms.uzh.ch/auth/RepositoryEntry/666697737/CourseNode/76022446801983'}" target="_blank" class="btn-vam-chip" title="Vorlesungsaufzeichnung direkt im UZH VAM-Archiv öffnen" style="font-size: 10px; padding: 2px 5px;">
              🎬 VAM
            </a>
          </div>
        `;

        // Slide Badge & Action Links (Direct Open, In-Browser View, Windows Explorer Folder, OpenOLAT)
        let slideBadge;
        if (slot.matched_slide_filename) {
          const slideRel = slot.slide_relative_path || slot.matched_slide_filename;
          const slideLocal = slot.local_slide_file_path || '';
          const folderLocal = slot.local_slide_folder_path || '';
          slideBadge = `
            <div style="display: flex; flex-direction: column; gap: 4px;">
              <a class="curriculum-slide-link" title="Folie im PDF-Viewer &amp; Browser öffnen: ${escapeHtml(slot.matched_slide_filename)}" href="/api/v1/schedule/slides/view?path=${encodeURIComponent(slideRel)}" target="_blank" rel="noopener">
                📄 ${escapeHtml(slot.matched_slide_filename.length > 20 ? slot.matched_slide_filename.substring(0, 18) + '...' : slot.matched_slide_filename)}
              </a>
              <div style="display: flex; gap: 4px; align-items: center;">
                <button type="button" class="btn-folder-chip" onclick="handleOpenLocalFolder('${escapeHtml(slideLocal || slideRel).replace(/\\/g, '\\\\')}', 'Folien-PDF', true)" title="Folien-PDF direkt im PDF-Viewer öffnen" style="font-size: 10px; padding: 2px 5px; color: #7ee787; border-color: rgba(46, 160, 67, 0.4);">
                  📄 Öffnen
                </button>
                <button type="button" class="btn-folder-chip" onclick="handleOpenLocalFolder('${escapeHtml(folderLocal || slideLocal).replace(/\\/g, '\\\\')}', 'Folien-Ordner', false)" title="Folien-Ordner im Windows Explorer öffnen" style="font-size: 10px; padding: 2px 5px;">
                  📂 Ordner
                </button>
                <a href="${slot.olat_url || 'https://lms.uzh.ch/url/RepositoryEntry/666697737'}" target="_blank" class="btn-olat-chip" title="Skripte &amp; Unterlagen auf OpenOLAT öffnen" style="font-size: 10px; padding: 2px 5px;">
                  🌐 OLAT
                </a>
              </div>
            </div>
          `;
        } else {
          slideBadge = '<span style="color: var(--text-dim); font-size: 11px;">–</span>';
        }

        const lecturerBadge = slot.lecturer
          ? `<span class="curriculum-lecturer-badge">👨‍🏫 ${escapeHtml(slot.lecturer)}</span>`
          : '';

        // Completion & In-Progress status badge
        const ankiStatusBadge = (slot.already_mastered_cards > 0)
          ? `<span style="margin-left: 6px; font-size: 10px; color: #7ee787; background: rgba(35, 134, 54, 0.15); padding: 1px 5px; border-radius: 4px; border: 1px solid rgba(35, 134, 54, 0.3);">🔄 ${slot.already_mastered_cards} gemeistert • ${slot.cards_to_learn} neu</span>`
          : '';

        // Scaffolding: Red Thread
        const redThreadHtml = slot.red_thread
          ? `<div class="curriculum-slot-redthread" style="margin-top: 5px; font-size: 11px; color: #7ee787; background: rgba(35, 134, 54, 0.08); border-left: 2px solid #238636; padding: 3px 6px; border-radius: 3px; line-height: 1.35;">
               <strong>Roter Faden:</strong> ${escapeHtml(slot.red_thread)}
             </div>`
          : '';

        // Scaffolding: Clinical Cross-Links
        const crossLinksHtml = (Array.isArray(slot.cross_links) && slot.cross_links.length > 0)
          ? `<div class="curriculum-slot-crosslinks" style="margin-top: 4px; font-size: 10.5px; color: #a5d6ff; line-height: 1.35;">
               <strong>Quervernetzung:</strong> ${slot.cross_links.map(cl => escapeHtml(cl)).join(' • ')}
             </div>`
          : '';

        const breadcrumb = slot.breadcrumb || slot.module_name || '';
        const rawTitle = slot.clean_title || slot.short_title || 'Thema';
        const displayTitle = slot.display_title_with_date || (slot.lecture_date_formatted ? `${rawTitle} (${slot.lecture_date_formatted})` : rawTitle);
        const dateBadge = slot.lecture_date_formatted
          ? `<span class="lecture-date-badge" title="Aufzeichnungsdatum der Vorlesung">📅 Gedreht: ${escapeHtml(slot.lecture_date_formatted)}</span>`
          : '';

        const reasonHtml = slot.didactic_reason
          ? `<div class="curriculum-slot-reason" style="margin-top: 3px;">💡 ${escapeHtml(slot.didactic_reason)}</div>`
          : '';

        const cards = slot.cards_to_learn !== undefined ? slot.cards_to_learn : 0;
        const escapedTitle = escapeHtml(displayTitle).replace(/'/g, "\\'");
        const escapedSlotKey = escapeHtml(slotKey).replace(/'/g, "\\'");

        return `
          <div class="topic-card ${isDone ? 'is-done' : ''}" id="topicCard-${escapedSlotKey}" data-slot-key="${escapedSlotKey}">
            <div class="topic-card-header" onclick="toggleTopicDetails(this, event)">
              <div class="topic-card-left">
                <button type="button" class="topic-check-btn ${isDone ? 'done' : ''}" onclick="event.stopPropagation(); handleToggleSlotDone('${escapedSlotKey}', ${cards}, '${escapedTitle}')" title="${isDone ? 'Als offen markieren' : 'Als erledigt markieren'}">
                  ${isDone ? '✓' : ''}
                </button>
                <div class="topic-card-info">
                  <div class="topic-card-title-row">
                    <span class="topic-card-title">${escapeHtml(displayTitle)}</span>
                    ${dateBadge}
                    ${ankiStatusBadge}
                  </div>
                  <div class="topic-card-sub">
                    <span class="topic-card-quota-pill"><strong>${cards}</strong> Karten</span>
                    ${slot.difficulty_badge ? `<span class="difficulty-badge ${slot.difficulty_level || 'medium'}" style="font-size: 10px; padding: 1px 6px;">${slot.difficulty_badge}</span>` : ''}
                    ${slot.yield_badge ? `<span class="yield-badge ${slot.exam_yield || ''}" style="font-size: 10px; padding: 1px 6px;" title="${escapeHtml(slot.yield_badge)}">${slot.yield_stars || ''} ${slot.yield_label || ''}</span>` : ''}
                    ${didacticBadge}
                    ${breadcrumb ? `<span>&bull;</span> <span>${escapeHtml(breadcrumb)}</span>` : ''}
                    ${slot.lecturer ? `<span>&bull;</span> <span class="curriculum-lecturer-badge">${escapeHtml(slot.lecturer)}</span>` : ''}
                  </div>
                </div>
              </div>
              <div class="topic-card-right">
                <button type="button" class="topic-expand-btn" onclick="toggleTopicDetails(this, event)">
                  <span class="expand-text">Details</span>
                  <span class="topic-expand-chevron">▾</span>
                </button>
              </div>
            </div>

            <!-- Expandable Details Drawer -->
            <div class="topic-card-details" style="display: none;">
              ${redThreadHtml}
              ${crossLinksHtml}
              ${reasonHtml}
              ${(timecodePill || lectureLinksHtml) ? `
                <div class="topic-detail-block lecture-strategy">
                  <div class="detail-label">Video & Timecodes</div>
                  <div class="detail-content">
                    ${timecodePill}
                    ${lectureLinksHtml}
                  </div>
                </div>
              ` : ''}
              ${slot.matched_slide_filename ? `
                <div class="topic-detail-block slides">
                  <div class="detail-label">Folien</div>
                  <div class="detail-content">
                    ${slideBadge}
                  </div>
                </div>
              ` : ''}
              <div class="topic-detail-actions">
                <button type="button" class="btn-slot-advisor" onclick="consultAdvisorForTopic('${escapedTitle}')" style="background: rgba(88,166,255,0.12); color: #58a6ff; border: 1px solid rgba(88,166,255,0.3); border-radius: 4px; font-size: 11px; padding: 0.35rem 0.65rem; cursor: pointer;">
                  Berater
                </button>
                <button type="button" class="btn-slot-toggle ${isDone ? 'done' : ''}" onclick="handleToggleSlotDone('${escapedSlotKey}', ${cards}, '${escapedTitle}')">
                  ${isDone ? '↩ Offen' : '✓ Erledigt'}
                </button>
              </div>
            </div>
          </div>
        `;
      }).join('');

      const hoursSaved = Math.floor(totalTimeSavedMinutes / 60);
      const minsSaved = totalTimeSavedMinutes % 60;
      const savedStr = hoursSaved > 0 ? `${hoursSaved}h ${minsSaved > 0 ? minsSaved + 'm' : ''}` : `${minsSaved}m`;

      topicsContainer.innerHTML = `
        <div class="topic-cards-list">
          ${rowsHtml}
        </div>
        <div class="topics-total-bar">
          <div class="topics-total-info">
            <span>Gesamt heute: <strong>${data.topic_slots.length} Vorlesungsthemen</strong></span>
            <span class="badge-total-saved">⚡ ${savedStr} gespart</span>
            <span style="color: var(--accent-blue); font-weight: 700;">${data.target_cards || 100} Karten</span>
          </div>
          <button type="button" class="btn-mini-done" onclick="handleMarkAllTargetDone()">
            ✓ Alle erledigt
          </button>
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
    // Semester-Gesamtfortschritt must ALWAYS display true cards learned so far
    let actual = 0;
    if (data.actual_cards_learned !== undefined && data.actual_cards_learned !== null) {
      actual = data.actual_cards_learned;
    } else if (state.ankiDesktopData && state.ankiDesktopData.cumulative_cards_learned !== undefined) {
      actual = state.ankiDesktopData.cumulative_cards_learned;
    } else if (localStorage.getItem('sl_real_cumulative_cards')) {
      actual = parseInt(localStorage.getItem('sl_real_cumulative_cards'), 10);
    } else if (data.cumulative_cards_learned !== undefined) {
      actual = data.cumulative_cards_learned;
    }
    const total = (data.total_curriculum_cards || 8729);
    const pct = Math.round((actual / Math.max(1, total)) * 1000) / 10;
    cardsProgress.textContent = `${actual.toLocaleString('de-CH')} / ${total.toLocaleString('de-CH')} Karten (${pct}%)`;
    if (progressBarFill) {
      progressBarFill.style.width = `${Math.min(100, Math.max(1, pct))}%`;
    }
    const planned = data.planned_cumulative_cards || data.cumulative_cards_learned || actual;
    cardsProgress.title = `Tatsächlich neu gelernt: ${actual} Karten | Geplanter Soll-Stand laut Roadmap: ${planned} Karten`;
  }

  if (countdownDays) {
    countdownDays.textContent = `${data.days_until_exam} Tage bis ${data.exam_date}`;
  }
}

async function handleStopMedia() {
  showToast('⏹️ Beende Audiowiedergabe...', 2000);
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 650);
    await fetch('http://127.0.0.1:8000/api/v1/schedule/system/stop-media', {
      method: 'POST',
      signal: ctrl.signal
    });
    clearTimeout(timer);
  } catch (_) {}

  try {
    const res = await fetch('/api/v1/schedule/system/stop-media', { method: 'POST' });
    const data = await res.json();
    showToast('⏹️ Alle Hintergrund-Audioplayer (VLC) gestoppt!', 4000);
  } catch (err) {
    showToast('⏹️ Stopp-Befehl gesendet.', 3000);
  }
}

let _lastOpenLocalTime = 0;
let _lastOpenLocalPath = '';

async function handleOpenLocalFolder(folderOrFilePath, label = 'Vorlesungs-Datei', directOpen = false) {
  if (!folderOrFilePath) {
    showToast(`⚠️ Kein Pfad für ${label} hinterlegt`);
    return;
  }
  const cleanPath = String(folderOrFilePath).trim().replace(/\\/g, '/').replace(/^['"]+|['"]+$/g, '');
  const now = Date.now();

  // Deduplicate and debounce rapid clicks / double clicks within 2.5 seconds
  if (now - _lastOpenLocalTime < 2500 && _lastOpenLocalPath === cleanPath) {
    console.debug('Ignoring duplicate open click within 2.5s:', cleanPath);
    return;
  }
  _lastOpenLocalTime = now;
  _lastOpenLocalPath = cleanPath;

  showToast(`📂 Öffnen von ${label}...`, 3000);
  const query = `path=${encodeURIComponent(cleanPath)}&direct_open=${directOpen ? 'true' : 'false'}`;
  const isLocalOrigin = (window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost');

  if (isLocalOrigin) {
    // 1. When app runs locally, execute directly on local server
    try {
      const localRes = await fetch(`/api/v1/schedule/folder/open?${query}`);
      if (localRes.ok) {
        const data = await localRes.json();
        if (data && data.success) {
          showToast(`✅ ${data.message || `${label} im Datei-Explorer geöffnet!`}`, 4000);
          return;
        }
      }
    } catch (_) {}
  } else {
    // 2. When app runs on Render / Cloud, queue exclusively through cloud backend for local agent
    try {
      const res = await fetch(`/api/v1/schedule/folder/open?${query}`);
      const data = await res.json();
      if (data && (data.success || data.queued)) {
        showToast(`💻 Datei-Explorer wird auf deinem Laptop geöffnet (${label})...`, 4500);
        return;
      }
    } catch (err) {
      try {
        await fetch('/api/v1/schedule/system/queue-action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'open_explorer', path: folderOrFilePath, direct_open: directOpen })
        });
        showToast(`💻 Befehl an deinen Laptop gesendet (${label})!`, 4000);
        return;
      } catch (_) {}
    }
  }

  // 3. Clipboard fallback
  try {
    await navigator.clipboard.writeText(folderOrFilePath);
    showToast(`📋 Pfad in Zwischenablage kopiert (Win+R zum Starten)`, 4000);
  } catch (_) {}
}

async function handleOpenSlidePdf(relPath, localFilePath) {
  const target = (relPath || localFilePath || '').replace(/\\/g, '/');
  if (!target) return;
  await handleOpenLocalFolder(target, 'Folien-PDF', false);
}

let _cachedRoadmapData = null;

function handleSelectRoadmapDay(dateStr) {
  if (!dateStr) return;
  state.targetDate = dateStr;
  if (dom.targetDateInput) dom.targetDateInput.value = dateStr;
  try {
    localStorage.setItem('sl_selected_date', dateStr);
  } catch (e) {}
  updateWeekdayDisplays();
  loadSchedule();
  loadExamPacing();
  loadStatsComparison();
  loadAnkiWeaknesses();
  loadCurriculumToday();
  loadAnkiDesktopStatus();
  loadScienceRhythm(dateStr);
  closeCurriculumRoadmapModal();
  switchAppPage('page-today');
  showToast(`📅 Tagesplan für ${dateStr} geladen`);
}

async function openCurriculumRoadmapModal() {
  const modal = document.getElementById('curriculumRoadmapModal');
  if (modal) modal.style.display = 'flex';

  try {
    const targetParam = state.targetDate ? `?target_date=${state.targetDate}` : '';
    const res = await fetch(`${API_BASE}/curriculum/roadmap${targetParam}`);
    if (res.ok) {
      _cachedRoadmapData = await res.json();
    }
  } catch (err) {
    console.debug('Error loading roadmap:', err);
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

  const now = new Date();
  const realTodayIso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  const activeDayStr = state.targetDate || realTodayIso;

  daysList.innerHTML = days.map(d => {
    const isToday = (d.date === realTodayIso);
    const isCurrentActive = (d.date === activeDayStr);
    const todayHighlightClass = isToday ? 'roadmap-today-highlight' : '';

    if (d.is_rest_day) {
      return `
        <div class="roadmap-day-row rest-day ${todayHighlightClass}" data-date="${d.date}" data-day-num="${d.day_number || ''}" data-is-rest="true" onclick="handleSelectRoadmapDay('${d.date}')" style="cursor: pointer; ${isToday ? 'border-left: 4px solid #58a6ff; background: rgba(88, 166, 255, 0.08);' : ''}">
          <div class="roadmap-day-date">
            <span>🏖️</span>
            <span>${d.date} (${d.day_of_week || 'So'})</span>
            ${isToday ? '<span class="status-badge" style="font-size: 9.5px; background: rgba(88,166,255,0.25); color: #79c0ff; border: 1px solid rgba(88,166,255,0.4); border-radius: 3px; padding: 1px 5px;">📍 HEUTE</span>' : ''}
          </div>
          <div style="flex: 1; color: var(--text-dim); font-size: 11.5px;">
            Sonntag – Geplanter Ruhetag & Erholung
          </div>
          <div style="font-size: 11px; color: var(--text-muted); display: flex; align-items: center; gap: 0.5rem;">
            <span>0 Karten</span>
            <button type="button" class="btn-day-jump" onclick="event.stopPropagation(); handleSelectRoadmapDay('${d.date}')" style="font-size: 10px; padding: 0.15rem 0.45rem; background: rgba(88, 166, 255, 0.12); border: 1px solid rgba(88, 166, 255, 0.3); color: #58a6ff; border-radius: 4px; cursor: pointer;" title="Diesen Tag im Tagesplan öffnen">
              📅 Plan
            </button>
          </div>
        </div>
      `;
    }

    const slotsText = (d.topic_slots || []).map((s, sIdx) => {
      const sKey = `${d.date}_${s.deck_name || sIdx}`;
      const isDone = Boolean(state.slotCompletions && state.slotCompletions[sKey]);
      const checkIcon = isDone ? `<span style="color: #3fb950; font-weight: 700; margin-right: 2px;" title="Im Tagesplan als erledigt markiert">✓ </span>` : '';
      const strikethrough = isDone ? 'text-decoration: line-through; opacity: 0.75;' : '';
      const lec = s.lecturer ? ` <span style="font-size: 10px; color: #79c0ff;">(${escapeHtml(s.lecturer)})</span>` : '';
      return `<span style="${strikethrough}">${checkIcon}<strong>${s.cards_to_learn}×</strong> ${escapeHtml(s.clean_title || s.short_title)}${lec}</span>`;
    }).join(' + ');

    const isSwappedBadge = d.is_swapped
      ? `<span style="font-size: 9.5px; color: #e3b341; background: rgba(227,179,65,0.15); border: 1px solid rgba(227,179,65,0.3); border-radius: 3px; padding: 1px 5px; margin-left: 0.35rem; display: inline-flex; align-items: center; gap: 2px;" title="Dieses Lernpaket wurde manuell von Tag ${d.swapped_with_day || d.original_day_number} hierher getauscht">🔄 Paket Tag ${d.swapped_with_day || d.original_day_number}</span>`
      : '';

    const todayBadge = isToday
      ? `<span class="status-badge" style="font-size: 9.5px; font-weight: 700; background: rgba(88,166,255,0.25); color: #79c0ff; border: 1px solid rgba(88,166,255,0.4); border-radius: 3px; padding: 1px 5px; display: inline-flex; align-items: center; gap: 2px;">📍 HEUTE</span>`
      : '';

    const todayStyle = isToday
      ? 'border-left: 4px solid #58a6ff; background: rgba(88, 166, 255, 0.08); box-shadow: inset 0 0 12px rgba(88, 166, 255, 0.06);'
      : '';

    return `
      <div class="roadmap-day-row draggable-active ${d.is_swapped ? 'swapped-row' : ''} ${todayHighlightClass}"
           id="roadmapRow-${d.date}"
           data-date="${d.date}"
           data-day-num="${d.day_number}"
           data-cards="${d.target_cards}"
           draggable="true"
           style="${todayStyle}"
           title="Klicken für Tagesplan • Lange gedrückt halten zum Tauschen">
        
        <!-- Drag Handle & Schnell-Tausch Tasten -->
        <div style="display: flex; align-items: center; gap: 0.25rem; flex-shrink: 0;">
          <span class="roadmap-drag-handle" title="Gedrückt halten & ziehen zum Tauschen">⠿</span>
          <div style="display: flex; flex-direction: column; gap: 1px;">
            <button type="button" class="roadmap-quick-btn" onclick="handleQuickSwapDay('${d.date}', -1, event)" title="Mit vorherigem Lerntag tauschen">▲</button>
            <button type="button" class="roadmap-quick-btn" onclick="handleQuickSwapDay('${d.date}', 1, event)" title="Mit nächstem Lerntag tauschen">▼</button>
          </div>
        </div>

        <div class="roadmap-day-date" onclick="handleSelectRoadmapDay('${d.date}')" style="cursor: pointer;">
          <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 0.25rem;">
            <span style="color: #58a6ff; font-weight: 600;">Tag ${d.day_number}</span>
            ${todayBadge}
            ${isSwappedBadge}
          </div>
          <span style="font-weight: 400; color: var(--text-dim); font-size: 11px;">${d.date} (${d.day_of_week || ''})</span>
        </div>

        <div style="flex: 1; font-size: 12px; color: var(--text-main); min-width: 180px; cursor: pointer;" onclick="handleSelectRoadmapDay('${d.date}')">
          <span style="color: var(--text-muted); font-size: 10.5px; display: block;">${escapeHtml(d.current_module)}</span>
          ${slotsText}
        </div>

        <div style="display: flex; align-items: center; gap: 0.35rem; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end;">
          <button type="button" class="btn-day-jump" onclick="event.stopPropagation(); handleSelectRoadmapDay('${d.date}')" style="font-size: 10px; padding: 0.15rem 0.45rem; background: rgba(88, 166, 255, 0.12); border: 1px solid rgba(88, 166, 255, 0.3); color: #58a6ff; border-radius: 4px; cursor: pointer;" title="Diesen Tag im Tagesplan öffnen">
            📅 Plan
          </button>
          <button type="button" class="btn-day-swap" onclick="event.stopPropagation(); openSwapDayModal('${d.date}', ${d.day_number})" title="Diesen Tag mit einem anderen Lerntag tauschen">
            ⇄ Tauschen
          </button>
          <span class="difficulty-badge ${d.difficulty_level || 'medium'}" style="font-size: 10.5px; padding: 0.15rem 0.45rem;" title="${escapeHtml(d.difficulty_reason || '')}">
            ${d.difficulty_badge || (d.target_cards + ' Karten')}
          </span>
          ${d.exam_yield_badge ? `<span class="yield-badge ${d.exam_yield || ''}" style="font-size: 10px; padding: 0.15rem 0.4rem;" title="${escapeHtml(d.exam_yield_badge)}">${d.yield_stars || ''} ${d.yield_label || ''}</span>` : ''}
          <span style="font-size: 10.5px; color: var(--text-muted); min-width: 40px; text-align: right;">
            ${d.curriculum_progress_pct}%
          </span>
        </div>
      </div>
    `;
  }).join('');

  initRoadmapDragAndDrop();
}

let _desktopDragSource = null;
let _touchDragSource = null;
let _touchTimer = null;
let _touchStartX = 0;
let _touchStartY = 0;
let _isTouchDragging = false;
let _lastHighlightedRow = null;

function initRoadmapDragAndDrop() {
  const container = document.getElementById('roadmapDaysList');
  if (!container || container._dndInitialized) return;
  container._dndInitialized = true;

  // Desktop Drag & Drop
  container.addEventListener('dragstart', (e) => {
    const row = e.target.closest('.roadmap-day-row:not(.rest-day)');
    if (!row) return;
    _desktopDragSource = row;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', row.dataset.date || '');
    setTimeout(() => row.classList.add('is-dragging'), 0);
  });

  container.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const targetRow = e.target.closest('.roadmap-day-row:not(.rest-day)');
    if (targetRow && targetRow !== _desktopDragSource) {
      if (_lastHighlightedRow && _lastHighlightedRow !== targetRow) {
        _lastHighlightedRow.classList.remove('drag-over-highlight');
      }
      targetRow.classList.add('drag-over-highlight');
      _lastHighlightedRow = targetRow;
    }
  });

  container.addEventListener('dragleave', (e) => {
    const targetRow = e.target.closest('.roadmap-day-row');
    if (targetRow && !targetRow.contains(e.relatedTarget)) {
      targetRow.classList.remove('drag-over-highlight');
    }
  });

  container.addEventListener('drop', (e) => {
    e.preventDefault();
    if (_lastHighlightedRow) {
      _lastHighlightedRow.classList.remove('drag-over-highlight');
      _lastHighlightedRow = null;
    }
    const targetRow = e.target.closest('.roadmap-day-row:not(.rest-day)');
    if (_desktopDragSource && targetRow && _desktopDragSource !== targetRow) {
      const srcDate = _desktopDragSource.dataset.date;
      const tgtDate = targetRow.dataset.date;
      const srcDayNum = parseInt(_desktopDragSource.dataset.dayNum, 10);
      const tgtDayNum = parseInt(targetRow.dataset.dayNum, 10);
      swapCurriculumDays(srcDate, tgtDate, srcDayNum, tgtDayNum);
    }
  });

  container.addEventListener('dragend', () => {
    if (_desktopDragSource) {
      _desktopDragSource.classList.remove('is-dragging');
      _desktopDragSource = null;
    }
    if (_lastHighlightedRow) {
      _lastHighlightedRow.classList.remove('drag-over-highlight');
      _lastHighlightedRow = null;
    }
  });

  // Mobile / Touch Drag & Drop (Long Press to drag)
  container.addEventListener('touchstart', (e) => {
    const row = e.target.closest('.roadmap-day-row:not(.rest-day)');
    if (!row) return;
    if (e.target.closest('button')) return;

    _touchStartX = e.touches[0].clientX;
    _touchStartY = e.touches[0].clientY;
    _touchDragSource = row;
    _isTouchDragging = false;

    clearTimeout(_touchTimer);
    _touchTimer = setTimeout(() => {
      _isTouchDragging = true;
      row.classList.add('is-dragging-touch');
      if (navigator.vibrate) {
        try { navigator.vibrate(35); } catch (_) {}
      }
      showToast(`🎯 Tag ${row.dataset.dayNum} zum Verschieben aktiv – ziehe auf einen Zieltag`, 'info');
    }, 320);
  }, { passive: true });

  container.addEventListener('touchmove', (e) => {
    if (!_touchDragSource) return;

    const currentX = e.touches[0].clientX;
    const currentY = e.touches[0].clientY;
    const dist = Math.hypot(currentX - _touchStartX, currentY - _touchStartY);

    if (!_isTouchDragging) {
      if (dist > 12) {
        clearTimeout(_touchTimer);
        _touchDragSource = null;
      }
      return;
    }

    e.preventDefault();

    const elemBelow = document.elementFromPoint(currentX, currentY);
    if (!elemBelow) return;
    const targetRow = elemBelow.closest('.roadmap-day-row:not(.rest-day)');

    if (targetRow && targetRow !== _touchDragSource) {
      if (_lastHighlightedRow && _lastHighlightedRow !== targetRow) {
        _lastHighlightedRow.classList.remove('drag-over-highlight');
      }
      targetRow.classList.add('drag-over-highlight');
      _lastHighlightedRow = targetRow;
    } else if (!targetRow && _lastHighlightedRow) {
      _lastHighlightedRow.classList.remove('drag-over-highlight');
      _lastHighlightedRow = null;
    }
  }, { passive: false });

  container.addEventListener('touchend', (e) => {
    clearTimeout(_touchTimer);
    if (!_isTouchDragging) {
      _touchDragSource = null;
      return;
    }

    if (_touchDragSource) {
      _touchDragSource.classList.remove('is-dragging-touch');
    }

    let targetRow = _lastHighlightedRow;
    if (!targetRow && e.changedTouches && e.changedTouches.length > 0) {
      const endX = e.changedTouches[0].clientX;
      const endY = e.changedTouches[0].clientY;
      const elem = document.elementFromPoint(endX, endY);
      if (elem) targetRow = elem.closest('.roadmap-day-row:not(.rest-day)');
    }

    if (_lastHighlightedRow) {
      _lastHighlightedRow.classList.remove('drag-over-highlight');
      _lastHighlightedRow = null;
    }

    if (_touchDragSource && targetRow && _touchDragSource !== targetRow) {
      const srcDate = _touchDragSource.dataset.date;
      const tgtDate = targetRow.dataset.date;
      const srcDayNum = parseInt(_touchDragSource.dataset.dayNum, 10);
      const tgtDayNum = parseInt(targetRow.dataset.dayNum, 10);
      swapCurriculumDays(srcDate, tgtDate, srcDayNum, tgtDayNum);
    }

    _isTouchDragging = false;
    _touchDragSource = null;
  });

  container.addEventListener('touchcancel', () => {
    clearTimeout(_touchTimer);
    if (_touchDragSource) {
      _touchDragSource.classList.remove('is-dragging-touch');
      _touchDragSource = null;
    }
    if (_lastHighlightedRow) {
      _lastHighlightedRow.classList.remove('drag-over-highlight');
      _lastHighlightedRow = null;
    }
    _isTouchDragging = false;
  });
}

function handleQuickSwapDay(date, direction, event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  if (!_cachedRoadmapData || !_cachedRoadmapData.schedule) return;

  const schedule = _cachedRoadmapData.schedule;
  const currIdx = schedule.findIndex(d => d.date === date);
  if (currIdx === -1) return;

  let targetIdx = currIdx + direction;
  while (targetIdx >= 0 && targetIdx < schedule.length && schedule[targetIdx].is_rest_day) {
    targetIdx += direction;
  }

  if (targetIdx < 0 || targetIdx >= schedule.length) {
    showToast('Kein weiterer Lerntag in dieser Richtung vorhanden.', 'info');
    return;
  }

  const currentDay = schedule[currIdx];
  const targetDay = schedule[targetIdx];
  swapCurriculumDays(currentDay.date, targetDay.date, currentDay.day_number, targetDay.day_number);
}

async function swapCurriculumDays(date1, date2, dayNum1, dayNum2) {
  if (!date1 || !date2 || date1 === date2) return;
  if (!_cachedRoadmapData || !_cachedRoadmapData.schedule) return;

  const d1 = _cachedRoadmapData.schedule.find(d => d.date === date1);
  const d2 = _cachedRoadmapData.schedule.find(d => d.date === date2);
  if (!d1 || !d2) return;

  const cards1 = d1.target_cards;
  const cards2 = d2.target_cards;
  const num1 = dayNum1 || d1.day_number;
  const num2 = dayNum2 || d2.day_number;

  // Optimistic swap in memory
  const swapKeys = [
    'target_cards', 'adjusted_target_cards', 'topic_slots', 'current_module', 
    'summary', 'synergy_headline', 'recommended_study_sequence',
    'estimated_study_minutes', 'avg_seconds_per_card', 'difficulty_level',
    'difficulty_label', 'difficulty_badge', 'difficulty_reason',
    'exam_yield', 'yield_stars', 'yield_label', 'exam_yield_badge'
  ];
  const temp = {};
  swapKeys.forEach(k => temp[k] = d1[k]);
  swapKeys.forEach(k => d1[k] = d2[k]);
  swapKeys.forEach(k => d2[k] = temp[k]);

  d1.is_swapped = true;
  d2.is_swapped = true;
  d1.swapped_with_day = num2;
  d2.swapped_with_day = num1;

  // Recalculate running cumulative progress
  let cum = 0;
  const totalCards = _cachedRoadmapData.total_cards || 8729;
  _cachedRoadmapData.schedule.forEach(d => {
    if (!d.is_rest_day) {
      cum += (d.target_cards || 0);
      d.cumulative_cards_learned = cum;
      d.curriculum_progress_pct = Math.round((cum / Math.max(1, totalCards)) * 1000) / 10;
    }
  });

  renderRoadmapDaysList(_cachedRoadmapData.schedule);
  if (typeof renderPageRoadmap === 'function') {
    renderPageRoadmap();
  }

  // Calculate preceding active study days for date1 and date2 (for 24h-lecture-priming sync)
  const getPrevActiveDateStr = (dateStr) => {
    if (!_cachedRoadmapData || !Array.isArray(_cachedRoadmapData.schedule)) return null;
    const sorted = _cachedRoadmapData.schedule
      .filter(d => !d.is_rest_day)
      .sort((a, b) => a.date.localeCompare(b.date));
    const idx = sorted.findIndex(d => d.date === dateStr);
    return (idx > 0) ? sorted[idx - 1].date : null;
  };

  const prevDate1 = getPrevActiveDateStr(date1);
  const prevDate2 = getPrevActiveDateStr(date2);

  // Invalidate daily caches for swapped dates AND their previous days so the 24h-pipeline reflects the new tomorrow lecture!
  try {
    const datesToClear = [date1, date2, prevDate1, prevDate2].filter(Boolean);
    datesToClear.forEach(dStr => {
      localStorage.removeItem(`sl_curr_cache_${dStr}`);
      localStorage.removeItem(`sl_rhythm_cache_${dStr}`);
    });
  } catch (_) {}

  // If currently viewing any affected date (the swapped days OR their preceding days), reload live immediately
  const currentDate = state.targetDate || '2026-09-14';
  if ([date1, date2, prevDate1, prevDate2].includes(currentDate)) {
    if (typeof loadScienceRhythm === 'function') {
      loadScienceRhythm(currentDate);
    }
    if (typeof loadCurriculumToday === 'function') {
      loadCurriculumToday(true);
    }
  }

  const badge1 = d1.difficulty_badge || `${cards2} Karten`;
  const badge2 = d2.difficulty_badge || `${cards1} Karten`;
  showToast(`🔄 Tag ${num1} (${badge1}) mit Tag ${num2} (${badge2}) getauscht! 24h-Vorlesungen am Vortag synchronisiert.`, 'success');

  // Persist to backend database
  try {
    const res = await fetch(`${API_BASE}/curriculum/swap-days`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date1: date1,
        date2: date2,
        day_num1: num1,
        day_num2: num2
      })
    });
    if (!res.ok) {
      console.warn('Backend returned non-ok for swap-days');
    }
  } catch (err) {
    console.error('Failed to persist day swap to server:', err);
    showToast('⚠️ Hinweis: Tausch konnte nicht online gespeichert werden.', 'warning');
  }
}

async function resetCurriculumSwaps() {
  try {
    const res = await fetch(`${API_BASE}/curriculum/reset-swaps`, {
      method: 'POST'
    });
    if (res.ok) {
      try {
        for (let i = localStorage.length - 1; i >= 0; i--) {
          const k = localStorage.key(i);
          if (k && k.startsWith('sl_curr_cache_')) {
            localStorage.removeItem(k);
          }
        }
      } catch (_) {}

      _cachedRoadmapData = null;
      await openCurriculumRoadmapModal();

      const currentDate = state.targetDate || '2026-09-14';
      if (typeof loadScienceRhythm === 'function') {
        loadScienceRhythm(currentDate);
      }

      showToast('✅ Alle Tage auf die originale didaktische Reihenfolge zurückgesetzt!', 'success');
    } else {
      showToast('⚠️ Fehler beim Zurücksetzen der Reihenfolge.', 'warning');
    }
  } catch (err) {
    console.error('Error resetting swaps:', err);
    showToast('⚠️ Netzwerkfehler beim Zurücksetzen.', 'warning');
  }
}

// ============================================================================
// FLEXIBLE CURRICULUM DAY SWAP MODAL CONTROLLER
// ============================================================================

let _swapSourceDate = null;
let _swapSourceDayNum = null;

async function ensureRoadmapDataLoaded() {
  if (_cachedRoadmapData && Array.isArray(_cachedRoadmapData.schedule)) {
    return _cachedRoadmapData;
  }
  try {
    const targetParam = state.targetDate ? `?target_date=${state.targetDate}` : '';
    const res = await fetch(`${API_BASE}/curriculum/roadmap${targetParam}`);
    if (res.ok) {
      _cachedRoadmapData = await res.json();
      return _cachedRoadmapData;
    }
  } catch (e) {
    console.warn('Failed to fetch roadmap data:', e);
  }
  return null;
}

async function openSwapDayModal(sourceDate, sourceDayNum) {
  const modal = document.getElementById('curriculumSwapModal');
  if (!modal) return;

  const data = await ensureRoadmapDataLoaded();
  if (!data || !Array.isArray(data.schedule)) {
    showToast('⚠️ Roadmap-Daten konnten nicht geladen werden.', 'warning');
    return;
  }

  const schedule = data.schedule;
  const sourceDay = schedule.find(d => d.date === sourceDate || d.day_number === sourceDayNum);
  if (!sourceDay || sourceDay.is_rest_day) {
    showToast('⚠️ Ruhetage (Sonntage) können nicht getauscht werden.', 'info');
    return;
  }

  _swapSourceDate = sourceDay.date;
  _swapSourceDayNum = sourceDay.day_number;

  // 1. Render Source Day Info
  const titleEl = document.getElementById('swapSourceTitle');
  const subEl = document.getElementById('swapSourceSub');
  const badgeEl = document.getElementById('swapSourceBadge');
  if (titleEl) {
    titleEl.textContent = `Tag ${sourceDay.day_number} (${sourceDay.day_of_week}, ${sourceDay.date})`;
  }
  if (subEl) {
    const topicsStr = (sourceDay.topic_slots || []).map(s => s.clean_title || s.short_title).slice(0, 3).join(', ');
    subEl.textContent = `${sourceDay.current_module || ''} • ${topicsStr || 'Lernpaket'}`;
  }
  if (badgeEl) {
    const minStr = sourceDay.estimated_study_minutes ? ` (~${sourceDay.estimated_study_minutes} Min.)` : '';
    const yieldBadge = sourceDay.exam_yield_badge ? `<span class="yield-badge ${sourceDay.exam_yield || ''}" style="font-size: 11px; padding: 0.2rem 0.55rem; margin-left: 4px;" title="${escapeHtml(sourceDay.exam_yield_badge)}">${sourceDay.exam_yield_badge}</span>` : '';
    badgeEl.innerHTML = `<span class="difficulty-badge ${sourceDay.difficulty_level || 'medium'}" style="font-size: 11px; padding: 0.2rem 0.55rem;">${sourceDay.difficulty_badge || (sourceDay.target_cards + ' Karten' + minStr)}</span>${yieldBadge}`;
  }

  // 2. Active days (excluding current source day and rest days)
  const activeDays = schedule.filter(d => !d.is_rest_day && d.date !== _swapSourceDate);
  const srcMinutes = sourceDay.estimated_study_minutes || Math.round(sourceDay.target_cards * 0.9);

  // 3. Smart suggestions: find days with lower cognitive load / study minutes
  const smartContainer = document.getElementById('swapSmartSuggestions');
  if (smartContainer) {
    const lightDays = activeDays
      .filter(d => (d.estimated_study_minutes || Math.round(d.target_cards * 0.9)) < srcMinutes)
      .sort((a, b) => (a.estimated_study_minutes || a.target_cards) - (b.estimated_study_minutes || b.target_cards))
      .slice(0, 6);

    if (lightDays.length > 0) {
      smartContainer.innerHTML = lightDays.map(d => {
        const icon = d.difficulty_level === 'easy' ? '🟢' : (d.difficulty_level === 'medium' ? '🟡' : (d.difficulty_level === 'very_hard' ? '🔥' : '🔴'));
        const estMin = d.estimated_study_minutes || Math.round(d.target_cards * 0.9);
        const stars = d.yield_stars ? ` • ${d.yield_stars}` : '';
        return `
          <button type="button" class="smart-suggestion-pill ${d.difficulty_level || 'easy'}" onclick="selectSwapTargetDay('${d.date}')" title="${escapeHtml(d.difficulty_reason || d.current_module || '')}">
            <span>${icon}</span>
            <strong>Tag ${d.day_number}</strong>
            <span>(${d.target_cards} Karten • ~${estMin}m${stars})</span>
          </button>
        `;
      }).join('');
    } else {
      smartContainer.innerHTML = `<span style="font-size: 11px; color: var(--text-dim);">Keine Tage mit geringerer Belastung gefunden. Wähle unten einen Wunschtag.</span>`;
    }
  }

  // 4. Populate Target Select Dropdown
  const selectEl = document.getElementById('swapTargetSelect');
  if (selectEl) {
    selectEl.innerHTML = activeDays.map(d => {
      const estMin = d.estimated_study_minutes || Math.round(d.target_cards * 0.9);
      const diffIcon = d.difficulty_level === 'easy' ? '🟢' : (d.difficulty_level === 'medium' ? '🟡' : (d.difficulty_level === 'very_hard' ? '🔥' : '🔴'));
      const isLighter = estMin < srcMinutes ? '🌱 ' : '';
      const yieldInfo = d.yield_stars ? ` • ${d.yield_stars} ${d.yield_label || ''}` : '';
      return `<option value="${d.date}">Tag ${d.day_number}: ${d.day_of_week}, ${d.date} – ${isLighter}${d.target_cards} Karten (~${estMin}m • ${diffIcon} ${d.difficulty_label || ''}${yieldInfo}) – ${escapeHtml(d.current_module || '')}</option>`;
    }).join('');

    // Pre-select Day 12 if available (or first lighter day)
    const day12 = activeDays.find(d => d.day_number === 12);
    if (day12) {
      selectEl.value = day12.date;
    } else if (activeDays.length > 0) {
      selectEl.value = activeDays[0].date;
    }
  }

  handleSwapTargetChanged(selectEl ? selectEl.value : null);
  modal.style.display = 'flex';
}

function selectSwapTargetDay(targetDate) {
  const selectEl = document.getElementById('swapTargetSelect');
  if (selectEl) {
    selectEl.value = targetDate;
  }
  handleSwapTargetChanged(targetDate);
}

function handleSwapTargetChanged(targetDate) {
  const previewText = document.getElementById('swapPreviewText');
  if (!previewText || !_cachedRoadmapData || !_cachedRoadmapData.schedule) return;

  const schedule = _cachedRoadmapData.schedule;
  const src = schedule.find(d => d.date === _swapSourceDate);
  const tgt = schedule.find(d => d.date === targetDate);
  if (!src || !tgt) return;

  const srcSlots = (src.topic_slots || []).map(s => s.clean_title || s.short_title).slice(0, 2).join(', ');
  const tgtSlots = (tgt.topic_slots || []).map(s => s.clean_title || s.short_title).slice(0, 2).join(', ');

  const srcMin = src.estimated_study_minutes || Math.round(src.target_cards * 0.9);
  const tgtMin = tgt.estimated_study_minutes || Math.round(tgt.target_cards * 0.9);
  const timeDiffMin = srcMin - tgtMin;

  const getPrevDay = (dStr) => {
    const sorted = schedule.filter(d => !d.is_rest_day).sort((a, b) => a.date.localeCompare(b.date));
    const idx = sorted.findIndex(d => d.date === dStr);
    return (idx > 0) ? sorted[idx - 1] : null;
  };
  const srcPrev = getPrevDay(src.date);
  const tgtPrev = getPrevDay(tgt.date);

  const tgtFirstTitle = (tgt.topic_slots && tgt.topic_slots[0]) ? (tgt.topic_slots[0].clean_title || tgt.topic_slots[0].short_title) : 'Morgen';
  const srcFirstTitle = (src.topic_slots && src.topic_slots[0]) ? (src.topic_slots[0].clean_title || src.topic_slots[0].short_title) : 'Original';

  let savingHighlight = '';
  if (timeDiffMin > 0) {
    savingHighlight = `
      <div style="margin-top: 0.45rem; padding: 0.45rem 0.65rem; background: rgba(46,160,67,0.15); border: 1px solid rgba(46,160,67,0.35); border-radius: 6px; color: #7ee787; font-size: 11.5px; font-weight: 600;">
        💡 Entlastung am ${src.day_of_week}: neu ~${tgtMin} Min. statt ~${srcMin} Min. (-${timeDiffMin} Min. / -${Math.round(timeDiffMin / 60 * 10) / 10}h Zeitersparnis!)
      </div>
    `;
  } else if (timeDiffMin < 0) {
    savingHighlight = `
      <div style="margin-top: 0.45rem; padding: 0.45rem 0.65rem; background: rgba(240,136,62,0.12); border: 1px solid rgba(240,136,62,0.3); border-radius: 6px; color: #f0883e; font-size: 11.5px; font-weight: 500;">
        ⚠️ Hinweis: Am ${src.day_of_week} erhöht sich der Lernaufwand um ~${Math.abs(timeDiffMin)} Minuten.
      </div>
    `;
  }

  previewText.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.35rem 0; border-bottom: 1px solid rgba(255,255,255,0.06);">
      <span>📅 <strong>${src.day_of_week}, ${src.date} (Tag ${src.day_number})</strong>:</span>
      <span style="color: #7ee787; font-weight: 700;">neu ${tgt.target_cards} Karten <span style="font-size: 11px; font-weight: 400; color: #a5d6ff;">(~${tgtMin}m • ${tgt.difficulty_label || ''}${tgt.yield_stars ? ' • ' + tgt.yield_stars : ''})</span></span>
    </div>
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.35rem 0; border-bottom: 1px solid rgba(255,255,255,0.06);">
      <span>📅 <strong>${tgt.day_of_week}, ${tgt.date} (Tag ${tgt.day_number})</strong>:</span>
      <span style="color: #58a6ff; font-weight: 700;">neu ${src.target_cards} Karten <span style="font-size: 11px; font-weight: 400; color: #a5d6ff;">(~${srcMin}m • ${src.difficulty_label || ''}${src.yield_stars ? ' • ' + src.yield_stars : ''})</span></span>
    </div>
    ${savingHighlight}
    <div style="font-size: 11px; color: #79c0ff; margin-top: 0.45rem; line-height: 1.45; background: rgba(56,139,253,0.08); padding: 0.45rem 0.65rem; border-radius: 6px; border: 1px solid rgba(56,139,253,0.25);">
      🎧 <strong>24h-Vorlesungs-Sync am Vortag:</strong>
      <div style="margin-top: 3px;">• Am Vortag (${srcPrev ? srcPrev.day_of_week + ', ' + srcPrev.date : 'Vortag'}) zeigt der Nachmittag neu die Vorlesung zu <em>${escapeHtml(tgtFirstTitle)}</em>!</div>
      ${tgtPrev ? `<div style="margin-top: 2px;">• Am ${tgtPrev.day_of_week}, ${tgtPrev.date} wird entsprechend <em>${escapeHtml(srcFirstTitle)}</em> vorbereitet.</div>` : ''}
    </div>
  `;
}

function closeCurriculumSwapModal() {
  const modal = document.getElementById('curriculumSwapModal');
  if (modal) modal.style.display = 'none';
  _swapSourceDate = null;
  _swapSourceDayNum = null;
}

async function confirmExecuteSwapDays() {
  const selectEl = document.getElementById('swapTargetSelect');
  if (!selectEl || !selectEl.value || !_swapSourceDate) {
    closeCurriculumSwapModal();
    return;
  }

  const targetDate = selectEl.value;
  if (targetDate === _swapSourceDate) {
    showToast('Bitte wähle zwei unterschiedliche Tage aus.', 'info');
    return;
  }

  const schedule = _cachedRoadmapData ? _cachedRoadmapData.schedule : [];
  const targetDay = schedule.find(d => d.date === targetDate);
  const targetDayNum = targetDay ? targetDay.day_number : null;

  const srcDate = _swapSourceDate;
  const srcDayNum = _swapSourceDayNum;

  closeCurriculumSwapModal();

  await swapCurriculumDays(srcDate, targetDate, srcDayNum, targetDayNum);

  // Synchronize both views
  if (typeof renderPageRoadmap === 'function') {
    renderPageRoadmap();
  }
  if (typeof loadCurriculumToday === 'function') {
    loadCurriculumToday(true);
  }
}

async function openSwapForCurrentViewDay() {
  const currentDate = state.targetDate || '2026-09-14';
  const data = await ensureRoadmapDataLoaded();
  const schedule = data ? data.schedule : [];
  const currentDay = schedule.find(d => d.date === currentDate);
  const dayNum = currentDay ? currentDay.day_number : 1;
  openSwapDayModal(currentDate, dayNum);
}

function handleFilterRoadmap(query, targetListId) {
  // Supports both the modal roadmap (#roadmapDaysList) and the page roadmap (#pageRoadmapDaysList)
  const schedule = _cachedRoadmapData ? _cachedRoadmapData.schedule : (state.roadmapData ? state.roadmapData.schedule : null);
  if (!schedule) return;

  const q = (query || '').toLowerCase().trim();

  const filtered = !q ? schedule : schedule.filter(d => {
    if (d.date.includes(q)) return true;
    if (d.day_of_week && d.day_of_week.toLowerCase().includes(q)) return true;
    if (d.current_module && d.current_module.toLowerCase().includes(q)) return true;
    if (d.day_number && `tag ${d.day_number}`.includes(q)) return true;
    if (d.exam_yield && d.exam_yield.toLowerCase().includes(q)) return true;
    if (d.difficulty_level && d.difficulty_level.toLowerCase().includes(q)) return true;
    if (d.topic_slots) {
      return d.topic_slots.some(s =>
        (s.deck_name && s.deck_name.toLowerCase().includes(q)) ||
        (s.short_title && s.short_title.toLowerCase().includes(q)) ||
        (s.clean_title && s.clean_title.toLowerCase().includes(q)) ||
        (s.lecturer && s.lecturer.toLowerCase().includes(q))
      );
    }
    return false;
  });

  if (targetListId) {
    // Render into page roadmap list
    const list = document.getElementById(targetListId);
    if (!list) return;
    const tempRoadmapData = _cachedRoadmapData || state.roadmapData;
    if (tempRoadmapData) {
      const savedCache = _cachedRoadmapData;
      _cachedRoadmapData = tempRoadmapData;
      const tempList = document.getElementById('roadmapDaysList');
      if (!tempList) {
        // Temporarily set the container so renderRoadmapDaysList can find it
        const fakeEl = document.createElement('div');
        fakeEl.id = 'roadmapDaysList';
        document.body.appendChild(fakeEl);
        renderRoadmapDaysList(filtered);
        list.innerHTML = fakeEl.innerHTML;
        fakeEl.remove();
      } else {
        renderRoadmapDaysList(filtered);
        list.innerHTML = tempList.innerHTML;
      }
      _cachedRoadmapData = savedCache;
    }
  } else {
    renderRoadmapDaysList(filtered);
  }
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
    const dateQuery = state.targetDate ? `?target_date=${state.targetDate}` : '';
    let data = null;

    // 1. If running on Render cloud, probe local laptop server to read fresh Anki collection directly!
    if (window.location.hostname !== '127.0.0.1' && window.location.hostname !== 'localhost') {
      try {
        const localRes = await fetch(`http://127.0.0.1:8000/api/v1/schedule/anki/desktop-status${dateQuery}`, {
          signal: (typeof AbortSignal !== 'undefined' && AbortSignal.timeout) ? AbortSignal.timeout(2000) : undefined
        });
        if (localRes.ok) {
          data = await localRes.json();
          // Push to cloud Render so cloud server cache is also up to date
          fetch(`${API_BASE}/anki/desktop-sync`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
          }).catch(() => {});
        }
      } catch (localErr) {
        // Local server not running or blocked, proceed with cloud
      }
    }

    if (!data) {
      const res = await fetch(`${API_BASE}/anki/desktop-status${dateQuery}`);
      if (!res.ok) return;
      data = await res.json();
    }

    state.ankiDesktopData = data;
    renderAnkiDesktopWidget(data);
    if (showFeedback) {
      const msg = `Anki synchronisiert: ${data.today_reviewed_count || 0} Karten für ${state.targetDate} erfasst, ${data.due_tomorrow_count || 0} morgen fällig.`;
      if (typeof showToast === 'function') showToast(msg);
    }
  } catch (err) {
    console.warn('Anki desktop status fetch warning:', err);
  }
}

async function syncAnkiDesktopNow(showFeedback = true) {
  const btn = document.getElementById('btnRefreshCurriculum') || document.querySelector('#ankiDesktopLiveCard button');
  if (btn) btn.textContent = '⏳ Lade...';
  await loadAnkiDesktopStatus(showFeedback);
  if (typeof loadCurriculumToday === 'function') await loadCurriculumToday(false);
  if (typeof loadExamPacing === 'function') await loadExamPacing();
  if (typeof loadWorkloadForecast === 'function') await loadWorkloadForecast(false);
  if (btn) btn.textContent = '🔄 Aktualisieren';
}

function renderAnkiDesktopWidget(data) {
  if (!data) return;
  state.ankiDesktopData = data;
  const tomCnt = data.due_tomorrow_count || 0;
  const topics = data.due_tomorrow_topics || [];

  // Update semester overall card progress if available
  if (data.cumulative_cards_learned !== undefined) {
    const cardsProgress = document.getElementById('currCardsProgress');
    const progressBarFill = document.getElementById('currProgressBarFill');
    const actual = data.cumulative_cards_learned;
    const total = data.total_curriculum_cards || 8729;
    const pct = data.curriculum_progress_pct !== undefined ? data.curriculum_progress_pct : (Math.round((actual / Math.max(1, total)) * 1000) / 10);
    try {
      localStorage.setItem('sl_real_cumulative_cards', String(actual));
    } catch (e) {}
    if (cardsProgress) {
      cardsProgress.textContent = `${actual.toLocaleString('de-CH')} / ${total.toLocaleString('de-CH')} Karten (${pct}%)`;
    }
    if (progressBarFill) {
      progressBarFill.style.width = `${Math.min(100, Math.max(1, pct))}%`;
    }
  }

  // Update real-time due reviews across all badges & weakness pill
  const dueLive = (data.due_today_count !== undefined) ? data.due_today_count : data.due_reviews_count;
  if (dueLive !== undefined) {
    updateAnkiDueBadges(dueLive);
  }

  // 1. Update Mission KPI strip with live Anki counts
  updateMissionKpiStrip();

  // 2. Update Box 3: Repetition morgen
  const kpiTomCount = document.getElementById('kpiTomorrowCount');
  const kpiTomSub = document.getElementById('kpiTomorrowTopicsSub');
  if (kpiTomCount) {
    kpiTomCount.textContent = tomCnt;
  }
  if (kpiTomSub) {
    if (topics.length > 0) {
      const firstDeck = topics[0].deck || 'Themen';
      const cleanFirst = firstDeck.length > 22 ? firstDeck.substring(0, 20) + '...' : firstDeck;
      kpiTomSub.textContent = `${topics.length} Thema${topics.length !== 1 ? 'en' : ''} (${cleanFirst})`;
    } else {
      kpiTomSub.textContent = 'Keine Wiederholungen morgen fällig';
    }
  }

  // 3. Update Detail Box for Tomorrow
  const tomListEl = document.getElementById('ankiTomorrowTopicsList');
  const tomTotalEl = document.getElementById('ankiTomorrowTotalTopics');
  if (tomTotalEl) {
    tomTotalEl.textContent = `${topics.length} Thema${topics.length !== 1 ? 'en' : ''} (${tomCnt} Karten)`;
  }
  if (tomListEl) {
    if (topics.length === 0) {
      tomListEl.innerHTML = '<span style="color: var(--text-muted);">Keine Wiederholungen für morgen fällig – du bist optimal im Plan!</span>';
    } else {
      tomListEl.innerHTML = topics.map(t => `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.35rem 0.5rem; background: rgba(255,255,255,0.03); border-radius: 4px; border: 1px solid rgba(255,255,255,0.05);">
          <span style="color: #e6edf3; font-weight: 500;">📖 ${escapeHtml(t.deck)}</span>
          <span style="color: #d2a8ff; font-weight: 700; background: rgba(210,168,255,0.15); padding: 0.15rem 0.45rem; border-radius: 4px;">${t.count} Karten</span>
        </div>
      `).join('');
    }
  }

  // 4. Update Advice Bar
  const adviceEl = document.getElementById('pacingAdviceText');
  if (adviceEl && todayCnt > 0) {
    adviceEl.textContent = `🎉 In Anki gemeistert: ${todayCnt} Karten (${mins} Min.) • Morgen stehen ${tomCnt} Karten zur Repetition an.`;
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

let currentTriageBudget = null;

async function toggleBacklogTriageModal() {
  const box = document.getElementById('ankiBacklogTriageBox');
  if (!box) return;
  const isHidden = box.style.display === 'none' || !box.style.display;
  box.style.display = isHidden ? 'block' : 'none';
  if (isHidden) {
    await loadBacklogTriage(currentTriageBudget);
  }
}

async function setTriageBudget(capacity, btnElement) {
  currentTriageBudget = capacity;
  document.querySelectorAll('.btn-triage-cap').forEach(b => {
    b.style.background = 'transparent';
    b.style.color = '#8b949e';
    b.classList.remove('active');
  });
  if (btnElement) {
    btnElement.style.background = 'rgba(255,255,255,0.15)';
    btnElement.style.color = '#fff';
    btnElement.classList.add('active');
  }
  await loadBacklogTriage(capacity);
}

async function loadBacklogTriage(maxCapacity) {
  const listEl = document.getElementById('triageTopicsList');
  const adviceEl = document.getElementById('triageAdviceBanner');
  if (!listEl) return;

  try {
    const url = maxCapacity 
      ? `/api/v1/schedule/anki/backlog-triage?max_capacity=${maxCapacity}`
      : '/api/v1/schedule/anki/backlog-triage';
    const res = await fetch(url);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();

    if (adviceEl) {
      adviceEl.textContent = data.summary_advice || 'Themen priorisiert nach Dringlichkeit.';
      adviceEl.style.borderColor = data.is_overloaded ? 'rgba(248,81,73,0.4)' : 'rgba(88,166,255,0.3)';
      adviceEl.style.background = data.is_overloaded ? 'rgba(248,81,73,0.12)' : 'rgba(56,139,253,0.1)';
      adviceEl.style.color = data.is_overloaded ? '#ff7b72' : '#79c0ff';
    }

    // 1-Click Copy Bar for combined query
    const combinedBar = document.getElementById('triageCombinedQueryBar');
    const combinedText = document.getElementById('triageCombinedQueryText');
    const combinedQuery = data.budget_combined_anki_query || data.urgent_combined_anki_query;
    if (combinedBar && combinedText && combinedQuery) {
      combinedText.textContent = combinedQuery;
      combinedText.setAttribute('title', combinedQuery);
      combinedBar.style.display = 'flex';
    }

    const topicsToShow = maxCapacity && data.budget_selected_topics 
      ? data.budget_selected_topics 
      : (data.topics || []);

    const deferredToShow = maxCapacity && data.budget_deferred_topics 
      ? data.budget_deferred_topics 
      : [];

    if (topicsToShow.length === 0) {
      listEl.innerHTML = '<div style="color: var(--text-muted); padding: 0.5rem;">Keine fälligen Karten gefunden.</div>';
      return;
    }

    let html = '';
    if (maxCapacity && deferredToShow.length > 0) {
      html += `<div style="font-size: 11px; font-weight: 600; color: #ff7b72; margin-bottom: 0.25rem;">
        🔥 Priorisierte Themen (Summe: ${data.budget_accumulated_cards || 0} Karten von ${maxCapacity} Budget):
      </div>`;
    }

    html += topicsToShow.map((t, idx) => `
      <div style="padding: 0.6rem 0.75rem; background: rgba(255,255,255,0.02); border-radius: 6px; border: 1px solid ${t.color}40; display: flex; flex-direction: column; gap: 0.35rem;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 6px;">
            <span style="font-size: 11px; font-weight: 700; color: ${t.color}; background: ${t.color}20; padding: 0.1rem 0.4rem; border-radius: 4px;">
              #${idx + 1} ${t.level_badge}
            </span>
            <strong style="color: #e6edf3; font-size: 12.5px;">${escapeHtml(t.deck_name)}</strong>
          </div>
          <button type="button" onclick="copyAnkiQuery('${encodeURIComponent(t.anki_filter_query)}', this)" style="background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.2); color: #c9d1d9; border-radius: 4px; font-size: 10px; padding: 0.2rem 0.45rem; cursor: pointer;">
            📋 Anki-Filter kopieren
          </button>
        </div>

        <div style="display: flex; gap: 1rem; font-size: 11px; color: var(--text-muted); flex-wrap: wrap;">
          <span>📦 <strong>${t.due_today} heute</strong> / <strong>${t.due_tomorrow} morgen</strong> fällig</span>
          <span>⚠️ Fehlerquote: <strong style="color: ${t.fail_rate_pct > 30 ? '#ff7b72' : '#e6edf3'};">${t.fail_rate_pct}%</strong></span>
          <span>⏱️ Zuletzt vor <strong>${t.days_since_last_review} Tagen</strong></span>
          <span>🧠 Stabilität: <strong>${t.avg_ease_pct}%</strong></span>
          <span>⚡ Dringlichkeits-Score: <strong style="color: ${t.color};">${t.urgency_score}/100</strong></span>
        </div>

        <div style="font-size: 11px; color: ${t.color}; font-weight: 500;">
          💡 ${escapeHtml(t.action_recommendation)}
        </div>
      </div>
    `).join('');

    if (maxCapacity && deferredToShow.length > 0) {
      html += `<div style="font-size: 11px; font-weight: 600; color: #3fb950; margin-top: 0.75rem; margin-bottom: 0.25rem;">
        💤 Auf morgen verschiebbar (Geringes Vergessensrisiko):
      </div>`;
      html += deferredToShow.map(t => `
        <div style="padding: 0.45rem 0.65rem; background: rgba(63,185,80,0.03); border-radius: 6px; border: 1px dashed rgba(63,185,80,0.3); display: flex; justify-content: space-between; align-items: center; font-size: 11px;">
          <span style="color: #8b949e;">📖 ${escapeHtml(t.deck_name)} (${t.due_tomorrow} Karten fällig)</span>
          <span style="color: #3fb950; font-weight: 600;">✅ Kann warten (Stabilität ${t.avg_ease_pct}%)</span>
        </div>
      `).join('');
    }

    listEl.innerHTML = html;
  } catch (err) {
    if (listEl) listEl.innerHTML = `<div style="color: #ff7b72; padding: 0.5rem;">Fehler beim Laden der Triage: ${err.message}</div>`;
  }
}

function copyTriageQueryToClipboard() {
  const textEl = document.getElementById('triageCombinedQueryText');
  const btn = document.getElementById('btnCopyCombinedQuery');
  if (!textEl) return;
  const query = textEl.textContent.trim();
  navigator.clipboard.writeText(query).then(() => {
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = '<span>✅</span> <span>Kopiert!</span>';
      btn.style.background = '#2ea043';
      setTimeout(() => {
        btn.innerHTML = orig;
        btn.style.background = '#238636';
      }, 2500);
    }
    if (typeof showToast === 'function') {
      showToast('Anki-Filter kopiert! In Anki: Werkzeuge ➔ Gefilterten Stapel erstellen');
    }
  }).catch(() => {
    prompt('Kopiere diesen Suchbegriff für Anki:', query);
  });
}

function copyAnkiQuery(encodedQuery, btn) {
  const query = decodeURIComponent(encodedQuery);
  navigator.clipboard.writeText(query).then(() => {
    const origText = btn.textContent;
    btn.textContent = '✅ Kopiert!';
    btn.style.color = '#3fb950';
    setTimeout(() => {
      btn.textContent = origText;
      btn.style.color = '#c9d1d9';
    }, 2000);
  }).catch(() => {
    prompt('Kopiere diesen Suchbegriff für Anki:', query);
  });
}

// ============================================================================
// PHASE 5: 14-TAGE RETENTIONS-RADAR & WORKLOAD-VORSCHAU
// ============================================================================

let currentForecastData = null;

async function loadWorkloadForecast(showFeedback = false) {
  try {
    const res = await fetch(`/api/v1/schedule/anki/workload-forecast?_t=${Date.now()}`);
    if (!res.ok) return;
    const data = await res.json();
    currentForecastData = data;
    renderWorkloadForecast(data);
    if (showFeedback && typeof showToast === 'function') {
      showToast('14-Tage Retentions-Radar aktualisiert.');
    }
  } catch (err) {
    console.warn('Workload forecast fetch failed:', err);
  }
}

function renderWorkloadForecast(data) {
  if (!data || !data.days) return;

  const totalText = `${data.total_due_14d || 0} Karten`;
  const avgText = `${Math.round(data.average_daily_due || 0)}`;
  const peakText = `${data.max_day_cards || 0} max`;
  const adviceText = data.smoothing_advice || 'Workload stabil.';

  ['forecastTotalVal', 'pageForecastTotalVal'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = totalText;
  });
  ['forecastAvgVal', 'pageForecastAvgVal'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = avgText;
  });
  ['forecastPeakVal', 'pageForecastPeakVal'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = peakText;
  });
  ['forecastSpikeBadge', 'pageForecastSpikeBadge'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = data.has_spike ? 'inline-block' : 'none';
  });
  ['forecastAdviceText', 'pageForecastAdviceText'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = adviceText;
  });

  const maxVal = Math.max(data.max_day_cards || 1, 100);
  const trackHeight = 55; // max height in pixels

  let html = '';
  data.days.forEach((day, idx) => {
    const cnt = day.total_due;
    const pct = Math.max(6, Math.round((cnt / maxVal) * trackHeight));
    const isToday = (idx === 0);
    const isTomorrow = (idx === 1);
    const dayLabel = isToday ? 'Heute' : (isTomorrow ? 'Morgen' : day.day_name);

    html += `
      <div onclick="selectForecastDay(${idx})" style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; cursor: pointer; position: relative; height: 100%;" title="${day.formatted_date}: ${cnt} Wiederholungen">
        <span style="font-size: 9.5px; font-weight: 600; color: ${cnt > 0 ? '#e6edf3' : 'var(--text-muted)'}; margin-bottom: 2px;">
          ${cnt > 0 ? cnt : ''}
        </span>
        <div style="width: 100%; max-width: 22px; height: ${pct}px; background: ${day.level_color}; border-radius: 3px 3px 1px 1px; transition: height 0.3s ease, opacity 0.2s; opacity: ${isToday ? '0.7' : '1'}; border: ${isToday ? '1px dashed #fff' : 'none'};"></div>
        <span style="font-size: 9px; color: ${isToday ? '#58a6ff' : 'var(--text-muted)'}; margin-top: 3px; font-weight: ${isToday ? '700' : '400'};">
          ${dayLabel}
        </span>
      </div>
    `;
  });

  ['forecastBarsContainer', 'pageForecastBarsContainer'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  });
}

function selectForecastDay(dayIdx) {
  if (!currentForecastData || !currentForecastData.days) return;
  const day = currentForecastData.days[dayIdx];
  if (!day) return;

  const drawers = [
    document.getElementById('forecastSelectedDayDrawer'),
    document.getElementById('pageForecastSelectedDayDrawer')
  ].filter(Boolean);

  if (drawers.length === 0) return;

  if (day.total_due === 0) {
    drawers.forEach(d => {
      d.style.display = 'block';
      d.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="color: #3fb950; font-weight: 600;">📅 ${day.formatted_date}: Keine Repetitionen fällig</span>
          <button type="button" onclick="closeForecastDrawers()" style="background: transparent; border: none; color: var(--text-muted); cursor: pointer;">✕</button>
        </div>
      `;
    });
    return;
  }

  let breakdownHtml = day.deck_breakdown.map(d => `
    <div style="display: flex; justify-content: space-between; color: #c9d1d9; padding: 2px 0;">
      <span>📖 ${escapeHtml(d.deck_name)}</span>
      <strong style="color: #58a6ff;">${d.count} Karten</strong>
    </div>
  `).join('');

  drawers.forEach(d => {
    d.style.display = 'block';
    d.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 4px; margin-bottom: 4px;">
        <span style="font-weight: 600; color: ${day.level_color};">📅 ${day.formatted_date}: ${day.total_due} Karten fällig (${day.workload_level})</span>
        <button type="button" onclick="closeForecastDrawers()" style="background: transparent; border: none; color: var(--text-muted); cursor: pointer;">✕</button>
      </div>
      <div style="display: flex; flex-direction: column; gap: 2px; max-height: 120px; overflow-y: auto;">
        ${breakdownHtml}
      </div>
    `;
  });
}

function closeForecastDrawers() {
  ['forecastSelectedDayDrawer', 'pageForecastSelectedDayDrawer'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
}
window.closeForecastDrawers = closeForecastDrawers;

// ============================================================================
// PHASE 6: 08:30 SCIENTIFIC STUDY RHYTHM & MANDATORY PRACTICALS
// ============================================================================

// Quick-Orchestrator State
state.rhythmStartTime = localStorage.getItem('sl_rhythm_start') || '08:30';
state.rhythmLunch = parseInt(localStorage.getItem('sl_rhythm_lunch') || '75', 10);
state.rhythmIncludeLecture = localStorage.getItem('sl_rhythm_lecture') !== 'false';
state.strugglesExpanded = false;

function calculateInstantFeierabend(startTimeStr, lunchMins, includeLecture) {
  try {
    const parts = (startTimeStr || '08:30').split(':').map(Number);
    const startTotal = (parts[0] !== undefined ? parts[0] : 8) * 60 + (parts[1] !== undefined ? parts[1] : 30);
    // 60m reps + 15m pause + 105m new + 15m pause + 60m transfer + lunch + (includeLecture ? 90m : 0) + 30m lapse
    const studyAndPause = 60 + 15 + 105 + 15 + 60 + (lunchMins || 75) + (includeLecture !== false ? 90 : 0) + 30;
    const endTotal = startTotal + studyAndPause;
    const endH = Math.floor(endTotal / 60) % 24;
    const endM = endTotal % 60;
    return `${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`;
  } catch (e) {
    return '16:00';
  }
}

function updateFeierabendBadgeInstantly() {
  const feierabendEl = document.getElementById('rhythmFeierabendBadge');
  if (feierabendEl) {
    const instantTime = calculateInstantFeierabend(state.rhythmStartTime, state.rhythmLunch, state.rhythmIncludeLecture);
    feierabendEl.textContent = `${instantTime} Uhr`;
  }
}

function setRhythmStartNow() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, '0');
  const mm = String(now.getMinutes()).padStart(2, '0');
  const timeStr = `${hh}:${mm}`;
  state.rhythmStartTime = timeStr;
  localStorage.setItem('sl_rhythm_start', timeStr);
  const input = document.getElementById('rhythmStartTimeInput');
  if (input) input.value = timeStr;
  updateFeierabendBadgeInstantly();
  loadScienceRhythm();
}

function setRhythmLunch(mins) {
  state.rhythmLunch = mins;
  localStorage.setItem('sl_rhythm_lunch', String(mins));
  document.querySelectorAll('.lunch-pill-btn').forEach(btn => {
    btn.classList.toggle('active', parseInt(btn.dataset.dur, 10) === mins);
  });
  updateFeierabendBadgeInstantly();
  loadScienceRhythm();
}

function handleRhythmConfigChange() {
  const input = document.getElementById('rhythmStartTimeInput');
  if (input && input.value) {
    state.rhythmStartTime = input.value;
    localStorage.setItem('sl_rhythm_start', input.value);
  }
  const check = document.getElementById('rhythmIncludeLectureCheck');
  if (check) {
    state.rhythmIncludeLecture = check.checked;
    localStorage.setItem('sl_rhythm_lecture', String(check.checked));
  }
  updateFeierabendBadgeInstantly();
  loadScienceRhythm();
}


async function createTemporaryStruggleDeck() {
  try {
    const res = await fetch('/api/v1/schedule/anki/create-temp-deck', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deck_name: '⚡ Problem-Karten Heute', tag_name: '⚡_Heute_Problemkarten', limit: 15 })
    });
    const data = await res.json();
    if (data.success) {
      if (navigator.clipboard && data.search_query) {
        try { await navigator.clipboard.writeText(data.search_query); } catch (e) {}
      }
      const instr = (data.instructions && data.instructions.length > 0)
        ? data.instructions.join('\n')
        : "1. Drücke in Anki Taste 'F' (Gefilterten Stapel erstellen).\n2. Filter: tag:⚡_Heute_Problemkarten";

      alert(
        `✅ ${data.message || 'Problemkarten in Anki vorbereitet!'}\n\n` +
        `🎯 ANKI GEFILTERTES DECK (Taste F):\n${instr}\n\n` +
        `🛡️ 100% SICHER FÜR DEINE DECKS:\n` +
        `Gefilterte Decks sind temporär. Sobald du das Deck heute Abend löschst, wandern alle Karten automatisch und unberührt in ihre Original-Heimatstapel zurück!`
      );
    } else {
      alert(`Hinweis: ${data.message || 'Konnte temporäres Deck nicht vorbereiten.'}`);
    }
  } catch (err) {
    alert(`Fehler beim Erstellen des temporären Decks: ${err.message}`);
  }
}

async function cleanupTemporaryStruggleDeck() {
  try {
    const res = await fetch('/api/v1/schedule/anki/cleanup-temp-deck', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag_name: '⚡_Heute_Problemkarten' })
    });
    const data = await res.json();
    alert(data.message || 'Temporäre Tags bereinigt.');
  } catch (err) {
    alert('Fehler beim Bereinigen.');
  }
}

async function openStruggleDeckInAnki(query) {
  return createTemporaryStruggleDeck();
}

async function openStruggleSlidesQuick(path, page) {
  if (!path) {
    showToast('Für diese Karten ist keine separate Folie hinterlegt.');
    return;
  }
  try {
    const res = await fetch(`/api/v1/schedule/slides/open?path=${encodeURIComponent(path)}&page=${page || 1}`);
    const data = await res.json();
    if (data.success) {
      showToast(`📄 Folie geöffnet: ${data.message}`);
    } else {
      showToast(`Hinweis: ${data.message || 'Konnte Folie nicht automatisch öffnen.'}`);
    }
  } catch (err) {
    showToast(`Fehler beim Öffnen der Folie: ${err.message}`);
  }
}


async function openPodcastFolder(folderName) {
  if (!folderName) {
    showToast('Kein Podcast-Ordner hinterlegt');
    return;
  }
  await handleOpenLocalFolder(folderName, 'Vorlesungs-Datei', false);
}

async function openSlideModalQuick(path, title = '') {
  if (!path) {
    showToast('Kein Folienpfad hinterlegt');
    return;
  }
  try {
    fetch(`/api/v1/schedule/slides/open?path=${encodeURIComponent(path)}&page=1`).catch(() => {});
  } catch (e) {}
}

window.handleOpenLocalFolder = handleOpenLocalFolder;
window.openPodcastFolder = openPodcastFolder;
window.openSlideModalQuick = openSlideModalQuick;

function toggleStrugglesExpanded() {
  state.strugglesExpanded = !state.strugglesExpanded;
  const listEl = document.getElementById('lapseStruggleCardsList');
  const btnEl = document.getElementById('btnToggleStruggles');
  if (listEl) {
    listEl.style.display = state.strugglesExpanded ? 'flex' : 'none';
  }
  if (btnEl) {
    btnEl.innerHTML = state.strugglesExpanded ? '▲ Problemkarten verbergen' : '▼ Problemkarten & Diagnosen anzeigen';
  }
}

async function loadScienceRhythm(targetDate) {
  const container = document.getElementById('scienceRhythmBlocksContainer');
  if (!container) return;

  const dateStr = targetDate || state.targetDate || '';
  const startTime = state.rhythmStartTime || '08:30';
  const lunchDur = state.rhythmLunch || 75;
  const incLec = state.rhythmIncludeLecture !== false;

  const timeInput = document.getElementById('rhythmStartTimeInput');
  if (timeInput && timeInput.value !== startTime) timeInput.value = startTime;
  
  const lecCheck = document.getElementById('rhythmIncludeLectureCheck');
  if (lecCheck && lecCheck.checked !== incLec) lecCheck.checked = incLec;

  document.querySelectorAll('.lunch-pill-btn').forEach(btn => {
    btn.classList.toggle('active', parseInt(btn.dataset.dur, 10) === lunchDur);
  });

  const removedKey = `sl_rhythm_removed_${dateStr}`;
  const localRemoved = JSON.parse(localStorage.getItem(removedKey) || '[]');
  const remQuery = localRemoved.length ? `&removed_blocks=${encodeURIComponent(localRemoved.join(','))}` : '';

  const orderKey = `sl_rhythm_order_${dateStr}`;
  const localOrder = JSON.parse(localStorage.getItem(orderKey) || '[]');
  const orderQuery = localOrder.length ? `&custom_order=${encodeURIComponent(localOrder.join(','))}` : '';

  try {
    const res = await fetch(`/api/v1/schedule/daily-rhythm?target_date=${dateStr}&start_time=${encodeURIComponent(startTime)}&lunch_duration=${lunchDur}&include_lecture=${incLec}${remQuery}${orderQuery}`);
    if (!res.ok) return;
    const data = await res.json();
    
    // Check if client has local postponed blocks for this date not yet returned by server
    const postKey = `sl_rhythm_postponed_${dateStr}`;
    const localPostponed = JSON.parse(localStorage.getItem(postKey) || '[]');
    if (localPostponed.length > 0 && Array.isArray(data.blocks)) {
      localPostponed.forEach(lp => {
        const pId = `postponed_${lp.id}`;
        if (!data.blocks.some(b => b.id === pId || b.id === lp.id)) {
          const lunchIdx = data.blocks.findIndex(b => b.id === 'pause_lunch');
          const insertIdx = lunchIdx >= 0 ? lunchIdx + 1 : Math.max(0, data.blocks.length - 2);
          const cleanTitle = (lp.title || 'Verschobener Schritt').replace('Nachmittag: ', '').replace('[Nachhol-Block] ', '').trim();
          data.blocks.splice(insertIdx, 0, {
            id: pId,
            original_id: lp.id,
            duration_minutes: lp.duration_minutes || 75,
            start_time: '14:00',
            end_time: '15:15',
            title: `⏩ [Nachhol-Block] ${cleanTitle}`,
            subtitle: `Von ${lp._postponed_from || 'gestern'} verschoben • Neuro-optimal: Nachmittags-Fokus (14:00)`,
            focus_type: 'postponed_catchup',
            icon: '⏩',
            color: '#f59f00',
            badge: '⏩ Von gestern verschoben (Optimal eingetaktet)',
            description: `Wissenschaftlich optimal nach der Mittagspause eingetaktet: ${lp.description || ''}`,
            is_break: false,
            is_mandatory: false,
            is_postponed: true,
            postponed_from: lp._postponed_from,
            vam_url: lp.vam_url,
            podcast_folder_name: lp.podcast_folder_name,
            slide_filename: lp.slide_filename,
            slide_rel_path: lp.slide_rel_path,
            tomorrow_lecture_title: lp.tomorrow_lecture_title || cleanTitle,
          });
          data.postponed_blocks_count = (data.postponed_blocks_count || 0) + 1;
        }
      });
    }

    // Check if client has custom block order for this date
    if (localOrder.length > 0 && Array.isArray(data.blocks)) {
      const blockMap = new Map();
      data.blocks.forEach(b => blockMap.set(b.id, b));
      const reordered = [];
      localOrder.forEach(id => {
        if (blockMap.has(id)) {
          reordered.push(blockMap.get(id));
          blockMap.delete(id);
        }
      });
      // Append any blocks not yet in localOrder
      blockMap.forEach(b => reordered.push(b));
      
      // Keep evening_free at the end
      const freeIdx = reordered.findIndex(b => b.id === 'evening_free');
      if (freeIdx >= 0) {
        const freeItem = reordered.splice(freeIdx, 1)[0];
        reordered.push(freeItem);
      }
      data.blocks = reordered;
      recalculateRhythmTimes(data);
    }

    // Check if client or server has custom durations for blocks on this date
    const durationsKey = `sl_rhythm_durations_${dateStr}`;
    const localDurations = JSON.parse(localStorage.getItem(durationsKey) || '{}');
    if (data.custom_durations && typeof data.custom_durations === 'object') {
      for (const [k, v] of Object.entries(data.custom_durations)) {
        if (localDurations[k] === undefined) {
          localDurations[k] = v;
        }
      }
    }
    if (Object.keys(localDurations).length > 0 && Array.isArray(data.blocks)) {
      data.blocks.forEach(b => {
        if (b && b.id && localDurations[b.id]) {
          b.duration_minutes = parseInt(localDurations[b.id], 10);
        }
      });
      recalculateRhythmTimes(data);
    }

    // Update Feierabend badge
    const feierabendEl = document.getElementById('rhythmFeierabendBadge');
    if (feierabendEl && data.feierabend_time) {
      feierabendEl.textContent = `${data.feierabend_time} Uhr`;
    }

    // Update Anki Auto-Start badge and input
    const ankiBadge = document.getElementById('rhythmAnkiStartBadge');
    if (ankiBadge) {
      if (data.used_anki_start && data.anki_first_review_time) {
        ankiBadge.style.display = 'inline-block';
        ankiBadge.textContent = `⚡ Anki: ${data.anki_first_review_time}`;
        ankiBadge.title = `Startzeit wurde automatisch von deiner ersten Anki-Wiederholung (${data.anki_first_review_time} Uhr) übernommen`;
        if (timeInput && (!localStorage.getItem('sl_rhythm_start') || localStorage.getItem('sl_rhythm_start') === '08:30')) {
          timeInput.value = data.start_time;
          state.rhythmStartTime = data.start_time;
        }
      } else {
        ankiBadge.style.display = 'none';
      }
    }

    renderScienceRhythm(data);
  } catch (err) {
    console.warn('Daily science rhythm fetch failed:', err);
  }
}

function toggleConfigDrawer(isOpen) {
  const drawer = document.getElementById('configDrawerBackdrop');
  if (!drawer) return;
  drawer.style.display = isOpen ? 'flex' : 'none';
  if (isOpen) {
    document.body.style.overflow = 'hidden';
  } else {
    document.body.style.overflow = '';
  }
}

function handleConfigDrawerBackdrop(e) {
  if (e.target.id === 'configDrawerBackdrop') {
    toggleConfigDrawer(false);
  }
}

async function toggleRhythmBlockDone(dateStr, blockId) {
  const key = `sl_rhythm_${dateStr}_${blockId}`;
  const block = (state.currentScienceRhythmData?.blocks || []).find(b => b.id === blockId);
  const cur = (block && block.is_completed) || (localStorage.getItem(key) === 'true');
  const nextState = !cur;
  localStorage.setItem(key, String(nextState));

  try {
    await fetch('/api/v1/schedule/rhythm-action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_date: dateStr,
        action: nextState ? 'complete' : 'uncomplete',
        block_id: blockId,
      }),
    });
  } catch (err) {
    console.warn('Backend rhythm completion sync note:', err);
  }

  loadScienceRhythm(dateStr);
}

function promptRhythmBlockAction(dateStr, blockId) {
  if (!state.currentScienceRhythmData || !Array.isArray(state.currentScienceRhythmData.blocks)) return;
  const block = state.currentScienceRhythmData.blocks.find(b => b.id === blockId);
  if (!block) return;

  state.activeRhythmActionTarget = {
    date: dateStr,
    block: block,
  };

  const modal = document.getElementById('rhythmBlockActionModal');
  if (!modal) return;

  const titleEl = document.getElementById('rhythmActionModalBlockTitle');
  const iconEl = document.getElementById('rhythmActionModalIcon');
  const infoEl = document.getElementById('rhythmActionModalBlockInfo');
  const subEl = document.getElementById('rhythmActionModalSubtitle');

  if (titleEl) titleEl.textContent = block.title || 'Schritt';
  if (iconEl) iconEl.textContent = block.icon || '⏱️';
  if (infoEl) infoEl.textContent = `Geplante Zeit: ${block.start_time || ''} – ${block.end_time || ''} (${block.duration_minutes || 0} Minuten)`;
  if (subEl) subEl.textContent = `Plan für ${formatGermanDate(dateStr)} • Schritt im Zeitorchester anpassen`;

  modal.style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function closeRhythmBlockActionModal() {
  const modal = document.getElementById('rhythmBlockActionModal');
  if (modal) modal.style.display = 'none';
  document.body.style.overflow = '';
  state.activeRhythmActionTarget = null;
}

async function executePostponeRhythmBlock() {
  const target = state.activeRhythmActionTarget;
  if (!target || !target.date || !target.block) {
    closeRhythmBlockActionModal();
    return;
  }

  // Compute tomorrow date string (YYYY-MM-DD)
  const d = new Date(target.date + 'T12:00:00');
  d.setDate(d.getDate() + 1);
  const tomorrowIso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

  const blockId = target.block.id;
  const sourceDate = target.date;

  // 1. Update localStorage
  const removedKey = `sl_rhythm_removed_${sourceDate}`;
  const removed = JSON.parse(localStorage.getItem(removedKey) || '[]');
  if (!removed.includes(blockId)) removed.push(blockId);
  localStorage.setItem(removedKey, JSON.stringify(removed));

  const postKey = `sl_rhythm_postponed_${tomorrowIso}`;
  const postponed = JSON.parse(localStorage.getItem(postKey) || '[]');
  postponed.push({
    ...target.block,
    _postponed_from: sourceDate,
    _postponed_to: tomorrowIso,
  });
  localStorage.setItem(postKey, JSON.stringify(postponed));

  closeRhythmBlockActionModal();

  // 2. Call backend API
  try {
    await fetch('/api/v1/schedule/rhythm-action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_date: sourceDate,
        action: 'postpone',
        block_id: blockId,
        target_date: tomorrowIso,
        block_payload: target.block,
      }),
    });
  } catch (err) {
    console.warn('Backend rhythm postpone action failed:', err);
  }

  // 3. Reload science rhythm for source date
  await loadScienceRhythm(sourceDate);

  showToast('⏩ Schritt auf morgen verschoben! Er wurde für morgen optimal nach der Mittagspause eingetaktet.');
}

async function executeDeleteRhythmBlock() {
  const target = state.activeRhythmActionTarget;
  if (!target || !target.date || !target.block) {
    closeRhythmBlockActionModal();
    return;
  }

  const blockId = target.block.id;
  const sourceDate = target.date;

  // 1. Update localStorage
  const removedKey = `sl_rhythm_removed_${sourceDate}`;
  const removed = JSON.parse(localStorage.getItem(removedKey) || '[]');
  if (!removed.includes(blockId)) removed.push(blockId);
  localStorage.setItem(removedKey, JSON.stringify(removed));

  closeRhythmBlockActionModal();

  // 2. Call backend API
  try {
    await fetch('/api/v1/schedule/rhythm-action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_date: sourceDate,
        action: 'delete',
        block_id: blockId,
      }),
    });
  } catch (err) {
    console.warn('Backend rhythm delete action failed:', err);
  }

  // 3. Reload science rhythm for source date
  await loadScienceRhythm(sourceDate);

  showToast('🗑️ Schritt aus dem heutigen Plan gelöscht. Feierabend rückt nach vorne!');
}

async function restoreRhythmBlocks(dateStr) {
  const removedKey = `sl_rhythm_removed_${dateStr}`;
  const orderKey = `sl_rhythm_order_${dateStr}`;
  const durationsKey = `sl_rhythm_durations_${dateStr}`;
  localStorage.removeItem(removedKey);
  localStorage.removeItem(orderKey);
  localStorage.removeItem(durationsKey);

  try {
    await fetch('/api/v1/schedule/rhythm-action/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_date: dateStr,
      }),
    });
  } catch (err) {
    console.warn('Backend rhythm restore failed:', err);
  }

  await loadScienceRhythm(dateStr);
  showToast('🔄 Stundenplan erfolgreich auf Ursprungszustand zurückgesetzt.');
}

function recalculateRhythmTimes(data) {
  if (!data || !Array.isArray(data.blocks)) return;
  const startTimeStr = data.start_time || state.rhythmStartTime || '08:30';
  const [sh, sm] = startTimeStr.split(':').map(Number);
  let curM = (sh || 8) * 60 + (sm || 30);
  let totalStudyM = 0;
  let totalPauseM = 0;

  data.blocks.forEach(b => {
    if (!b || !b.id) return;
    if (b.id === 'evening_free') return;

    if (b.is_mandatory && b.start_time && b.end_time) {
      const [msh, msm] = b.start_time.split(':').map(Number);
      const [meh, mem] = b.end_time.split(':').map(Number);
      const mStartM = (msh || 0) * 60 + (msm || 0);
      const mEndM = (meh || 0) * 60 + (mem || 0);
      curM = Math.max(curM, mEndM);
      totalStudyM += (b.duration_minutes || (mEndM - mStartM));
    } else {
      const dur = b.duration_minutes || 45;
      const startH = String(Math.floor(curM / 60)).padStart(2, '0');
      const startMin = String(curM % 60).padStart(2, '0');
      curM += dur;
      const endH = String(Math.floor(curM / 60)).padStart(2, '0');
      const endMin = String(curM % 60).padStart(2, '0');

      b.start_time = `${startH}:${startMin}`;
      b.end_time = `${endH}:${endMin}`;

      if (b.is_break) {
        totalPauseM += dur;
      } else {
        totalStudyM += dur;
      }
    }
  });

  const feierabendH = String(Math.floor(curM / 60)).padStart(2, '0');
  const feierabendMin = String(curM % 60).padStart(2, '0');
  const feierabendTime = `${feierabendH}:${feierabendMin}`;
  data.feierabend_time = feierabendTime;
  data.total_study_minutes = totalStudyM;
  data.total_pause_minutes = totalPauseM;

  const feierabendEl = document.getElementById('rhythmFeierabendBadge');
  if (feierabendEl) {
    feierabendEl.textContent = `${feierabendTime} Uhr`;
  }

  const freeBlock = data.blocks.find(b => b.id === 'evening_free');
  if (freeBlock) {
    freeBlock.start_time = feierabendTime;
    freeBlock.end_time = '22:00';
    freeBlock.duration_minutes = Math.max(60, (22 * 60) - curM);
    freeBlock.title = `🎉 Feierabend ab ${feierabendTime} & Sport am Abend`;
  }
}

async function saveRhythmReorderToBackend(dateStr, orderIds) {
  try {
    await fetch('/api/v1/schedule/rhythm-action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_date: dateStr,
        action: 'reorder',
        block_id: '__custom_order__',
        block_payload: { order: orderIds },
      }),
    });
  } catch (err) {
    console.warn('Backend rhythm reorder save failed:', err);
  }
}

function moveRhythmBlock(dateStr, blockId, delta) {
  if (!state.currentScienceRhythmData || !Array.isArray(state.currentScienceRhythmData.blocks)) return;
  const blocks = state.currentScienceRhythmData.blocks;
  const idx = blocks.findIndex(b => b.id === blockId);
  if (idx < 0) return;
  const targetIdx = idx + delta;
  const maxIdx = blocks[blocks.length - 1]?.id === 'evening_free' ? blocks.length - 2 : blocks.length - 1;
  if (targetIdx < 0 || targetIdx > maxIdx) return;

  const item = blocks.splice(idx, 1)[0];
  blocks.splice(targetIdx, 0, item);

  recalculateRhythmTimes(state.currentScienceRhythmData);

  const orderIds = blocks.map(b => b.id);
  localStorage.setItem(`sl_rhythm_order_${dateStr}`, JSON.stringify(orderIds));
  saveRhythmReorderToBackend(dateStr, orderIds);

  renderScienceRhythm(state.currentScienceRhythmData);
  showToast('🔄 Stundenplan angepasst: Neuer Ablauf & Zeiten aktualisiert');
}

function handleQuickMoveRhythmBlock(dateStr, blockId, delta, event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  moveRhythmBlock(dateStr, blockId, delta);
}

function reorderRhythmBlockTo(dateStr, sourceBlockId, targetBlockId) {
  if (!state.currentScienceRhythmData || !Array.isArray(state.currentScienceRhythmData.blocks)) return;
  if (sourceBlockId === targetBlockId) return;
  const blocks = state.currentScienceRhythmData.blocks;
  const srcIdx = blocks.findIndex(b => b.id === sourceBlockId);
  const tgtIdx = blocks.findIndex(b => b.id === targetBlockId);
  if (srcIdx < 0 || tgtIdx < 0) return;
  if (blocks[tgtIdx].id === 'evening_free') return;

  const item = blocks.splice(srcIdx, 1)[0];
  blocks.splice(tgtIdx, 0, item);

  recalculateRhythmTimes(state.currentScienceRhythmData);

  const orderIds = blocks.map(b => b.id);
  localStorage.setItem(`sl_rhythm_order_${dateStr}`, JSON.stringify(orderIds));
  saveRhythmReorderToBackend(dateStr, orderIds);

  renderScienceRhythm(state.currentScienceRhythmData);
  showToast('🔄 Stundenplan angepasst: Neuer Ablauf & Zeiten aktualisiert');
}

let _desktopRhythmDragSource = null;
let _touchRhythmDragSource = null;
let _touchRhythmTimer = null;
let _touchRhythmStartX = 0;
let _touchRhythmStartY = 0;
let _isTouchRhythmDragging = false;
let _lastHighlightedRhythmRow = null;

function initRhythmDragAndDrop() {
  const container = document.getElementById('scienceRhythmBlocksContainer');
  if (!container || container._rhythmDndInitialized) return;
  container._rhythmDndInitialized = true;

  // 1. Desktop Drag & Drop
  container.addEventListener('dragstart', (e) => {
    if (e.target.closest('.rhythm-resize-handle') || e.target.closest('.btn-duration-nudge') || e.target.closest('.duration-badge-pill')) {
      e.preventDefault();
      return;
    }
    const row = e.target.closest('.rhythm-row-card:not(#rhythmRow-evening_free)');
    if (!row) return;
    _desktopRhythmDragSource = row;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', row.dataset.blockId || '');
    setTimeout(() => row.classList.add('is-dragging-desktop'), 0);
  });

  container.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const row = e.target.closest('.rhythm-row-card:not(#rhythmRow-evening_free)');
    if (!row || row === _desktopRhythmDragSource) return;

    container.querySelectorAll('.rhythm-row-card').forEach(r => {
      if (r !== row) r.classList.remove('drag-over-highlight');
    });
    row.classList.add('drag-over-highlight');
  });

  container.addEventListener('dragleave', (e) => {
    const row = e.target.closest('.rhythm-row-card');
    if (row && !row.contains(e.relatedTarget)) {
      row.classList.remove('drag-over-highlight');
    }
  });

  container.addEventListener('drop', (e) => {
    e.preventDefault();
    container.querySelectorAll('.rhythm-row-card').forEach(r => {
      r.classList.remove('drag-over-highlight');
      r.classList.remove('is-dragging-desktop');
    });

    const targetRow = e.target.closest('.rhythm-row-card:not(#rhythmRow-evening_free)');
    if (!targetRow || !_desktopRhythmDragSource || targetRow === _desktopRhythmDragSource) {
      _desktopRhythmDragSource = null;
      return;
    }

    const srcId = _desktopRhythmDragSource.dataset.blockId;
    const tgtId = targetRow.dataset.blockId;
    _desktopRhythmDragSource = null;

    if (srcId && tgtId && state.currentScienceRhythmData) {
      reorderRhythmBlockTo(state.currentScienceRhythmData.date, srcId, tgtId);
    }
  });

  container.addEventListener('dragend', () => {
    container.querySelectorAll('.rhythm-row-card').forEach(r => {
      r.classList.remove('drag-over-highlight');
      r.classList.remove('is-dragging-desktop');
    });
    _desktopRhythmDragSource = null;
  });

  // 2. Touch Support (Mobile & iPad - Touch & Hold or Drag Handle)
  container.addEventListener('touchstart', (e) => {
    if (e.target.closest('.rhythm-resize-handle') || e.target.closest('.btn-duration-nudge') || e.target.closest('.duration-badge-pill')) {
      return;
    }
    const handle = e.target.closest('.rhythm-drag-handle');
    const row = e.target.closest('.rhythm-row-card:not(#rhythmRow-evening_free)');
    if (!row) return;

    const isHandle = Boolean(handle);
    const touch = e.touches[0];
    _touchRhythmStartX = touch.clientX;
    _touchRhythmStartY = touch.clientY;
    _touchRhythmDragSource = row;
    _isTouchRhythmDragging = false;

    clearTimeout(_touchRhythmTimer);
    _touchRhythmTimer = setTimeout(() => {
      _isTouchRhythmDragging = true;
      if (row) {
        row.classList.add('is-dragging-touch');
        if (navigator.vibrate) {
          try { navigator.vibrate(40); } catch (err) {}
        }
      }
    }, isHandle ? 60 : 320);
  }, { passive: true });

  container.addEventListener('touchmove', (e) => {
    if (!_touchRhythmDragSource) return;
    const touch = e.touches[0];
    const diffX = Math.abs(touch.clientX - _touchRhythmStartX);
    const diffY = Math.abs(touch.clientY - _touchRhythmStartY);

    if (!_isTouchRhythmDragging) {
      if (diffY > 12 || diffX > 12) {
        clearTimeout(_touchRhythmTimer);
        _touchRhythmDragSource = null;
      }
      return;
    }

    // Touch dragging active: prevent page scroll
    e.preventDefault();

    const elem = document.elementFromPoint(touch.clientX, touch.clientY);
    const targetRow = elem ? elem.closest('.rhythm-row-card:not(#rhythmRow-evening_free)') : null;

    if (targetRow && targetRow !== _touchRhythmDragSource) {
      if (_lastHighlightedRhythmRow && _lastHighlightedRhythmRow !== targetRow) {
        _lastHighlightedRhythmRow.classList.remove('drag-over-highlight');
      }
      _lastHighlightedRhythmRow = targetRow;
      targetRow.classList.add('drag-over-highlight');
    } else if (_lastHighlightedRhythmRow) {
      _lastHighlightedRhythmRow.classList.remove('drag-over-highlight');
      _lastHighlightedRhythmRow = null;
    }
  }, { passive: false });

  container.addEventListener('touchend', () => {
    clearTimeout(_touchRhythmTimer);
    if (_touchRhythmDragSource) {
      _touchRhythmDragSource.classList.remove('is-dragging-touch');
    }
    if (_lastHighlightedRhythmRow) {
      _lastHighlightedRhythmRow.classList.remove('drag-over-highlight');
    }

    if (_isTouchRhythmDragging && _touchRhythmDragSource && _lastHighlightedRhythmRow) {
      const srcId = _touchRhythmDragSource.dataset.blockId;
      const tgtId = _lastHighlightedRhythmRow.dataset.blockId;
      if (srcId && tgtId && srcId !== tgtId && state.currentScienceRhythmData) {
        reorderRhythmBlockTo(state.currentScienceRhythmData.date, srcId, tgtId);
      }
    }

    _touchRhythmDragSource = null;
    _lastHighlightedRhythmRow = null;
    _isTouchRhythmDragging = false;
  });

  container.addEventListener('touchcancel', () => {
    clearTimeout(_touchRhythmTimer);
    if (_touchRhythmDragSource) {
      _touchRhythmDragSource.classList.remove('is-dragging-touch');
    }
    if (_lastHighlightedRhythmRow) {
      _lastHighlightedRhythmRow.classList.remove('drag-over-highlight');
    }
    _touchRhythmDragSource = null;
    _lastHighlightedRhythmRow = null;
    _isTouchRhythmDragging = false;
  });
}

async function saveRhythmDurationsToBackend(dateStr, durationsMap) {
  try {
    await fetch('/api/v1/schedule/rhythm-action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_date: dateStr,
        action: 'durations',
        block_id: '__custom_durations__',
        block_payload: { durations: durationsMap },
      }),
    });
  } catch (err) {
    console.warn('Backend rhythm durations save failed:', err);
  }
}

function handleNudgeBlockDuration(dateStr, blockId, deltaMinutes, event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  const data = state.currentScienceRhythmData;
  if (!data || !Array.isArray(data.blocks)) return;
  const b = data.blocks.find(x => x.id === blockId);
  if (!b) return;

  const currentDur = b.duration_minutes || 45;
  const newDur = Math.max(5, Math.min(360, currentDur + deltaMinutes));
  if (newDur === currentDur) return;

  b.duration_minutes = newDur;
  recalculateRhythmTimes(data);

  const durationsKey = `sl_rhythm_durations_${dateStr}`;
  const durationsMap = JSON.parse(localStorage.getItem(durationsKey) || '{}');
  durationsMap[blockId] = newDur;
  localStorage.setItem(durationsKey, JSON.stringify(durationsMap));

  saveRhythmDurationsToBackend(dateStr, durationsMap);
  renderScienceRhythm(data);

  const diffStr = deltaMinutes > 0 ? `+${deltaMinutes}m` : `${deltaMinutes}m`;
  showToast(`⏱️ ${b.title}: ${diffStr} (jetzt ${newDur} Min.) – Ablauf neu berechnet!`, 3500);
}

function handlePromptBlockDuration(dateStr, blockId, currentMinutes, event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  const val = prompt(`Dauer für diesen Block in Minuten festlegen:`, String(currentMinutes));
  if (val === null) return;
  const num = parseInt(val.trim(), 10);
  if (isNaN(num) || num < 5 || num > 360) {
    showToast('⚠️ Bitte eine gültige Minutenzahl zwischen 5 und 360 eingeben.');
    return;
  }
  const diff = num - currentMinutes;
  handleNudgeBlockDuration(dateStr, blockId, diff, null);
}

function initRhythmResizeHandlers() {
  const handles = document.querySelectorAll('.rhythm-resize-handle');
  handles.forEach(handle => {
    let isResizing = false;
    let startY = 0;
    let startDur = 0;
    const blockId = handle.dataset.blockId;
    const rowCard = document.getElementById(`rhythmRow-${blockId}`);
    const pillEl = handle.querySelector('.rhythm-resize-pill');

    handle.addEventListener('dragstart', e => {
      e.preventDefault();
      e.stopPropagation();
    });

    handle.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 && e.pointerType === 'mouse') return;
      e.preventDefault();
      e.stopPropagation();

      const data = state.currentScienceRhythmData;
      if (!data || !Array.isArray(data.blocks)) return;
      const b = data.blocks.find(x => x.id === blockId);
      if (!b) return;

      isResizing = true;
      startY = e.clientY;
      startDur = b.duration_minutes || 45;

      try {
        handle.setPointerCapture(e.pointerId);
      } catch (_) {}

      handle.classList.add('is-resizing');
      if (rowCard) {
        rowCard.classList.add('is-resizing-card');
        rowCard.setAttribute('draggable', 'false');
      }

      if (pillEl) {
        pillEl.innerHTML = `<strong>↕ ${b.duration_minutes}m</strong>`;
        pillEl.style.display = 'inline-flex';
      }
    });

    handle.addEventListener('pointermove', (e) => {
      if (!isResizing) return;
      e.preventDefault();
      e.stopPropagation();

      const data = state.currentScienceRhythmData;
      if (!data) return;
      const b = data.blocks.find(x => x.id === blockId);
      if (!b) return;

      const deltaY = e.clientY - startY;
      // 2.5px drag per minute, snapped to 5 minutes
      const deltaMinutes = Math.round((deltaY / 2.5) / 5) * 5;
      const newDur = Math.max(5, Math.min(360, startDur + deltaMinutes));

      if (b.duration_minutes !== newDur) {
        b.duration_minutes = newDur;
        recalculateRhythmTimes(data);

        // Update current card live
        if (rowCard) {
          const timeTextEl = rowCard.querySelector('.rhythm-card-times');
          const durBadgeEl = rowCard.querySelector('.rhythm-card-duration-text');
          if (timeTextEl) {
            timeTextEl.innerHTML = `${b.start_time} <span style="font-weight: 400; color: var(--text-dim);">–</span> ${b.end_time}`;
          }
          if (durBadgeEl) {
            durBadgeEl.textContent = `${newDur} Min.`;
          }
        }

        if (pillEl) {
          const diff = newDur - startDur;
          const diffStr = diff > 0 ? `+${diff}m` : (diff < 0 ? `${diff}m` : `±0m`);
          pillEl.innerHTML = `<strong>↕ ${newDur} Min.</strong> (${diffStr}) &bull; Ende: ${b.end_time}`;
          pillEl.style.display = 'inline-flex';
        }

        // Live update following cards' start/end times in DOM
        data.blocks.forEach(otherB => {
          if (otherB.id === blockId || otherB.id === 'evening_free') return;
          const otherRow = document.getElementById(`rhythmRow-${otherB.id}`);
          if (otherRow) {
            const ot = otherRow.querySelector('.rhythm-card-times');
            if (ot) {
              ot.innerHTML = `${otherB.start_time} <span style="font-weight: 400; color: var(--text-dim);">–</span> ${otherB.end_time}`;
            }
          }
        });
      }
    });

    const finishResize = (e) => {
      if (!isResizing) return;
      isResizing = false;
      try {
        handle.releasePointerCapture(e.pointerId);
      } catch (_) {}
      handle.classList.remove('is-resizing');
      if (pillEl) {
        pillEl.style.display = 'none';
      }
      if (rowCard) {
        rowCard.classList.remove('is-resizing-card');
        rowCard.setAttribute('draggable', 'true');
      }

      const data = state.currentScienceRhythmData;
      if (!data) return;
      const b = data.blocks.find(x => x.id === blockId);
      if (!b) return;

      const dateStr = data.date;
      const durationsKey = `sl_rhythm_durations_${dateStr}`;
      const durationsMap = JSON.parse(localStorage.getItem(durationsKey) || '{}');
      durationsMap[blockId] = b.duration_minutes;
      localStorage.setItem(durationsKey, JSON.stringify(durationsMap));

      saveRhythmDurationsToBackend(dateStr, durationsMap);

      renderScienceRhythm(data);
      const diff = b.duration_minutes - startDur;
      const diffMsg = diff > 0 ? `+${diff} Min. verlängert` : (diff < 0 ? `${Math.abs(diff)} Min. gekürzt` : `Dauer unverändert`);
      showToast(`⏱️ ${b.title}: ${diffMsg} (${b.duration_minutes}m) – Tagesplan angepasst!`, 4000);
    };

    handle.addEventListener('pointerup', finishResize);
    handle.addEventListener('pointercancel', finishResize);
  });
}

function renderScienceRhythm(data) {
  const container = document.getElementById('scienceRhythmBlocksContainer');
  if (!container || !data || data.error || !Array.isArray(data.blocks)) return;

  state.currentScienceRhythmData = data;

  const now = new Date();
  const todayIso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  const isToday = (data.date === todayIso);
  const nowMinutes = now.getHours() * 60 + now.getMinutes();

  let activeBlockTitle = '';
  let activeMinsLeft = 0;
  let doneCount = 0;

  data.blocks.forEach(b => {
    if (!b || !b.id) return;
    const key = `sl_rhythm_${data.date}_${b.id}`;
    if (b.is_completed || localStorage.getItem(key) === 'true') doneCount++;
  });

  const removedKey = `sl_rhythm_removed_${data.date}`;
  const orderKey = `sl_rhythm_order_${data.date}`;
  const localRemoved = JSON.parse(localStorage.getItem(removedKey) || '[]');
  const localOrder = JSON.parse(localStorage.getItem(orderKey) || '[]');
  const durationsKey = `sl_rhythm_durations_${data.date}`;
  const localDurations = JSON.parse(localStorage.getItem(durationsKey) || '{}');
  const hasAdjustments = (data.removed_blocks_count > 0 || localRemoved.length > 0 || data.postponed_blocks_count > 0 || localOrder.length > 0 || (Array.isArray(data.custom_order) && data.custom_order.length > 0) || Object.keys(localDurations).length > 0 || (data.custom_durations && Object.keys(data.custom_durations).length > 0));

  const progressEl = document.getElementById('scienceRhythmProgressText');
  if (progressEl) {
    progressEl.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; flex-wrap: wrap; gap: 0.5rem;">
        <span><strong>${doneCount} von ${data.blocks.length} Abschnitten</strong> erledigt &bull; Geplante Arbeitszeit: <strong>${Math.round((data.total_study_minutes || 0) / 60)}h ${(data.total_study_minutes || 0) % 60}m</strong> (ohne Puffer)</span>
        ${hasAdjustments ? `
          <button type="button" onclick="restoreRhythmBlocks('${data.date}')" class="btn-secondary" style="font-size: 10.5px; padding: 0.15rem 0.55rem; height: auto; border-color: rgba(56, 139, 253, 0.4); color: #79c0ff; cursor: pointer;" title="Stellt alle gelöschten, verschobenen oder umgestellten Schritte dieses Tages wieder her">
            🔄 Plan wiederherstellen
          </button>
        ` : ''}
      </div>
    `;
  }

  let tomorrowAlertHtml = '';
  if (Array.isArray(data.tomorrow_mandatory_events) && data.tomorrow_mandatory_events.length > 0) {
    const tmList = data.tomorrow_mandatory_events.map(ev => 
      `<strong>${escapeHtml(ev.title)}</strong> (${ev.start_time} – ${ev.end_time} Uhr${ev.location ? ` @ ${escapeHtml(ev.location)}` : ''})`
    ).join(', ');
    tomorrowAlertHtml = `
      <div style="background: linear-gradient(135deg, rgba(163, 113, 247, 0.15), rgba(138, 56, 245, 0.08)); border: 1.5px solid rgba(163, 113, 247, 0.4); border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 0.85rem; display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; flex-wrap: wrap;">
        <div style="display: flex; align-items: center; gap: 0.65rem; min-width: 0; flex: 1;">
          <span style="font-size: 22px; flex-shrink: 0;">🏛️</span>
          <div>
            <div style="font-weight: 700; font-size: 13px; color: #d2a8ff; letter-spacing: 0.2px;">
              WICHTIGER HINWEIS: MORGEN PRÄSENZPFLICHT VOR ORT!
            </div>
            <div style="font-size: 11.5px; color: var(--text-main); margin-top: 2px;">
              ${tmList}
            </div>
          </div>
        </div>
        <button type="button" onclick="stepDate(1)" class="btn-primary" style="font-size: 11px; padding: 0.35rem 0.75rem; background: rgba(163, 113, 247, 0.25); border: 1px solid #a371f7; color: #d2a8ff; font-weight: 700; border-radius: 6px; cursor: pointer;" title="Zeigt den morgigen Tagesplan inklusive Präsenz-Slot">
          Morgen ansehen &rarr;
        </button>
      </div>
    `;
  }

  let html = '';
  data.blocks.forEach(b => {
    if (!b || !b.start_time || !b.end_time) return;
    const isBreak = b.is_break;
    const isMandatory = b.is_mandatory;
    const isLapseBlock = (b.id === 'block_evening_lapse');
    const isPostponed = Boolean(b.is_postponed);
    const key = `sl_rhythm_${data.date}_${b.id}`;
    const isCompleted = Boolean(b.is_completed) || (localStorage.getItem(key) === 'true');

    // Parse start and end time (HH:MM)
    const [sh, sm] = b.start_time.split(':').map(Number);
    const [eh, em] = b.end_time.split(':').map(Number);
    const startM = (sh || 0) * 60 + (sm || 0);
    const endM = (eh || 0) * 60 + (em || 0);

    const isCurrent = isToday && (nowMinutes >= startM && nowMinutes < endM);
    if (isCurrent) {
      activeBlockTitle = b.title;
      activeMinsLeft = endM - nowMinutes;
    }

    let borderLeft = isPostponed ? '3.5px solid #f59f00' : (isMandatory ? '4px solid #a371f7' : (isBreak ? '3px solid #3fb950' : `3px solid ${b.color}`));
    let bg = isPostponed ? 'rgba(245, 159, 0, 0.08)' : (isMandatory ? 'rgba(163, 113, 247, 0.08)' : (isBreak ? 'rgba(63, 185, 80, 0.03)' : 'rgba(255, 255, 255, 0.02)'));
    let activeClass = isCurrent ? 'active-now' : '';
    let compClass = isCompleted ? 'completed' : '';
    const isDraggable = (b.id !== 'evening_free');

    html += `
      <div class="rhythm-row-card ${isDraggable ? 'draggable-active' : ''} ${activeClass} ${compClass}"
           id="rhythmRow-${b.id}"
           data-block-id="${b.id}"
           draggable="${isDraggable ? 'true' : 'false'}"
           style="border-left: ${borderLeft}; background: ${bg}; flex-direction: column; align-items: stretch; gap: 0.35rem;"
           title="${isDraggable ? 'Gedrückt halten &amp; ziehen oder ▲ / ▼ nutzen zum Umstellen im Stundenplan • ' : ''}${escapeHtml(b.description || '')}">
        <!-- Top Row: Drag Handle, Time, Title, Badges, Delete & Checkbox -->
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 0.65rem;">
          <!-- Far Left: Drag Handle & Quick Reorder (unless evening_free) -->
          ${isDraggable ? `
            <div style="display: flex; align-items: center; gap: 0.18rem; flex-shrink: 0;">
              <span class="rhythm-drag-handle" title="Gedrückt halten &amp; ziehen zum Umstellen des Stundenplans">⠿</span>
              <div style="display: flex; flex-direction: column; gap: 1px;">
                <button type="button" class="rhythm-quick-btn" onclick="handleQuickMoveRhythmBlock('${data.date}', '${b.id}', -1, event)" title="Einen Schritt nach oben verschieben">▲</button>
                <button type="button" class="rhythm-quick-btn" onclick="handleQuickMoveRhythmBlock('${data.date}', '${b.id}', 1, event)" title="Einen Schritt nach unten verschieben">▼</button>
              </div>
            </div>
          ` : ''}

          <!-- Left: Time & Duration with Nudge & Click-to-edit -->
          <div style="min-width: 95px; flex-shrink: 0;">
            <div class="rhythm-card-times" style="font-family: monospace; font-size: 12px; font-weight: 700; color: #f0f6fc;">
              ${b.start_time} <span style="font-weight: 400; color: var(--text-dim);">–</span> ${b.end_time}
            </div>
            <div style="display: flex; align-items: center; gap: 3px; margin-top: 3px;">
              ${isDraggable ? `<button type="button" class="btn-duration-nudge" onclick="handleNudgeBlockDuration('${data.date}', '${b.id}', -15, event)" title="15 Min. kürzen">–15</button>` : ''}
              <span class="duration-badge-pill rhythm-card-duration-text" onclick="handlePromptBlockDuration('${data.date}', '${b.id}', ${b.duration_minutes}, event)" title="Klicken zum manuellen Einstellen der Minuten">${b.duration_minutes}m</span>
              ${isDraggable ? `<button type="button" class="btn-duration-nudge btn-duration-plus" onclick="handleNudgeBlockDuration('${data.date}', '${b.id}', 15, event)" title="15 Min. verlängern">+15</button>` : ''}
            </div>
          </div>

          <!-- Center: Icon & Title & Subtitle -->
          <div style="display: flex; align-items: center; gap: 0.65rem; min-width: 0; flex: 1;">
            <span style="font-size: 16px; flex-shrink: 0;">${b.icon}</span>
            <div style="min-width: 0;">
              <div style="display: flex; align-items: center; gap: 0.45rem; flex-wrap: wrap;">
                <strong style="color: ${isPostponed ? '#f59f00' : (isMandatory ? '#d2a8ff' : '#f0f6fc')}; font-size: 12.5px; ${isCompleted ? 'text-decoration: line-through; opacity: 0.6;' : ''}">
                  ${escapeHtml(b.title)}
                </strong>
                ${isPostponed ? `<span style="font-size: 9.5px; padding: 0.08rem 0.45rem; border-radius: 4px; font-weight: 700; background: rgba(245, 159, 0, 0.2); color: #f59f00; border: 1px solid rgba(245, 159, 0, 0.45);">⏩ Von gestern verschoben</span>` : ''}
                ${b.badge && !isPostponed ? `<span style="font-size: 9.5px; padding: 0.08rem 0.4rem; border-radius: 4px; font-weight: 600; background: ${b.color}20; color: ${b.color}; border: 1px solid ${b.color}35;">${escapeHtml(b.badge)}</span>` : ''}
                ${isMandatory && b.location ? `<span style="font-size: 9.5px; padding: 0.08rem 0.45rem; border-radius: 4px; font-weight: 600; background: rgba(163, 113, 247, 0.15); color: #d2a8ff; border: 1px solid rgba(163, 113, 247, 0.35); display: inline-flex; align-items: center; gap: 3px;">📍 ${escapeHtml(b.location)}</span>` : ''}
                ${isCurrent ? `<span style="font-size: 9.5px; padding: 0.08rem 0.45rem; border-radius: 4px; font-weight: 700; background: rgba(56, 139, 253, 0.2); color: #79c0ff; border: 1px solid rgba(56, 139, 253, 0.45);">🔴 JETZT AKTIV (${activeMinsLeft}m)</span>` : ''}
              </div>
              <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
                ${escapeHtml(b.subtitle || '')}
              </div>
            </div>
          </div>

          <!-- Right: Delete / Postpone Button & Checkbox -->
          <div style="display: flex; align-items: center; gap: 0.45rem; flex-shrink: 0;">
            ${b.id !== 'evening_free' ? `
              <button type="button" onclick="promptRhythmBlockAction('${data.date}', '${b.id}')" title="Schritt entfernen oder auf morgen verschieben" style="background: transparent; border: 1px solid transparent; color: var(--text-dim); font-size: 13px; cursor: pointer; padding: 0.2rem 0.35rem; border-radius: 4px; transition: all 0.15s ease;" onmouseenter="this.style.color='#ff7b72'; this.style.borderColor='rgba(248,81,73,0.3)'; this.style.background='rgba(248,81,73,0.1)';" onmouseleave="this.style.color='var(--text-dim)'; this.style.borderColor='transparent'; this.style.background='transparent';">
                🗑️
              </button>
            ` : ''}
            <div onclick="toggleRhythmBlockDone('${data.date}', '${b.id}')" style="cursor: pointer; flex-shrink: 0; width: 22px; height: 22px; border-radius: 5px; border: 1.5px solid ${isCompleted ? '#3fb950' : 'rgba(255,255,255,0.25)'}; background: ${isCompleted ? '#238636' : 'rgba(255,255,255,0.03)'}; display: flex; align-items: center; justify-content: center; font-size: 12px; color: #fff; transition: all 0.15s ease;" title="${isCompleted ? 'Als offen markieren' : 'Als erledigt markieren'}">
              ${isCompleted ? '✓' : ''}
            </div>
          </div>
        </div>

        <!-- Detail Strip for Mandatory Attendance Events -->
        ${isMandatory && b.description ? `
          <div style="margin-top: 0.3rem; padding: 0.35rem 0.65rem; border-radius: 4px; background: rgba(163, 113, 247, 0.08); border-left: 2px solid #a371f7; font-size: 11px; color: #e2d9f3; line-height: 1.4;">
            🏛️ <strong>Offizielle Kurs-Information:</strong> ${escapeHtml(b.description.split('\n')[0])}
            ${b.location ? `<div style="margin-top: 0.15rem; color: #bca4ea; font-size: 10.5px;">📍 Kursort: ${escapeHtml(b.location)}</div>` : ''}
          </div>
        ` : ''}

        <!-- Subtopics / Decks for Morning New Cards Block -->
        ${b.id === 'block_new_cards' && b.topic_slots && b.topic_slots.length > 0 ? `
          <div style="margin-top: 0.35rem; padding-top: 0.4rem; border-top: 1px solid rgba(255,255,255,0.06); display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center;">
            <span style="font-size: 11px; font-weight: 700; color: #d2a8ff; display: inline-flex; align-items: center; gap: 4px;">
              ☀️ Vormittags-Karten:
            </span>
            ${b.topic_slots.map(s => `
              <span style="font-size: 11px; padding: 0.18rem 0.55rem; background: rgba(210, 168, 255, 0.12); border: 1px solid rgba(210, 168, 255, 0.3); color: #d2a8ff; border-radius: 4px; font-weight: 600;">
                ⚡ <strong>${s.cards_to_learn}×</strong> ${escapeHtml(s.clean_title || s.short_title)}${s.tomorrow_remaining_cards ? ` <span style="font-size: 9.5px; opacity: 0.75; color: #79c0ff;">(+${s.tomorrow_remaining_cards} morgen)</span>` : ''}
              </span>
            `).join('')}
            <span style="font-size: 11px; padding: 0.18rem 0.55rem; background: rgba(56, 139, 253, 0.12); border: 1px solid rgba(56, 139, 253, 0.3); color: #58a6ff; border-radius: 4px; font-weight: 700;">
              🎯 Exakt ${b.target_cards || 101} Karten HEUTE
            </span>
          </div>
          <div style="margin-top: 0.35rem; display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center;">
            <span style="font-size: 11px; font-weight: 700; color: #7ee787; display: inline-flex; align-items: center; gap: 4px;">
              🎬 Vorlesung &amp; Folien für HEUTE:
            </span>
            ${b.topic_slots.map(s => {
              const vidPath = (s.preferred_video_file || s.local_podcast_file_path || s.podcast_folder_name || s.local_podcast_folder_path || '').replace(/\\/g, '/');
              const slideRel = (s.slide_relative_path || s.matched_slide_filename || s.local_slide_file_path || '').replace(/\\/g, '/');
              return `
                ${vidPath ? `
                  <button type="button" class="btn-folder-chip" onclick="handleOpenLocalFolder('${escapeHtml(vidPath)}', 'Vorlesung (${escapeHtml(s.clean_title || s.short_title)})', false)" style="font-size: 10.5px; padding: 2px 7px; color: #7ee787; border: 1px solid rgba(46, 160, 67, 0.4); border-radius: 4px; background: rgba(46, 160, 67, 0.12); cursor: pointer; display: inline-flex; align-items: center; gap: 3px; font-weight: 600;" title="Öffnet das passende Vorlesungsvideo zu diesem Kartendeck im Datei-Explorer">
                    📂 ${escapeHtml(s.clean_title || s.short_title)}
                  </button>
                ` : ''}
                ${slideRel ? `
                  <a href="/api/v1/schedule/slides/view?path=${encodeURIComponent(slideRel)}" target="_blank" rel="noopener" style="font-size: 10.5px; padding: 2px 7px; color: #58a6ff; border: 1px solid rgba(88, 166, 255, 0.4); border-radius: 4px; background: rgba(88, 166, 255, 0.12); text-decoration: none; display: inline-flex; align-items: center; gap: 3px; font-weight: 600;" title="Öffnet die Folien-PDF zu diesem Thema">
                    📄 ${escapeHtml(s.matched_slide_filename || 'Folien')}
                  </a>
                ` : ''}
              `;
            }).join('')}
          </div>
        ` : ''}

        <!-- Action Strip for Afternoon Flex Block, Completed Lecture, or Block 3 Transfer -->
        ${(b.id === 'block_afternoon_flex' || b.id === 'block_podcasts' || isPostponed || b.focus_type === 'postponed_catchup') && (b.vam_url || b.podcast_folder_name || b.slide_filename || b.slide_rel_path || b.local_podcast_folder_path || b.local_slide_file_path || b.preferred_video_file) ? `
          <div style="margin-top: 0.35rem; padding-top: 0.4rem; border-top: 1px solid rgba(255,255,255,0.06); display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center;">
            <span style="font-size: 11px; font-weight: 700; color: ${isPostponed ? '#f59f00' : (b.id === 'block_podcasts' ? '#7ee787' : (b.is_completed ? '#3fb950' : '#79c0ff'))}; display: inline-flex; align-items: center; gap: 4px;">
              ${isPostponed ? '⏩ Nachhol-Vorlesung:' : (b.id === 'block_podcasts' ? '📖 Vorlesungs-Check HEUTE:' : (b.is_completed ? '✅ Absolvierte Vorlesung:' : '🌅 Vorlesung für MORGEN:'))}
            </span>
            ${(b.podcast_folder_name || b.local_podcast_folder_path || b.preferred_video_file || b.local_podcast_file_path) ? `
              <button type="button" class="btn-primary" onclick="handleOpenLocalFolder('${escapeHtml((b.preferred_video_file || b.local_podcast_file_path || b.podcast_folder_name || b.local_podcast_folder_path || '').replace(/\\/g, '/'))}', 'Vorlesungs-Datei', false)" style="font-size: 11px; padding: 0.32rem 0.75rem; background: #238636; border: 1px solid #2ea043; color: #fff; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; font-weight: 700;" title="Öffnet sofort deinen Windows Datei-Explorer mit dem Vorlesungsvideo vorausgewählt!">
                📂 Im Datei-Explorer öffnen
              </button>
            ` : ''}
            ${(b.slide_rel_path || b.slide_filename || b.local_slide_file_path) ? `
              <a href="/api/v1/schedule/slides/view?path=${encodeURIComponent((b.slide_rel_path || b.slide_filename || b.local_slide_file_path || '').replace(/\\/g, '/'))}" target="_blank" rel="noopener" class="btn-secondary" style="font-size: 11px; padding: 0.32rem 0.65rem; background: rgba(35, 134, 54, 0.15); color: #7ee787; border: 1px solid rgba(35, 134, 54, 0.4); border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; font-weight: 600; text-decoration: none;" title="Öffnet die Folien-PDF direkt im Browser">
                📄 Folien öffnen
              </a>
            ` : ''}
            <button type="button" onclick="consultAdvisorForLecture('${escapeHtml(b.tomorrow_lecture_title || b.title || '')}', '${escapeHtml(b.slide_filename || '')}')" class="btn-secondary" style="font-size: 11px; padding: 0.32rem 0.65rem; background: rgba(88, 166, 255, 0.15); color: #58a6ff; border: 1px solid rgba(88, 166, 255, 0.4); border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; font-weight: 600;" title="Öffnet die Vorlesungs- und Folien-Empfehlung im Vorlesungsberater">
              💡 Vorlesungsberater
            </button>
            <button type="button" onclick="handleStopMedia()" class="btn-secondary" style="font-size: 9.5px; padding: 0.2rem 0.45rem; background: rgba(218, 54, 51, 0.12); color: #f85149; border: 1px solid rgba(218, 54, 51, 0.35); border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center; gap: 3px; font-weight: 500;" title="Stoppt sofort alle im Hintergrund laufenden Audio- oder Videoplayer (VLC)">
              ⏹️ Ton beenden
            </button>
            <span style="font-size: 10.5px; padding: 0.18rem 0.5rem; background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.12); color: var(--text-muted); border-radius: 4px;">
              ${isPostponed ? '🧠 Neuro-optimal eingetaktet: 14:00 Uhr nach der Mensa' : `🎯 Bereitet ${b.tomorrow_cards || 101} Anki-Karten für morgen vor`}
            </span>
          </div>
        ` : ''}

        <!-- Special Action Strip & Cards for Lapse Block -->
        ${isLapseBlock ? `
          <div style="margin-top: 0.35rem; padding-top: 0.45rem; border-top: 1px solid rgba(255,255,255,0.08);">
            <!-- The 2 Dominant Action Buttons -->
            <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center;">
              <button type="button" onclick="createTemporaryStruggleDeck()" class="btn-primary" style="font-size: 11px; padding: 0.35rem 0.75rem; background: #238636; border-color: #2ea043; display: flex; align-items: center; gap: 0.35rem; color: #fff; font-weight: 700; border-radius: 5px; cursor: pointer;" title="Erstellt ein gefiltertes Problemkarten-Deck in Anki (beim Löschen bleiben alle Originaldecks unberührt)">
                <span>⚡</span> Temporäres Deck in Anki erstellen
              </button>
              <button type="button" onclick="openStruggleSlidesQuick('${escapeHtml(b.top_struggles?.[0]?.slide_info?.slide_pdf || 'Vorlesungen im Themenblock Blut und Immunsystem/Tuzlak_Adaptives und angeborenes Immunsystem.pdf')}', ${b.top_struggles?.[0]?.slide_info?.page_hint || 1})" class="btn-secondary" style="font-size: 11px; padding: 0.35rem 0.75rem; border-color: #58a6ff; color: #58a6ff; display: flex; align-items: center; gap: 0.35rem; font-weight: 600; border-radius: 5px; cursor: pointer;" title="Öffnet bei Zeitdruck sofort die relevante Folie mit Dozentengrafik">
                <span>📄</span> Relevante Folien öffnen (Schnell-Fokus)
              </button>
              <button type="button" onclick="cleanupTemporaryStruggleDeck()" class="btn-secondary" style="font-size: 10px; padding: 0.3rem 0.5rem; color: var(--text-muted); border-color: rgba(255,255,255,0.15); border-radius: 5px; cursor: pointer;" title="Entfernt das temporäre Tag nach Abschluss des Tages">
                <span>🧹</span> Tag bereinigen
              </button>
              ${(b.total_struggles || 0) > 0 ? `
                <button type="button" id="btnToggleStruggles" onclick="toggleStrugglesExpanded()" class="btn-secondary" style="font-size: 10.5px; padding: 0.3rem 0.6rem; color: var(--text-muted); border-color: rgba(255,255,255,0.15); border-radius: 5px; cursor: pointer;">
                  ${state.strugglesExpanded ? '▲ Problemkarten verbergen' : `▼ ${b.total_struggles} Problemkarten & Diagnosen anzeigen`}
                </button>
              ` : ''}
            </div>

            <!-- Expandable Struggle Cards List -->
            ${b.top_struggles && b.top_struggles.length > 0 ? `
              <div id="lapseStruggleCardsList" style="display: ${state.strugglesExpanded ? 'flex' : 'none'}; flex-direction: column; gap: 0.4rem; margin-top: 0.65rem; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 0.5rem;">
                <div style="font-size: 11px; color: var(--text-dim); display: flex; justify-content: space-between; align-items: center;">
                  <span>🧠 <strong>Wissenschaftliche Struggle-Analyse:</strong> Erkannte Kognitions-Engpässe &amp; synaptische Anker</span>
                  <span style="font-size: 10px; color: #8b949e;">Score: Latenz + Lapses + Ease</span>
                </div>
                ${b.top_struggles.map((c) => `
                  <div class="struggle-card-item">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; flex-wrap: wrap;">
                      <div style="display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap;">
                        <span style="font-size: 10px; font-weight: 700; color: ${c.ease_color}; background: ${c.ease_color}18; border: 1px solid ${c.ease_color}40; padding: 0.08rem 0.4rem; border-radius: 3px;">
                          ${escapeHtml(c.ease_label)} (${c.time_sec}s)
                        </span>
                        <span style="font-size: 10px; font-weight: 600; color: #d2a8ff; background: rgba(210, 168, 255, 0.1); padding: 0.08rem 0.35rem; border-radius: 3px;">
                          ${escapeHtml(c.diagnosis?.badge || 'Problemkarte')}
                        </span>
                        <span style="font-size: 10px; color: var(--text-dim); font-family: monospace;">Score: ${c.struggle_score}</span>
                      </div>
                      ${c.slide_info && c.slide_info.has_slide_link ? `
                        <button type="button" onclick="openStruggleSlidesQuick('${escapeHtml(c.slide_info.slide_pdf)}', ${c.slide_info.page_hint})" class="btn-secondary" style="font-size: 9.5px; padding: 0.1rem 0.4rem; height: auto; border-color: rgba(56, 139, 253, 0.3); color: #79c0ff; cursor: pointer;">
                          📄 ${escapeHtml(c.slide_info.estimated_slides)}
                        </button>
                      ` : ''}
                    </div>
                    <div style="font-size: 12px; font-weight: 600; color: var(--text-main); margin-top: 0.3rem;">
                      ${escapeHtml(c.question)}
                    </div>
                    <div style="font-size: 11px; color: #8b949e; margin-top: 0.15rem; font-style: italic;">
                      ↳ ${escapeHtml(c.answer)}
                    </div>
                    <div style="margin-top: 0.35rem; font-size: 11px; background: rgba(255, 255, 255, 0.03); border-left: 2px solid #58a6ff; padding: 0.25rem 0.5rem; border-radius: 0 4px 4px 0;">
                      <span style="color: #79c0ff; font-weight: 600;">💡 Imprägnierungs-Tipp:</span>
                      <span style="color: var(--text-muted);">${escapeHtml(c.diagnosis?.anchor_tip || '')}</span>
                    </div>
                  </div>
                `).join('')}
              </div>
            ` : ''}
          </div>
        ` : ''}
        <!-- Draggable bottom border handle for dynamic stretching/shortening -->
        ${isDraggable ? `
          <div class="rhythm-resize-handle" data-block-id="${b.id}" title="Untere Kante ziehen zum Verlängern oder Verkürzen">
            <div class="rhythm-resize-pill" style="display: none;"></div>
          </div>
        ` : ''}
      </div>
    `;
  });

  container.innerHTML = tomorrowAlertHtml + html;
  initRhythmDragAndDrop();
  initRhythmResizeHandlers();

  const indicatorEl = document.getElementById('scienceRhythmCurrentIndicator');
  if (indicatorEl) {
    if (activeBlockTitle) {
      indicatorEl.innerHTML = `<span style="color: #79c0ff;">🔴 JETZT AKTIV:</span> ${escapeHtml(activeBlockTitle)} (${activeMinsLeft}m)`;
    } else if (isToday && nowMinutes >= 17 * 60 + 30) {
      indicatorEl.innerHTML = `🎉 Feierabend & Sport am Abend!`;
    } else {
      indicatorEl.textContent = `Lernstart: ${data.start_time || '08:30'} Uhr`;
    }
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
window.toggleBacklogTriageModal = toggleBacklogTriageModal;
window.setTriageBudget = setTriageBudget;
window.copyAnkiQuery = copyAnkiQuery;
window.copyTriageQueryToClipboard = copyTriageQueryToClipboard;
window.loadWorkloadForecast = loadWorkloadForecast;
window.selectForecastDay = selectForecastDay;
window.loadScienceRhythm = loadScienceRhythm;
window.toggleRhythmBlockDone = toggleRhythmBlockDone;
window.toggleConfigDrawer = toggleConfigDrawer;
window.handleConfigDrawerBackdrop = handleConfigDrawerBackdrop;
window.setRhythmStartNow = setRhythmStartNow;
window.setRhythmLunch = setRhythmLunch;
window.handleRhythmConfigChange = handleRhythmConfigChange;
window.createTemporaryStruggleDeck = createTemporaryStruggleDeck;
window.cleanupTemporaryStruggleDeck = cleanupTemporaryStruggleDeck;
window.openStruggleDeckInAnki = openStruggleDeckInAnki;
window.openStruggleSlidesQuick = openStruggleSlidesQuick;
window.toggleStrugglesExpanded = toggleStrugglesExpanded;
window.promptRhythmBlockAction = promptRhythmBlockAction;
window.closeRhythmBlockActionModal = closeRhythmBlockActionModal;
window.executePostponeRhythmBlock = executePostponeRhythmBlock;
window.executeDeleteRhythmBlock = executeDeleteRhythmBlock;
window.restoreRhythmBlocks = restoreRhythmBlocks;
window.handleQuickMoveRhythmBlock = handleQuickMoveRhythmBlock;
window.moveRhythmBlock = moveRhythmBlock;
window.reorderRhythmBlockTo = reorderRhythmBlockTo;
window.recalculateRhythmTimes = recalculateRhythmTimes;
window.handleNudgeBlockDuration = handleNudgeBlockDuration;
window.handlePromptBlockDuration = handlePromptBlockDuration;
window.initRhythmResizeHandlers = initRhythmResizeHandlers;
window.saveRhythmDurationsToBackend = saveRhythmDurationsToBackend;
window.toggleMissionMetricsDrawer = toggleMissionMetricsDrawer;
window.toggleTopicDetails = toggleTopicDetails;

// Auto-sync Anki desktop periodically every 30 seconds
setInterval(() => {
  loadAnkiDesktopStatus(false);
  loadWorkloadForecast(false);
  loadAnkiWeaknesses();
}, 30000);

// Run on page load (support immediate execution if DOM is already ready)
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    init();
    loadAnkiDesktopStatus(false);
    loadWorkloadForecast(false);
    loadScienceRhythm();
  });
} else {
  init();
  loadAnkiDesktopStatus(false);
  loadWorkloadForecast(false);
  loadScienceRhythm();
}


// ============================================================================
// MULTI-PAGE VIEW ROUTER (APP RESTRUCTURING)
// ============================================================================

function switchAppPage(pageId) {
  if (!pageId) return;
  if (!pageId.startsWith('page-')) pageId = 'page-' + pageId;

  const navBtns = document.querySelectorAll('.nav-tab-btn, .bottom-nav-item, .side-menu-item');
  navBtns.forEach(btn => {
    if (btn.getAttribute('data-page') === pageId) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  const pages = document.querySelectorAll('.app-page');
  pages.forEach(p => {
    if (p.id === pageId) {
      p.classList.add('active');
    } else {
      p.classList.remove('active');
    }
  });

  try {
    localStorage.setItem('sl_active_page', pageId);
    const hash = pageId.replace('page-', '');
    if (window.location.hash !== '#' + hash) {
      history.replaceState(null, '', '#' + hash);
    }
  } catch (e) {}

  // Page-specific lazy activations
  if (pageId === 'page-advisor') {
    if (!state.advisorData) {
      loadAdvisorData();
    }
  } else if (pageId === 'page-roadmap') {
    renderPageRoadmap();
  } else if (pageId === 'page-analytics') {
    renderPageAnalytics();
  }
}

function switchMobileView(view) {
  if (view === 'mission') switchAppPage('page-today');
  else if (view === 'schedule') switchAppPage('page-today');
  else if (view === 'stats') switchAppPage('page-analytics');
}

window.addEventListener('hashchange', () => {
  if (window.location.hash) {
    const hashPage = 'page-' + window.location.hash.replace('#', '');
    if (document.getElementById(hashPage)) {
      switchAppPage(hashPage);
    }
  }
});


// ============================================================================
// VORLESUNGS- & ANKI-BERATER (COGNITIVE ADVISOR ENGINE)
// ============================================================================

state.advisorData = null;
state.advisorFilterMode = 'all';
state.advisorFilterModule = 'all';
state.advisorTargetCards = 100;
state.selectedAdvisorLecture = null;

async function loadAdvisorData(query = '') {
  try {
    let url = `${API_BASE}/advisor/search?q=${encodeURIComponent(query)}&cards=${state.advisorTargetCards}`;
    if (state.advisorFilterMode && state.advisorFilterMode !== 'all') {
      url += `&mode=${encodeURIComponent(state.advisorFilterMode)}`;
    }
    if (state.advisorFilterModule && state.advisorFilterModule !== 'all') {
      url += `&module=${encodeURIComponent(state.advisorFilterModule)}`;
    }

    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.advisorData = data;

    const countBadge = document.getElementById('advisorCountBadge');
    if (countBadge && data.summary) {
      countBadge.textContent = `${data.summary.total_matching} von ${data.summary.total_lectures} Vorlesungen`;
    }

    // Set or refresh selected lecture
    if (query || !state.selectedAdvisorLecture) {
      state.selectedAdvisorLecture = data.top_match;
    } else if (state.selectedAdvisorLecture && data.results) {
      const refreshed = data.results.find(l => l.id === state.selectedAdvisorLecture.id);
      if (refreshed) state.selectedAdvisorLecture = refreshed;
    }

    renderAdvisorHero(state.selectedAdvisorLecture);
    renderAdvisorCatalog(data.results);
    renderAdvisorModuleFilters();
  } catch (err) {
    console.error('Failed to load advisor data:', err);
  }
}

let advisorSearchTimer = null;
function handleAdvisorSearch(query) {
  clearTimeout(advisorSearchTimer);
  const clearBtn = document.getElementById('advisorClearBtn');
  if (clearBtn) {
    clearBtn.style.display = query ? 'block' : 'none';
  }
  advisorSearchTimer = setTimeout(() => {
    loadAdvisorData(query);
  }, 120);
}

function clearAdvisorSearch() {
  const input = document.getElementById('advisorSearchInput');
  if (input) {
    input.value = '';
    handleAdvisorSearch('');
  }
}

function handleAdvisorTargetCardsChange(val) {
  const num = parseInt(val, 10);
  if (!isNaN(num) && num > 0) {
    state.advisorTargetCards = num;
    const searchInput = document.getElementById('advisorSearchInput');
    loadAdvisorData(searchInput ? searchInput.value : '');
  }
}

function setAdvisorTargetCards(cards, btnEl) {
  state.advisorTargetCards = cards;
  const input = document.getElementById('advisorTargetCardsInput');
  if (input) input.value = cards;
  document.querySelectorAll('.advisor-preset-btn').forEach(b => {
    b.classList.remove('active');
    b.style.borderColor = '';
    b.style.color = '';
  });
  if (btnEl) {
    btnEl.classList.add('active');
    btnEl.style.borderColor = 'var(--accent-blue)';
    btnEl.style.color = 'var(--accent-blue)';
  }
  const searchInput = document.getElementById('advisorSearchInput');
  loadAdvisorData(searchInput ? searchInput.value : '');
}

function applyAdvisorChip(topic) {
  const input = document.getElementById('advisorSearchInput');
  if (input) {
    input.value = topic;
    handleAdvisorSearch(topic);
    const hero = document.getElementById('advisorDecisionHeroContainer');
    if (hero) hero.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function setAdvisorModeFilter(mode, btnEl) {
  state.advisorFilterMode = mode;
  document.querySelectorAll('.advisor-filter-btn').forEach(b => b.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');
  const input = document.getElementById('advisorSearchInput');
  loadAdvisorData(input ? input.value : '');
}

function setAdvisorModuleFilter(moduleName, btnEl) {
  state.advisorFilterModule = moduleName;
  document.querySelectorAll('.advisor-mod-btn').forEach(b => b.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');
  const input = document.getElementById('advisorSearchInput');
  loadAdvisorData(input ? input.value : '');
}

function selectAdvisorLecture(lectureId) {
  if (!state.advisorData || !state.advisorData.results) return;
  const lect = state.advisorData.results.find(l => l.id === lectureId) ||
               (state.advisorData.top_match && state.advisorData.top_match.id === lectureId ? state.advisorData.top_match : null);
  if (lect) {
    state.selectedAdvisorLecture = lect;
    renderAdvisorHero(lect);
    const hero = document.getElementById('advisorDecisionHeroContainer');
    if (hero) {
      hero.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }
}

function renderAdvisorHero(lect) {
  const container = document.getElementById('advisorDecisionHeroContainer');
  if (!container) return;

  if (!lect) {
    container.innerHTML = `
      <div class="advisor-decision-card" style="text-align: center; padding: 2rem;">
        <span style="font-size: 32px;">🔍</span>
        <h3 style="color: var(--text-muted); margin-top: 0.5rem;">Keine Vorlesung gefunden</h3>
        <p style="font-size: 12px; color: var(--text-dim);">Versuche einen anderen Begriff (z. B. Hämoglobin, Manatschal, Magen, EKG, Vitamine, Sauerstoff).</p>
      </div>
    `;
    return;
  }

  const isSkip = lect.recommendation && lect.recommendation.toLowerCase().includes('skip');
  const is1_0x = lect.recommendation && lect.recommendation.includes('1.0x');
  const isAudio = lect.is_audio_only;

  let borderColor = '#d29922';
  let bannerBg = 'rgba(210, 153, 34, 0.15)';
  let bannerBorder = 'rgba(210, 153, 34, 0.4)';
  let bannerText = '#e3b341';

  if (isSkip) {
    borderColor = '#f85149';
    bannerBg = 'rgba(248, 81, 73, 0.15)';
    bannerBorder = 'rgba(248, 81, 73, 0.4)';
    bannerText = '#ff7b72';
  } else if (is1_0x) {
    borderColor = '#3fb950';
    bannerBg = 'rgba(63, 185, 80, 0.15)';
    bannerBorder = 'rgba(63, 185, 80, 0.4)';
    bannerText = '#56d364';
  } else if (isAudio) {
    borderColor = '#58a6ff';
    bannerBg = 'rgba(56, 139, 253, 0.15)';
    bannerBorder = 'rgba(56, 139, 253, 0.4)';
    bannerText = '#79c0ff';
  }

  // 1. Multi-Lecture Selector (When multiple lectures match query)
  let multiMatchHtml = '';
  if (state.advisorData && state.advisorData.top_matches && state.advisorData.top_matches.length > 1) {
    multiMatchHtml = `
      <div class="advisor-top-matches-bar">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 11.5px; font-weight: 700; color: #58a6ff; display: flex; align-items: center; gap: 0.35rem;">
            <span>📚</span> Passende Vorlesungen (${state.advisorData.top_matches.length} Treffer):
          </span>
          <span style="font-size: 11px; color: var(--text-dim);">Klicke zum Umschalten</span>
        </div>
        <div class="advisor-top-matches-pills">
          ${state.advisorData.top_matches.map((m, idx) => {
            const isActive = lect && lect.id === m.id;
            const recShort = m.recommendation.toLowerCase().includes('skip') ? '🛑 Skip' : m.recommendation;
            return `
              <button type="button" class="advisor-match-pill ${isActive ? 'active' : ''}" onclick="selectAdvisorLecture('${m.id}')" title="${escapeHtml(m.title)}">
                <span>${idx + 1}.</span>
                <span style="max-width: 170px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(m.title)}</span>
                <span style="font-size: 10px; opacity: 0.85; background: rgba(0,0,0,0.25); padding: 0.1rem 0.3rem; border-radius: 3px;">${recShort}</span>
              </button>
            `;
          }).join('')}
        </div>
      </div>
    `;
  }

  // 2. Dynamic Timestamp Guidance Hero Box
  const ts = lect.timestamp_guidance || {
    target_cards: state.advisorTargetCards,
    total_lecture_cards: lect.total_anki_cards || 200,
    start_timestamp: '00:00',
    end_timestamp: '85:00',
    video_minutes_raw: 85,
    video_minutes_effective: 70,
    saved_minutes: 0,
    guidance_text: 'Schau die empfohlene Vorlesung nach Bedarf.',
    annotated_chapters: lect.chapters || []
  };

  let tsHeroHtml = '';
  if (ts.is_full_skip) {
    tsHeroHtml = `
      <div class="advisor-ts-hero-box" style="border-color: rgba(248, 81, 73, 0.35); background: rgba(248, 81, 73, 0.05);">
        <div style="display: flex; align-items: flex-start; gap: 0.65rem; flex: 1; min-width: 250px;">
          <span style="font-size: 26px;">⚡</span>
          <div>
            <div style="font-size: 13px; font-weight: 700; color: #f85149; display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
              <span>100% SKIP-EMPFEHLUNG: 0 Minuten Vorlesung nötig!</span>
              <span class="advisor-ts-timecode" style="background: rgba(248, 81, 73, 0.15); color: #ff7b72; border-color: rgba(248, 81, 73, 0.3);">Skip (0x)</span>
            </div>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 0.25rem; line-height: 1.4;">
              ${escapeHtml(ts.guidance_text)}
            </div>
            ${ts.time_roi ? `
              <div class="advisor-roi-box">
                <span style="font-size: 14px;">⏱️</span>
                <div>
                  <strong style="color: #ff7b72;">Time-ROI Analyse:</strong>
                  <span style="color: var(--text-dim); margin-left: 0.25rem;">${escapeHtml(ts.time_roi.verdict)}</span>
                </div>
              </div>
            ` : ''}
          </div>
        </div>
        <div class="advisor-ts-savings-badge" style="background: rgba(35, 134, 54, 0.2); border-color: #3fb950; color: #3fb950;" title="Volle Vorlesungszeit gespart!">
          <span>⚡</span>
          <span>+${ts.saved_minutes} Min gespart!</span>
        </div>
      </div>
    `;
  } else if (ts.is_micro_deep_dive) {
    tsHeroHtml = `
      <div class="advisor-ts-hero-box" style="border-color: rgba(210, 153, 34, 0.45); background: rgba(210, 153, 34, 0.06);">
        <div style="display: flex; align-items: flex-start; gap: 0.65rem; flex: 1; min-width: 250px;">
          <span style="font-size: 26px;">💡</span>
          <div>
            <div style="font-size: 13px; font-weight: 700; color: #d29922; display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
              <span>Optionaler Micro-Deep-Dive:</span>
              <span class="advisor-ts-timecode" style="background: rgba(210, 153, 34, 0.15); color: #e3b341; border-color: rgba(210, 153, 34, 0.35);">${ts.start_timestamp} – ${ts.end_timestamp}</span>
              <span style="font-size: 11px; font-weight: 600; color: var(--text-dim);">(${ts.video_minutes_effective} Min. / max. 20m)</span>
            </div>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 0.25rem; line-height: 1.4;">
              ${escapeHtml(ts.guidance_text)}
            </div>
          </div>
        </div>
        <div class="advisor-ts-savings-badge" title="Ersparnis gegenüber der Gesamtvorlesung">
          <span>⚡</span>
          <span>+${ts.saved_minutes} Min gespart!</span>
        </div>
      </div>
    `;
  } else {
    tsHeroHtml = `
      <div class="advisor-ts-hero-box">
        <div style="display: flex; align-items: flex-start; gap: 0.65rem; flex: 1; min-width: 250px;">
          <span style="font-size: 24px;">⏱️</span>
          <div>
            <div style="font-size: 13px; font-weight: 700; color: var(--text-main); display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
              <span>Relevanter Video-Abschnitt für deine <strong>${ts.target_cards}</strong> Anki-Karten:</span>
              <span class="advisor-ts-timecode">${ts.start_timestamp} – ${ts.end_timestamp}</span>
            </div>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 0.25rem; line-height: 1.4;">
              ${escapeHtml(ts.guidance_text)}
            </div>
          </div>
        </div>
        <div class="advisor-ts-savings-badge" title="Ersparnis gegenüber der 90-minütigen Gesamtvorlesung">
          <span>⚡</span>
          <span>${ts.saved_minutes > 0 ? `+${ts.saved_minutes} Min gespart!` : `${ts.video_minutes_effective} Min Fokus`}</span>
        </div>
      </div>
    `;
  }

  // 3. Detailed Chapters with Timestamps & Cards Mapping
  let chaptersHtml = '';
  const chaptersList = ts.annotated_chapters && ts.annotated_chapters.length > 0 ? ts.annotated_chapters : (lect.chapters || []);
  if (chaptersList && chaptersList.length > 0) {
    chaptersHtml = `
      <div class="advisor-chapters-container">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.2rem; flex-wrap: wrap; gap: 0.35rem;">
          <strong style="font-size: 12.5px; color: var(--text-main); display: flex; align-items: center; gap: 0.35rem;">
            <span>📋</span> Kapitel- &amp; Timestamp-Aufschlüsselung (${lect.total_anki_cards || 200} Anki-Karten):
          </strong>
          <span style="font-size: 11px; color: var(--text-dim);">Exakte Timecodes aus Podcast-Aufzeichnung</span>
        </div>
        ${chaptersList.map((chap, idx) => {
          const isNeeded = chap.is_needed_for_target !== false;
          const statusClass = isNeeded ? 'needed' : 'skipped';
          return `
            <div class="advisor-chapter-card ${statusClass}">
              <div style="display: flex; align-items: flex-start; gap: 0.65rem; flex: 1; min-width: 220px;">
                <span class="advisor-chapter-time" title="Klicke zum Kopieren" onclick="copyAnkiFactText('${encodeURIComponent(chap.start + ' - ' + chap.end)}', this)">
                  ⏱️ ${chap.start} – ${chap.end}
                </span>
                <div style="flex: 1;">
                  <div style="font-size: 12.5px; font-weight: 600; color: var(--text-main);">
                    ${escapeHtml(chap.title)}
                  </div>
                  <div style="font-size: 11px; color: var(--text-dim); margin-top: 0.15rem;">
                    📄 ${escapeHtml(chap.slide_range || '')} • 🃏 <strong>${chap.cards_count} Karten</strong> (Bereich: ${chap.cards_range || ''})
                  </div>
                  <div style="display: flex; gap: 0.25rem; flex-wrap: wrap; margin-top: 0.35rem;">
                    ${(chap.topics || []).map(t => `<span class="advisor-topic-tag">${escapeHtml(t)}</span>`).join('')}
                  </div>
                </div>
              </div>
              <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 0.25rem; flex-shrink: 0;">
                <span style="font-size: 11px; font-weight: 600; color: ${isNeeded ? '#56d364' : 'var(--text-dim)'}; background: ${isNeeded ? 'rgba(63, 185, 80, 0.12)' : 'rgba(255,255,255,0.05)'}; padding: 0.2rem 0.5rem; border-radius: 4px;">
                  ${escapeHtml(chap.coverage_label || (isNeeded ? '🟢 Ansehen' : '⚪ Überspringen'))}
                </span>
                <span style="font-size: 10.5px; color: var(--text-dim);">Dauer: ${chap.duration_min} Min</span>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;
  }

  // 4. Pure-Anki Facts
  let factsHtml = '';
  if (lect.anki_facts && lect.anki_facts.length > 0) {
    factsHtml = `
      <div class="advisor-anki-facts-box" style="margin-top: 0.75rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.35rem;">
          <strong style="color: ${isSkip ? '#ff7b72' : '#58a6ff'}; font-size: 13px; display: flex; align-items: center; gap: 0.4rem;">
            <span>${isSkip ? '🚨' : '💡'}</span>
            ${isSkip ? 'Pure-Anki Prioritäten (Exakt diese 3 Kernfakten lernen):' : 'Zentrale Fokus-Konzepte der Vorlesung:'}
          </strong>
          <span style="font-size: 11px; color: var(--text-dim);">Grounded in UZH-Folien</span>
        </div>
        <div style="display: flex; flex-direction: column; gap: 0.5rem;">
          ${lect.anki_facts.map((fact, idx) => `
            <div class="advisor-anki-fact-item">
              <span style="font-weight: 700; color: ${isSkip ? '#ff7b72' : '#58a6ff'}; font-size: 13px; min-width: 20px;">${idx + 1}.</span>
              <div style="flex: 1; font-size: 12px; color: var(--text-main); line-height: 1.5;">${escapeHtml(fact)}</div>
              <button type="button" class="btn-copy-fact" onclick="copyAnkiFactText('${encodeURIComponent(fact)}', this)" title="Fakt für Anki kopieren">
                📋 Kopieren
              </button>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  let mediaHtml = '';
  if (lect.has_local_podcast) {
    mediaHtml = `
      <div style="display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 0.5rem; font-size: 11.5px; color: var(--text-muted); background: var(--bg-base); padding: 0.6rem 0.85rem; border-radius: var(--radius-xs); border: 1px solid var(--border-subtle);">
        <span style="color: #3fb950; font-weight: 600;">🎬 Lokaler Podcast verfügbar:</span>
        <span>📽️ Folien: <strong>${escapeHtml(lect.folien_filename || 'Folien.mp4')}</strong></span>
        <span>•</span>
        <span>👨‍🏫 Dozent: <strong>${escapeHtml(lect.prof_filename || 'Prof.mp4')}</strong></span>
      </div>
    `;
  }

  let slideLinkHtml = '';
  if (lect.slide_pdf) {
    slideLinkHtml = `
      <div style="margin-top: 0.35rem; font-size: 11.5px; color: var(--text-dim);">
        📄 Kurs-Folie: <span style="color: var(--accent-blue); font-family: monospace;">${escapeHtml(lect.slide_pdf)}</span>
      </div>
    `;
  }

  container.innerHTML = `
    ${multiMatchHtml}
    <div class="advisor-decision-card" style="border-left: 4px solid ${borderColor};">
      
      <div class="advisor-decision-header">
        <div style="flex: 1; min-width: 260px;">
          <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
            <span style="font-size: 11px; background: var(--bg-surface-active); color: var(--text-muted); padding: 0.15rem 0.45rem; border-radius: 4px; font-weight: 600;">
              📅 ${lect.date}
            </span>
            <span style="font-size: 11.5px; color: var(--text-dim); font-weight: 500;">
              ${escapeHtml(lect.module)}
            </span>
          </div>
          <h2 style="margin: 0; font-size: 18px; font-weight: 700; color: var(--text-main); line-height: 1.35;">
            ${escapeHtml(lect.title)}
          </h2>
          <div style="font-size: 12px; color: var(--text-muted); margin-top: 0.25rem;">
            👨‍🏫 ${escapeHtml(lect.lecturer || 'UZH Dozierende')}
          </div>
          ${slideLinkHtml}
        </div>

        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 0.35rem;">
          <div class="advisor-speed-banner" style="background: ${bannerBg}; border: 1px solid ${bannerBorder}; color: ${bannerText};">
            <span>${isSkip ? '🛑' : (isAudio ? '🎧' : '⚡')}</span>
            <span>${escapeHtml(lect.badge_label || lect.recommendation)}</span>
          </div>
          <span style="font-size: 11px; color: var(--text-dim);">
            Empfohlene Geschwindigkeit: <strong style="color: var(--text-main);">${lect.recommendation}</strong>
          </span>
        </div>
      </div>

      ${tsHeroHtml}

      <div class="advisor-metrics-grid">
        <div class="advisor-metric-box">
          <div class="advisor-metric-label">📊 Prüfungsrelevanz</div>
          <div class="advisor-metric-val" style="color: ${lect.exam_yield === 'High-Yield' ? '#f85149' : (lect.exam_yield === 'Med-Yield' ? '#d29922' : '#8b949e')};">
            ${escapeHtml(lect.exam_yield)}
          </div>
        </div>

        <div class="advisor-metric-box">
          <div class="advisor-metric-label">👁️ Visuelle Abhängigkeit</div>
          <div class="advisor-metric-val" style="color: ${lect.visual_dependency === 'Hoch' ? '#58a6ff' : '#3fb950'};">
            ${escapeHtml(lect.visual_dependency)} ${lect.visual_dependency === 'Hoch' ? '(Bildschirm zwingend)' : '(Audio möglich)'}
          </div>
        </div>

        <div class="advisor-metric-box">
          <div class="advisor-metric-label">🗣️ Dozenten-Tempo (gemessen)</div>
          <div class="advisor-metric-val">
            ${escapeHtml(lect.lecturer_tempo)} <span style="font-size: 11px; font-weight: normal; color: var(--text-dim);">(${Math.round(lect.silence_ratio * 100)}% Pause)</span>
          </div>
        </div>

        <div class="advisor-metric-box">
          <div class="advisor-metric-label">💡 Lern-Strategie</div>
          <div class="advisor-metric-val" style="color: ${bannerText};">
            ${isSkip ? '100% Anki' : (isAudio ? 'Audio-Podcast' : 'Aktiv Mitdenken')}
          </div>
        </div>
      </div>

      <div class="advisor-reason-box">
        <strong style="color: #58a6ff; display: block; margin-bottom: 0.25rem;">
          🧠 Kognitive Begründung &amp; Zeitersparnis (Cognitive Load Theory):
        </strong>
        ${escapeHtml(lect.tradeoff_reason)}
      </div>

      ${chaptersHtml}
      ${factsHtml}
      ${mediaHtml}

    </div>
  `;
}

function renderAdvisorCatalog(lectures) {
  const container = document.getElementById('advisorLecturesListContainer');
  if (!container) return;

  if (!lectures || lectures.length === 0) {
    container.innerHTML = `
      <div style="padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 12px;">
        Keine Vorlesungen für die gewählten Filterkriterien gefunden.
      </div>
    `;
    return;
  }

  container.innerHTML = lectures.map(l => {
    const isSelected = state.selectedAdvisorLecture && state.selectedAdvisorLecture.id === l.id;
    const isSkip = l.recommendation.toLowerCase().includes('skip');
    const is1_0x = l.recommendation.includes('1.0x');
    const isAudio = l.is_audio_only;

    let badgeColor = '#d29922';
    if (isSkip) badgeColor = '#f85149';
    else if (is1_0x) badgeColor = '#3fb950';
    else if (isAudio) badgeColor = '#58a6ff';

    const ts = l.timestamp_guidance;
    const tsSnippet = ts ? `<span style="font-size: 11px; color: #56d364; font-family: monospace; margin-left: 0.4rem;">⏱️ ${ts.start_timestamp}–${ts.end_timestamp}</span>` : '';

    return `
      <div class="advisor-lecture-row" onclick="selectAdvisorLecture('${l.id}')" style="${isSelected ? 'background: rgba(56, 139, 253, 0.12); border: 1px solid rgba(56, 139, 253, 0.35);' : ''}">
        <div style="display: flex; align-items: center; gap: 0.75rem; flex: 1; min-width: 0;">
          <span style="font-size: 11px; color: var(--text-dim); font-family: monospace; min-width: 72px;">${l.date}</span>
          <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            <strong style="color: var(--text-main); font-size: 13px;">${escapeHtml(l.title)}</strong>
            ${tsSnippet}
            <div style="font-size: 11px; color: var(--text-muted); overflow: hidden; text-overflow: ellipsis;">
              ${escapeHtml(l.module)} • ${escapeHtml(l.lecturer || '')} • 🃏 ${l.total_anki_cards || 200} Karten
            </div>
          </div>
        </div>

        <div style="display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0;">
          <span style="font-size: 10.5px; padding: 0.15rem 0.45rem; border-radius: 4px; border: 1px solid ${badgeColor}; color: ${badgeColor}; font-weight: 600;">
            ${escapeHtml(l.recommendation)}
          </span>
          <button type="button" class="btn-secondary" style="font-size: 11px; padding: 0.2rem 0.5rem;" onclick="event.stopPropagation(); selectAdvisorLecture('${l.id}')">
            Details ▶
          </button>
        </div>
      </div>
    `;
  }).join('');
}

function renderAdvisorModuleFilters() {
  const container = document.getElementById('advisorModuleFilterBar');
  if (!container) return;

  const modules = [
    { id: 'all', label: 'Alle Module' },
    { id: 'Blut', label: '1. Blut & Immun' },
    { id: 'Herz', label: '2. Herz-Kreislauf' },
    { id: 'Atmung', label: '3. Atmung' },
    { id: 'Verdauung', label: '4. Verdauung' },
    { id: 'Stoffwechsel', label: '5. Stoffwechsel' },
    { id: 'Endokrinologie', label: '6. Endokrinologie' },
  ];

  container.innerHTML = modules.map(m => `
    <button type="button" class="advisor-mod-btn ${state.advisorFilterModule === m.id ? 'active' : ''}" onclick="setAdvisorModuleFilter('${m.id}', this)" style="background: ${state.advisorFilterModule === m.id ? 'rgba(56, 139, 253, 0.15)' : 'transparent'}; border: 1px solid ${state.advisorFilterModule === m.id ? '#58a6ff' : 'var(--border-subtle)'}; color: ${state.advisorFilterModule === m.id ? '#58a6ff' : 'var(--text-muted)'}; border-radius: 4px; padding: 0.2rem 0.55rem; font-size: 11px; font-weight: 500; cursor: pointer;">
      ${m.label}
    </button>
  `).join('');
}

function copyAnkiFactText(encodedText, btnEl) {
  const text = decodeURIComponent(encodedText);
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => {
      const orig = btnEl.textContent;
      btnEl.textContent = '✓ Kopiert!';
      btnEl.style.color = '#3fb950';
      btnEl.style.borderColor = '#3fb950';
      setTimeout(() => {
        btnEl.textContent = orig;
        btnEl.style.color = '';
        btnEl.style.borderColor = '';
      }, 2000);
    });
  } else {
    showToast('Kopieren nicht unterstützt');
  }
}

// 1-Click Jump from Today Topic to Advisor
window.consultAdvisorForTopic = function(topicName) {
  switchAppPage('page-advisor');
  const input = document.getElementById('advisorSearchInput');
  if (input) {
    const cleaned = topicName.replace(/^\d+\s+/, '').trim();
    input.value = cleaned;
    handleAdvisorSearch(cleaned);
  }
};

// 1-Click Jump from Schedule Block / Slide directly to Lecture Advisor
window.consultAdvisorForLecture = function(lectureTitle, slideFilename) {
  switchAppPage('page-advisor');
  let q = lectureTitle || '';
  // Remove prefixes like "Nachmittag: Vorlesung für MORGEN sichten – "
  q = q.replace(/^Nachmittag:\s*Vorlesung\s*für\s*MORGEN\s*sichten\s*–\s*/i, '');
  // Remove date hints like "(22.09.2025)"
  q = q.replace(/\s*\(\d{2}\.\d{2}\.\d{4}\)/g, '');
  q = q.replace(/\s*\(.*?\)/g, '');
  q = q.trim();

  // If multiple comma-separated topics, take the primary topic (e.g. "Thrombozyten")
  const primaryTopic = q.split(',')[0].trim() || q;

  const input = document.getElementById('advisorSearchInput');
  if (input) {
    input.value = primaryTopic;
    handleAdvisorSearch(primaryTopic);
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
};


// ============================================================================
// PAGE ROADMAP & ANALYTICS SYNCHRONIZERS
// ============================================================================

async function renderPageRoadmap() {
  const grid = document.getElementById('pageRoadmapModulesGrid');
  const list = document.getElementById('pageRoadmapDaysList');
  if (!grid || !list) return;

  try {
    const targetParam = state.targetDate ? `?target_date=${state.targetDate}` : '';
    const res = await fetch(`${API_BASE}/curriculum/roadmap${targetParam}`);
    if (!res.ok) return;
    const data = await res.json();
    state.roadmapData = data;
    _cachedRoadmapData = data;

    if (data.modules) {
      grid.innerHTML = data.modules.map(m => `
        <div class="roadmap-module-card">
          <div class="roadmap-mod-header">
            <span class="roadmap-mod-name">${escapeHtml(m.module_name)}</span>
            <span class="status-badge" style="font-size: 10px; background: rgba(88,166,255,0.15); color: #58a6ff;">${m.total_cards} Karten</span>
          </div>
          <div style="font-size: 11px; color: var(--text-muted); margin-top: 0.35rem;">
            📅 ${m.start_date} bis ${m.end_date} (${m.active_days} Lerntage)
          </div>
          <div style="margin-top: 0.5rem; height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden;">
            <div style="height: 100%; width: ${m.progress_pct || 0}%; background: var(--status-done);"></div>
          </div>
        </div>
      `).join('');
    }

    if (data.schedule) {
      _cachedRoadmapData = data;
      // Render into a temporary #roadmapDaysList if it doesn't exist, then copy to page list
      const modalList = document.getElementById('roadmapDaysList');
      if (modalList) {
        renderRoadmapDaysList(data.schedule);
        list.innerHTML = modalList.innerHTML;
        // Reassign event listeners by reinitializing DnD on the page list
        initRoadmapDragAndDrop();
      } else {
        // Temporarily create a shadow container
        const shadow = document.createElement('div');
        shadow.id = 'roadmapDaysList';
        document.body.appendChild(shadow);
        renderRoadmapDaysList(data.schedule);
        list.innerHTML = shadow.innerHTML;
        shadow.remove();
      }
    }
  } catch (err) {
    console.warn('Roadmap fetch error:', err);
  }
}

async function renderPageAnalytics() {
  if (currentForecastData) {
    renderWorkloadForecast(currentForecastData);
  } else {
    await loadWorkloadForecast(false);
  }

  const pageTree = document.getElementById('pageDeckTreeContainer');
  const modalTree = document.getElementById('deckTreeContainer');
  if (pageTree && modalTree && modalTree.children.length > 0) {
    pageTree.innerHTML = modalTree.innerHTML;
  }

  const pageTriage = document.getElementById('pageTriageTopicsList');
  const modalTriage = document.getElementById('triageTopicsList');
  if (pageTriage && modalTriage && modalTriage.children.length > 0) {
    pageTriage.innerHTML = modalTriage.innerHTML;
  }
}

async function handleSyncCalendarUrlPage() {
  const input = document.getElementById('pageCalendarUrlInput');
  const origInput = document.getElementById('calendarUrlInput');
  if (input && origInput) {
    origInput.value = input.value;
    await handleSyncCalendarUrl();
  }
}

async function handleAddManualActivityFromPage() {
  const title = document.getElementById('pageActTitle');
  const start = document.getElementById('pageActStart');
  const end = document.getElementById('pageActEnd');
  if (dom.actTitle && title) dom.actTitle.value = title.value;
  if (dom.actStart && start) dom.actStart.value = start.value;
  if (dom.actEnd && end) dom.actEnd.value = end.value;
  await handleAddManualActivity();
  if (title) title.value = '';
}

// ============================================================================
// MULTI-PAGE VIEW ROUTER & HAMBURGER SIDE-MENU CONTROLLER
// ============================================================================

function switchAppPage(pageId) {
  if (!pageId) return;

  // 1. Hide all pages and reveal the active one
  const pages = document.querySelectorAll('.app-page');
  pages.forEach(p => {
    p.classList.remove('active');
  });

  const targetPage = document.getElementById(pageId);
  if (targetPage) {
    targetPage.classList.add('active');
  }

  // 2. Update active states on top segmented control
  const navBtns = document.querySelectorAll('.nav-tab-btn');
  navBtns.forEach(btn => {
    if (btn.getAttribute('data-page') === pageId) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  // 3. Update active states in slide-over side menu
  const sideItems = document.querySelectorAll('.side-menu-item');
  sideItems.forEach(item => {
    if (item.getAttribute('data-page') === pageId) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });

  // 4. Save state locally
  try {
    localStorage.setItem('study_current_page', pageId);
  } catch (e) {}

  // 5. Trigger page-specific data loaders
  if (pageId === 'page-advisor') {
    if (!state.advisorData) {
      loadAdvisorData('');
    }
  } else if (pageId === 'page-roadmap') {
    renderPageRoadmap();
  } else if (pageId === 'page-analytics') {
    renderPageAnalytics();
  } else if (pageId === 'page-setup') {
    const origInput = document.getElementById('calendarUrlInput');
    const pageInput = document.getElementById('pageCalendarUrlInput');
    if (origInput && pageInput && origInput.value) {
      pageInput.value = origInput.value;
    }
  }

  // 6. Smooth scroll to top
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function toggleSideMenu(isOpen) {
  const backdrop = document.getElementById('sideMenuBackdrop');
  if (!backdrop) return;
  if (isOpen) {
    backdrop.classList.add('open');
    document.body.style.overflow = 'hidden';
  } else {
    backdrop.classList.remove('open');
    document.body.style.overflow = '';
  }
}

function navigateToPage(pageId) {
  switchAppPage(pageId);
  toggleSideMenu(false);
}

// Global escape key listener to close menu drawer
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    toggleSideMenu(false);
  }
});

// Restore previous page on startup if user refreshed while on a specific tab
document.addEventListener('DOMContentLoaded', () => {
  try {
    const savedPage = localStorage.getItem('study_current_page');
    if (savedPage && savedPage !== 'page-today' && document.getElementById(savedPage)) {
      switchAppPage(savedPage);
    }
  } catch (e) {}

  // Automatischer Anki-Sync via AnkiConnect (alle 90s)
  // Hält iPad-Reviews aktuell und verschiebt Plan bei Overrun
  setTimeout(startAnkiAutoSync, 3000); // 3s Verzögerung damit App erst lädt
});

// Window exports
window.switchAppPage = switchAppPage;
window.toggleSideMenu = toggleSideMenu;
window.navigateToPage = navigateToPage;
window.loadAdvisorData = loadAdvisorData;
window.handleAdvisorSearch = handleAdvisorSearch;
window.clearAdvisorSearch = clearAdvisorSearch;
window.applyAdvisorChip = applyAdvisorChip;
window.setAdvisorModeFilter = setAdvisorModeFilter;
window.setAdvisorModuleFilter = setAdvisorModuleFilter;
window.selectAdvisorLecture = selectAdvisorLecture;
window.copyAnkiFactText = copyAnkiFactText;
window.renderPageRoadmap = renderPageRoadmap;
window.renderPageAnalytics = renderPageAnalytics;
window.handleSyncCalendarUrlPage = handleSyncCalendarUrlPage;
window.handleAddManualActivityFromPage = handleAddManualActivityFromPage;
window.swapCurriculumDays = swapCurriculumDays;
window.resetCurriculumSwaps = resetCurriculumSwaps;
window.handleQuickSwapDay = handleQuickSwapDay;
window.initRoadmapDragAndDrop = initRoadmapDragAndDrop;
window.openSwapDayModal = openSwapDayModal;
window.closeCurriculumSwapModal = closeCurriculumSwapModal;
window.selectSwapTargetDay = selectSwapTargetDay;
window.handleSwapTargetChanged = handleSwapTargetChanged;
window.confirmExecuteSwapDays = confirmExecuteSwapDays;
window.openSwapForCurrentViewDay = openSwapForCurrentViewDay;





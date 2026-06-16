// ===== ENTRY POINT =====
import { CONFIG, applyConfig } from './config.js';
import { allProjects, allTasks, allTasks2026, allDetails, setData } from './state.js';
import { renderStatusBadges } from './render/overview.js';
import { renderVysvBlock } from './render/vysv.js';
import { renderDeadlineMap } from './render/deadlines.js';
import { renderTasks, filterTasksByStat, populateTaskFilter } from './render/tasks.js';
import { loadDetail, populateDetailSelect } from './render/detail.js';
import { renderFullProjTable } from './render/projects.js';
import { populateOwnerFilter, applyExecFilters } from './filters.js';
import { showTab } from './nav.js';

function initDashboard(data) {
  const s = data.summary;

  // Timestamp
  document.getElementById('updated-at').textContent = 'Обновлено: ' + data.updated_at;

  // Store globally (use all_tasks for full task coverage)
  setData(data);

  applyConfig(data);
  const yearLabel = document.getElementById('yearLabel');
  if (yearLabel) yearLabel.textContent = CONFIG.year;

  // Gauges (Высвобождение — never filtered)
  renderVysvBlock();

  // KPI cards
  document.getElementById('kpi-projects').textContent = s.projects_total;
  document.getElementById('kpi-projects-sub').innerHTML =
    `<span class="trend up">${s.projects_active} активных</span>&nbsp;/ ${s.projects_closed} закрыто`;

  const activeProjs = data.projects.filter(p => p.status === 'В работе');
  const avgPct = activeProjs.length
    ? Math.round(activeProjs.reduce((sum, p) => sum + (p.pct || 0), 0) / activeProjs.length)
    : 0;
  document.getElementById('kpi-completion').textContent = avgPct + '%';
  document.getElementById('kpi-completion-sub').textContent =
    `среднее по ${activeProjs.length} активным проектам`;

  const overall = data.curators.find(c => c.name === 'Комитет и РЦТ') || data.curators[0];
  if (overall) {
    document.getElementById('kpi-vysv').textContent = overall.pct_vysv + '%';
    document.getElementById('kpi-vysv-sub').innerHTML =
      `<span class="trend ${overall.pct_vysv >= 100 ? 'up' : 'down'}">${overall.pct_vysv >= 100 ? '↑' : '↓'} план</span> ${overall.name}`;
  }

  // Projects screen badge (total unfiltered)
  document.getElementById('badge-projects-total').innerHTML =
    `<div class="dot" style="background:var(--accent)"></div>Всего: ${s.projects_total}`;

  // Tasks screen stats (from summary — not filtered)
  document.getElementById('kpi-deadline14').textContent = s.tasks_deadline_14 ?? '—';
  document.getElementById('kpi-overdue').textContent = s.tasks_overdue ?? '—';

  if ((s.tasks_overdue || 0) === 0) {
    document.getElementById('kpi-overdue-sub').innerHTML = `<span class="trend up">✓</span> Всё в норме`;
  } else {
    document.getElementById('kpi-overdue-sub').innerHTML = `<span class="trend down">!</span> Требует внимания`;
  }

  // Exec filter badges
  renderStatusBadges(allProjects.filter(p => p.deadline && p.deadline.endsWith(String(CONFIG.year))));

  // Tasks stats (computed from 2026 tasks only)
  const tTotal = allTasks2026.length;
  const tActive = allTasks2026.filter(t => t.status === 'В работе').length;
  const tClosed = allTasks2026.filter(t => t.status === 'Закрыта').length;
  const tDeadline14 = allTasks2026.filter(t => (t.urgency === 'overdue' || t.urgency === 'today' || t.urgency === 'urgent' || t.urgency === 'soon') && t.status !== 'Закрыта' && t.status !== 'Выполнено').length;
  const tOverdue = allTasks2026.filter(t => t.urgency === 'overdue' && t.status !== 'Закрыта' && t.status !== 'Выполнено').length;
  document.getElementById('tasks-stat-total').textContent = tTotal;
  document.getElementById('tasks-stat-active').textContent = tActive;
  document.getElementById('tasks-stat-closed').textContent = tClosed;
  document.getElementById('tasks-stat-deadline14').textContent = tDeadline14;
  document.getElementById('tasks-stat-overdue').textContent = tOverdue;

  // Populate dropdowns
  populateOwnerFilter(allProjects);
  populateTaskFilter(allTasks2026);
  populateDetailSelect(allDetails);

  // Static renders
  renderFullProjTable(allProjects);
  renderDeadlineMap(allTasks);
  renderTasks(allTasks2026);

  // Apply exec filters (uses default year/owner=all)
  applyExecFilters();
}

// ===== EVENT LISTENERS SETUP =====
function setupEventListeners() {
  // Tab buttons
  document.querySelectorAll('.tab[data-tab]').forEach(tab => {
    tab.addEventListener('click', () => showTab(tab.dataset.tab));
  });

  // Bottom nav (mobile) — reuse showTab
  document.querySelectorAll('.bottom-tab[data-tab]').forEach(btn => {
    btn.addEventListener('click', () => showTab(btn.dataset.tab));
  });

  // Owner filter
  document.getElementById('ownerFilter').addEventListener('change', applyExecFilters);

  // Project status filter
  document.getElementById('projectStatusFilter').addEventListener('change', (e) => {
    renderFullProjTable(allProjects, e.target.value);
  });

  // Task project filter
  document.getElementById('taskProjectFilter').addEventListener('change', (e) => {
    document.querySelectorAll('.stat-pill').forEach(p => p.classList.remove('selected'));
    document.getElementById('spill-all').classList.add('selected');
    renderTasks(allTasks2026, e.target.value);
  });

  // Detail select
  document.getElementById('detailSelect').addEventListener('change', (e) => {
    loadDetail(e.target.value);
  });

  // Stat pills
  document.querySelectorAll('.stat-pill[data-filter]').forEach(pill => {
    pill.addEventListener('click', () => filterTasksByStat(pill.dataset.filter));
  });

  // Tablist keyboard navigation (WAI-ARIA tabs pattern)
  setupTablistKeyboard();
}

// ===== TABLIST KEYBOARD (arrows + Home/End) =====
function setupTablistKeyboard() {
  const tabs = [...document.querySelectorAll('.nav .tab[role="tab"]')];
  tabs.forEach((tab, i) => {
    tab.addEventListener('keydown', (e) => {
      const map = {
        ArrowRight: (i + 1) % tabs.length,
        ArrowLeft: (i - 1 + tabs.length) % tabs.length,
        Home: 0,
        End: tabs.length - 1,
      };
      if (!(e.key in map)) return;
      e.preventDefault();
      const next = tabs[map[e.key]];
      showTab(next.dataset.tab);
      next.focus();
    });
  });
}

// ===== FETCH DATA =====
// "Unexpected token '<'" at runtime = server returned an HTML error page
// instead of JSON (e.g. 404 from GitHub Pages). We detect this explicitly
// and show a meaningful message instead of a cryptic SyntaxError.
async function loadData() {
  const loader = document.getElementById('loader');
  try {
    const resp = await fetch('data.json');

    const ct = resp.headers.get('content-type') || '';
    const bodyText = await resp.text();

    if (!resp.ok || (!ct.includes('json') && bodyText.trim().startsWith('<'))) {
      const dataUrl = new URL('data.json', location.href).href;
      throw new Error(
        `Сервер вернул HTML вместо JSON (HTTP ${resp.status}).\n` +
        `Проверьте, что файл доступен по адресу:\n${dataUrl}`
      );
    }

    let data;
    try {
      data = JSON.parse(bodyText);
    } catch (parseErr) {
      const pos = parseInt((parseErr.message.match(/position (\d+)/) || [])[1]);
      const snippet = Number.isFinite(pos)
        ? bodyText.slice(Math.max(0, pos - 40), pos + 40)
        : '';
      throw new Error(
        `Ошибка разбора data.json: ${parseErr.message}` +
        (snippet ? `\nФрагмент: …${snippet}…` : '')
      );
    }

    initDashboard(data);
    setupEventListeners();
    loader.style.display = 'none';

  } catch (err) {
    loader.innerHTML = `
      <div style="color:var(--danger);font-family:'Orbitron',sans-serif;font-size:12px;
                  letter-spacing:1px;text-align:center;max-width:460px;padding:0 16px">
        Ошибка загрузки данных
        <pre style="font-size:10px;color:var(--text-dim);font-family:'Exo 2',sans-serif;
                    margin-top:12px;white-space:pre-wrap;text-align:left;
                    background:rgba(255,255,255,0.06);padding:10px;border-radius:8px;
                    word-break:break-all">${err.message}</pre>
      </div>`;
  }
}

// Start
if (typeof document !== 'undefined') {
  loadData();
}

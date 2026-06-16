import { CONFIG } from './config.js';
import { allProjects } from './state.js';
import { renderProjTable, computeTaskKPIs, renderStatusBadges } from './render/overview.js';
import { highlightGauge } from './render/vysv.js';

// ===== POPULATE OWNER FILTER =====
export function populateOwnerFilter(projects) {
  const sel = document.getElementById('ownerFilter');
  const proj2026 = projects.filter(p => p.deadline && p.deadline.split('.')[2] === String(CONFIG.year));
  const owners = [...new Set(proj2026.map(p => p.owner_short).filter(Boolean))].sort();
  owners.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  });
}

// ===== APPLY EXEC FILTERS =====
export function applyExecFilters() {
  const owner = document.getElementById('ownerFilter').value;

  let filtered = allProjects.filter(p => p.deadline && p.deadline.endsWith(String(CONFIG.year)));
  if (owner !== 'all') filtered = filtered.filter(p => p.owner_short === owner);

  const active = filtered.filter(p => p.status === 'В работе');
  const closed = filtered.filter(p => p.status === 'Закрыта');
  const { deadline14, overdue } = computeTaskKPIs(filtered);

  // KPI cards
  document.getElementById('kpi-projects').textContent = filtered.length;
  document.getElementById('kpi-projects-sub').innerHTML =
    `<span class="trend up">${active.length} активных</span>&nbsp;/ ${closed.length} закрыто`;

  const avgPct = active.length
    ? Math.round(active.reduce((s, p) => s + (p.pct || 0), 0) / active.length)
    : 0;
  document.getElementById('kpi-completion').textContent = avgPct + '%';
  document.getElementById('kpi-completion-sub').textContent =
    `среднее по ${active.length} активным проектам`;

  document.getElementById('kpi-deadline14').textContent = deadline14;
  document.getElementById('kpi-overdue').textContent = overdue;
  document.getElementById('kpi-overdue-sub').innerHTML = overdue === 0
    ? `<span class="trend up">✓</span> Всё в норме`
    : `<span class="trend down">!</span> Требует внимания`;

  // Badges
  renderStatusBadges(filtered);

  // Project table (sorted by deadline, all non-closed)
  renderProjTable(filtered);

  // Gauge highlight
  highlightGauge(owner);
}

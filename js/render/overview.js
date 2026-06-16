import { escapeHTML, getProgressColor, getQuarter, byDeadline, CLOSED_STATUSES, Q_COLORS, PRIORITY_STAR, STATUS_COLORS, STATUS_ORDER } from '../helpers.js';
import { allTasks2026 } from '../state.js';
import { goToDetail } from '../nav.js';

export function renderProjTable(projects) {
  const body = document.getElementById('projTableBody');

  const closed = projects.filter(p => CLOSED_STATUSES.has(p.status)).sort(byDeadline);
  const active = projects.filter(p => !CLOSED_STATUSES.has(p.status)).sort(byDeadline);

  const qCounts = {1:0, 2:0, 3:0, 4:0};
  active.forEach(p => { const q = getQuarter(p.deadline); if (q) qCounts[q]++; });

  const renderRow = (p, isClosed) => {
    const q = getQuarter(p.deadline);
    const rowClass = isClosed ? 'row-closed' : (q ? `row-q${q}` : '');
    const pctDisplay = isClosed
      ? `<span style="color:#4caf50;font-weight:700;font-size:12px">✓ Завершён</span>`
      : `<div class="progress-wrap">
           <div class="progress-bar">
             <div class="progress-fill" style="width:${p.pct}%;background:${getProgressColor(p.pct)}"></div>
           </div>
           <span class="progress-pct" style="color:${getProgressColor(p.pct)}">${p.pct}%</span>
         </div>`;
    return `
      <tr data-name="${escapeHTML(p.name)}"${rowClass ? ` class="${rowClass}"` : ''} style="cursor:pointer" title="Двойной клик — детализация">
        <td>${p.is_priority ? PRIORITY_STAR : ''}${escapeHTML(p.name)}</td>
        <td style="color:var(--text-dim);font-size:12px">${escapeHTML(p.owner_short || p.person || '—')}</td>
        <td style="color:var(--text-dim);font-size:12px">${p.deadline || '—'}</td>
        <td>${pctDisplay}</td>
      </tr>`;
  };

  body.innerHTML = [
    ...closed.map(p => renderRow(p, true)),
    ...active.map(p => renderRow(p, false))
  ].join('');

  // Update quarter badges (only active)
  const badgesRow = document.getElementById('qBadgesRow');
  if (badgesRow) {
    badgesRow.innerHTML = [1,2,3,4].map(q => {
      const c = Q_COLORS[q];
      return `<span class="q-badge" style="background:${c.bg};color:${c.color};border:1px solid ${c.border}">Q${q}: ${qCounts[q]}</span>`;
    }).join('');
  }

  // Add double-click handlers
  body.querySelectorAll('tr').forEach(tr => {
    tr.addEventListener('dblclick', () => goToDetail(tr.dataset.name));
  });
}

// ===== COMPUTE TASK KPIs FOR FILTERED PROJECTS =====
export function computeTaskKPIs(filteredProjects) {
  const projNames = new Set(filteredProjects.map(p => p.name));
  const tasks = allTasks2026.filter(t => projNames.has(t.project));
  const deadline14 = tasks.filter(t =>
    (t.urgency === 'overdue' || t.urgency === 'today' || t.urgency === 'urgent' || t.urgency === 'soon')
    && !CLOSED_STATUSES.has(t.status)
  ).length;
  const overdue = tasks.filter(t => t.urgency === 'overdue' && !CLOSED_STATUSES.has(t.status)).length;
  return { deadline14, overdue };
}

export function renderStatusBadges(filtered) {
  const counts = {};
  filtered.forEach(p => { if (p.status) counts[p.status] = (counts[p.status] || 0) + 1; });

  const ordered = [
    ...STATUS_ORDER.filter(s => counts[s]),
    ...Object.keys(counts).filter(s => !STATUS_ORDER.includes(s)),
  ];

  const row = document.getElementById('status-badges-row');
  row.innerHTML = '';
  ordered.forEach(status => {
    const color = STATUS_COLORS[status] || '#888';
    const badge = document.createElement('div');
    badge.className = 'info-badge';
    badge.innerHTML = `<div class="dot" style="background:${color}"></div>${status}: ${counts[status]}`;
    row.appendChild(badge);
  });
}

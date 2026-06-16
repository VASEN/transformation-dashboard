import { escapeHTML, getProgressColor, CLOSED_STATUSES, PRIORITY_STAR } from '../helpers.js';
import { allTasks } from '../state.js';
import { goToDetail } from '../nav.js';

// ===== RENDER: FULL PROJECTS TABLE =====
export function renderFullProjTable(projects, filter = 'all') {
  const body = document.getElementById('fullProjTable');
  const overdueProjects = new Set(allTasks.filter(t => t.urgency === 'overdue' && !CLOSED_STATUSES.has(t.status)).map(t => t.project));
  const todayProjects   = new Set(allTasks.filter(t => t.urgency === 'today'   && !CLOSED_STATUSES.has(t.status)).map(t => t.project));
  const filtered = filter === 'all' ? projects : projects.filter(p => p.status === filter);

  body.innerHTML = filtered.map((p, i) => {
    const isActive = p.status === 'В работе';
    const rowClass = overdueProjects.has(p.name) ? 'row-overdue'
      : todayProjects.has(p.name) ? 'row-today'
      : '';
    return `
      <tr data-name="${escapeHTML(p.name)}"${rowClass ? ' class="' + rowClass + '"' : ''} style="cursor:pointer" title="Двойной клик — детализация">
        <td data-label="#" style="color:var(--text-dim);font-size:11px">${i + 1}</td>
        <td data-label="Проект">${p.is_priority ? PRIORITY_STAR : ''}${escapeHTML(p.name)}</td>
        <td data-label="Статус"><span class="status-badge ${isActive ? 'active' : 'done'}">${escapeHTML(p.status)}</span></td>
        <td data-label="Назначена" style="color:var(--text-dim);font-size:12px">${escapeHTML(p.owner_short || p.person || '—')}</td>
        <td data-label="Срок" style="color:var(--text-dim);font-size:12px">${p.deadline || '—'}</td>
        <td data-label="Готовность">
          <div class="progress-wrap">
            <div class="progress-bar">
              <div class="progress-fill" style="width:${p.pct}%;background:${getProgressColor(p.pct)}"></div>
            </div>
            <span class="progress-pct" style="color:${getProgressColor(p.pct)}">${p.pct}%</span>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  // Add double-click handlers
  body.querySelectorAll('tr').forEach(tr => {
    tr.addEventListener('dblclick', () => goToDetail(tr.dataset.name));
  });
}

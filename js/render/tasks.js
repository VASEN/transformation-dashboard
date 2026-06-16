import { escapeHTML, getProjectStyle, parseDate, byDeadline } from '../helpers.js';
import { allTasks2026 } from '../state.js';
import { CONFIG } from '../config.js';

export function renderTasks(tasks, filter = 'all') {
  const body = document.getElementById('taskTableBody');
  const filtered = (filter === 'all') ? tasks : tasks.filter(t => t.project === filter);

  body.innerHTML = filtered.map(t => {
    const ps = getProjectStyle(t.project);
    const isClosed = t.status === 'Закрыта' || t.status === 'Выполнено';
    const urgencyLabel = isClosed ? 'ok'
      : t.urgency === 'overdue' ? 'urgent'
      : t.urgency === 'today'   ? 'today'
      : t.urgency === 'urgent'  ? 'soon'
      : t.urgency === 'soon'    ? 'soon' : 'ok';
    const urgencyIcon = isClosed ? ''
      : t.urgency === 'overdue' ? '🔴 '
      : t.urgency === 'today'   ? '🔴 '
      : t.urgency === 'urgent'  ? '🟡 ' : '';
    const statusColor = t.status === 'В работе' ? 'var(--accent)' : 'var(--text-dim)';

    const daysLeft = (() => {
      if (!t.deadline || isClosed) return '—';
      const today = new Date(); today.setHours(0,0,0,0);
      const diff = Math.round((parseDate(t.deadline) - today) / 86400000);
      if (diff === 0) return '<span style="color:var(--danger);font-weight:600">сегодня</span>';
      if (diff < 0)  return `<span style="color:var(--danger)">−${Math.abs(diff)} дн</span>`;
      return `<span style="color:var(--text-dim)">+${diff} дн</span>`;
    })();

    return `
      <tr>
        <td><span class="project-tag" style="background:${ps.bg};color:${ps.color}">${escapeHTML(t.project)}</span></td>
        <td style="max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${t.id ? `<a href="${CONFIG.redmineBase}/${t.id}" target="_blank" rel="noopener noreferrer" class="task-link">${escapeHTML(t.theme)}</a>` : escapeHTML(t.theme)}</td>
        <td><span style="color:${statusColor};font-size:12px">${escapeHTML(t.status)}</span></td>
        <td style="color:var(--text-dim);font-size:12px">${escapeHTML(t.executor_short || t.person || '—')}</td>
        <td><span class="deadline-chip ${urgencyLabel}">${urgencyIcon}${t.deadline || '—'}</span></td>
        <td style="font-size:12px;text-align:right;padding-right:8px">${daysLeft}</td>
      </tr>
    `;
  }).join('');
}

// ===== FILTER TASKS BY STAT PILL =====
export function filterTasksByStat(type) {
  document.querySelectorAll('.stat-pill').forEach(p => p.classList.remove('selected'));
  document.getElementById('spill-' + type).classList.add('selected');
  document.getElementById('taskProjectFilter').value = 'all';

  const byProjectThenDeadline = (a, b) =>
    (a.project || '').localeCompare(b.project || '', 'ru') || parseDate(a.deadline) - parseDate(b.deadline);

  let filtered;
  if (type === 'active') {
    filtered = allTasks2026.filter(t => t.status === 'В работе').sort(byProjectThenDeadline);
  } else if (type === 'closed') {
    filtered = allTasks2026.filter(t => t.status === 'Закрыта').sort(byProjectThenDeadline);
  } else if (type === 'deadline14') {
    filtered = allTasks2026
      .filter(t => (t.urgency === 'overdue' || t.urgency === 'today' || t.urgency === 'urgent' || t.urgency === 'soon') && t.status !== 'Закрыта' && t.status !== 'Выполнено')
      .sort(byDeadline);
  } else if (type === 'overdue') {
    filtered = allTasks2026.filter(t => t.urgency === 'overdue' && t.status !== 'Закрыта' && t.status !== 'Выполнено').sort(byDeadline);
  } else {
    filtered = [...allTasks2026].sort(byProjectThenDeadline);
  }
  renderTasks(filtered);
}

// ===== POPULATE TASK PROJECT FILTER =====
export function populateTaskFilter(tasks) {
  const sel = document.getElementById('taskProjectFilter');
  sel.innerHTML = '<option value="all">Все проекты</option>';
  const projects = [...new Set(tasks.map(t => t.project).filter(Boolean))].sort();
  projects.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  });
}

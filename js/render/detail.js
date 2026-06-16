import { escapeHTML, byDeadline, CLOSED_STATUSES } from '../helpers.js';
import { allTasks, allDetails } from '../state.js';
import { CONFIG } from '../config.js';

export function loadDetail(name) {
  const d = allDetails.find(x => x.name === name);
  if (!d) return;

  const planH = d.plan_hours ? Math.round(d.plan_hours).toLocaleString('ru') : '—';
  const planInt = d.plan_hours_cio ? Math.round(d.plan_hours_cio).toLocaleString('ru') : '—';
  const planUnits = d.plan_hours ? (d.plan_hours / CONFIG.hoursPerUnit).toFixed(2) : '—';
  const planIntUnits = d.plan_hours_cio
    ? (d.plan_hours_cio / CONFIG.hoursPerUnit).toFixed(2) : '—';
  const planExtVal = (d.plan_hours && d.plan_hours_cio != null)
    ? d.plan_hours - d.plan_hours_cio : null;
  const planExtH = planExtVal != null
    ? Math.round(planExtVal).toLocaleString('ru') : '—';
  const planExtUnits = planExtVal != null
    ? (planExtVal / CONFIG.hoursPerUnit).toFixed(2) : '—';

  const teamArr = d.team ? d.team.split(',').map(s => s.trim()).filter(Boolean) : [];
  const indicatorsArr = d.indicators
    ? d.indicators.split('\n').map(s => s.trim()).filter(Boolean)
    : [];

  // Determine active ETAPs from tasks (tasks "В работе" grouped by parent_id)
  const statusText = (d.current_status || '').trim();
  const currentStages = (() => {
    const projTasks = allTasks.filter(t => t && t.project === name);
    if (!projTasks.length) return [];

    // Group tasks by parent_id; find groups with at least one "В работе"
    const groups = {};
    projTasks.forEach(t => {
      const pid = t.parent_id || '__root__';
      if (!groups[pid]) groups[pid] = [];
      groups[pid].push(t);
    });

    const activeGroups = Object.values(groups).filter(g =>
      g.some(t => t.status === 'В работе')
    );
    if (!activeGroups.length) return [];

    // Build ЭТАП label map from status_text: "ЭТАП N ..." → label
    const etapMap = {};
    if (statusText) {
      const rx = /ЭТАП\s+(\d+)[.:\s]+([^\n;]+)/gi;
      let m;
      while ((m = rx.exec(statusText)) !== null) {
        etapMap[m[1]] = `ЭТАП ${m[1]}: ${m[2].trim()}`;
      }
    }

    const stageEntries = []; // { num: Number, label: String }

    activeGroups.forEach(g => {
      const sampleTheme = g[0].theme || '';
      const numMatch = sampleTheme.match(/^(\d+)\./);
      const etapNum = numMatch ? numMatch[1] : null;
      const numInt = etapNum ? parseInt(etapNum, 10) : null;

      let label;
      if (etapNum && etapMap[etapNum]) {
        label = etapMap[etapNum];
      } else if (etapNum) {
        label = `ЭТАП ${etapNum}`;
      } else {
        const activeTask = g.find(t => t.status === 'В работе');
        label = activeTask ? activeTask.theme : null;
      }

      if (label && !stageEntries.find(e => e.label === label)) {
        stageEntries.push({ num: numInt ?? 9999, label });
      }
    });

    // Sort by ЭТАП number ascending
    stageEntries.sort((a, b) => a.num - b.num);
    return stageEntries.map(e => e.label);
  })();

  const isClosed = CLOSED_STATUSES.has(d.status);

  // Текущий этап
  const currentStageHTML = isClosed
    ? `<div style="padding:9px 14px;background:rgba(76,175,80,0.12);border-left:3px solid #4caf50;border-radius:0 8px 8px 0;font-size:13px;font-weight:600;color:#4caf50">✓ Реализован</div>`
      + (d.defense_at ? `<div style="padding:6px 14px;font-size:12px;color:var(--text-dim);margin-top:4px">Защищён: <span style="color:var(--text);font-weight:600">${d.defense_at}</span></div>` : '')
    : currentStages.length
      ? currentStages.map(s => `<div style="padding:9px 14px;background:rgba(0,229,255,0.09);border-left:3px solid var(--accent);border-radius:0 8px 8px 0;margin-bottom:6px;font-size:13px;line-height:1.5;font-weight:500">${s}</div>`).join('')
      : `<div style="padding:9px 14px;background:rgba(255,255,255,0.04);border-left:3px solid rgba(255,255,255,0.15);border-radius:0 8px 8px 0;font-size:13px;color:var(--text-dim)">Нет данных</div>`;

  // Full status lines for block 2
  const statusFullLines = statusText
    ? statusText.split('\n').map(s => s.trim()).filter(Boolean)
    : [];
  const statusArr = d.current_status
    ? d.current_status.split('\n').map(s => s.trim()).filter(Boolean)
    : ['Нет данных'];
  const problemArr = d.problem
    ? d.problem.split('\n').map(s => s.trim()).filter(Boolean)
    : [];

  const grid = document.getElementById('detailGrid');
  grid.innerHTML = `
    <!-- LEFT: info + team -->
    <div style="display:flex;flex-direction:column;gap:16px">
      <div class="info-block">
        <div class="info-label">Держатель проекта</div>
        <div class="info-value" style="font-size:20px;font-weight:700">${d.owner_short || d.owner || '—'}</div>
        <div class="info-label">Руководитель проекта</div>
        <div class="info-value" style="color:var(--accent2);font-size:20px;font-weight:700">${d.manager_short || d.manager || '—'}</div>
        <div class="info-label">Срок завершения</div>
        <div class="info-value" style="color:var(--warn);font-size:20px;font-weight:700">${d.deadline || '—'}</div>

        <div style="margin-top:12px">
          <div class="section-title" style="margin-bottom:12px">Высвобождение часов</div>
          <div class="hours-visual">
            <div class="hour-box">
              <div class="hour-num" style="color:var(--accent)">${planH}</div>
              <div class="hour-lbl">план всего</div>
            </div>
            <div class="hour-box">
              <div class="hour-num" style="color:var(--accent2)">${planUnits}</div>
              <div class="hour-lbl">план шт.ед.</div>
            </div>
            <div class="hour-box">
              <div class="hour-num" style="color:var(--accent)">${planInt}</div>
              <div class="hour-lbl">внутреннее</div>
            </div>
            <div class="hour-box">
              <div class="hour-num" style="color:var(--accent2)">${planIntUnits}</div>
              <div class="hour-lbl">внутр. шт.ед.</div>
            </div>
            <div class="hour-box">
              <div class="hour-num" style="color:var(--accent)">${planExtH}</div>
              <div class="hour-lbl">внешнее</div>
            </div>
            <div class="hour-box">
              <div class="hour-num" style="color:var(--accent2)">${planExtUnits}</div>
              <div class="hour-lbl">внешн. шт.ед.</div>
            </div>
          </div>
        </div>
      </div>

      <div class="info-block">
        <div class="section-title" style="margin-bottom:12px">Команда проекта</div>
        ${teamArr.length
          ? teamArr.map(m => `<div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06);font-size:13px">${escapeHTML(m)}</div>`).join('')
          : '<div style="color:var(--text-dim);font-size:13px">—</div>'}
      </div>
    </div>

    <!-- MIDDLE: status + goal -->
    <div style="display:flex;flex-direction:column;gap:16px">
      <div class="info-block">
        <div class="section-title" style="margin-bottom:12px">Актуальный статус</div>

        <!-- Sub-block 1: current stages -->
        <div style="margin-bottom:12px">
          <div style="font-size:11px;font-weight:700;letter-spacing:.08em;color:var(--accent);text-transform:uppercase;margin-bottom:8px">Текущий этап</div>
          ${currentStageHTML}
        </div>

        <!-- Sub-block 2: full status -->
        <div>
          <div style="font-size:11px;font-weight:700;letter-spacing:.08em;color:var(--accent2);text-transform:uppercase;margin-bottom:8px">Статус проекта</div>
          ${statusFullLines.length
            ? statusFullLines.map(s => {
                const isStage = /^(ЭТАП\s+\d+|Подпроект|Текущий этап)/i.test(s);
                const isBullet = /^\d+\./.test(s);
                const bg = isStage ? 'rgba(100,220,100,0.07)' : 'transparent';
                const border = isStage ? 'border-left:2px solid var(--accent2);padding-left:10px;' : isBullet ? 'padding-left:14px;' : '';
                return `<div style="font-size:12px;line-height:1.6;${border}background:${bg};border-radius:4px;margin-bottom:3px;color:${isStage?'var(--accent2)':'var(--text)'}">${escapeHTML(s)}</div>`;
              }).join('')
            : `<div style="font-size:13px;color:var(--text-dim)">Нет данных</div>`}
        </div>
      </div>

      <div class="info-block" style="flex:1">
        <div class="section-title" style="margin-bottom:16px">Критически важная цель</div>
        <div class="big-goal">${escapeHTML(d.goal || '—')}</div>
      </div>

      ${problemArr.length ? `
      <div class="info-block">
        <div class="section-title" style="margin-bottom:12px">Описание проекта</div>
        ${problemArr.map((s, i) => `<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05)"><span style="color:var(--accent);font-weight:700;font-size:11px">${i+1}.</span><span style="font-size:13px">${escapeHTML(s)}</span></div>`).join('')}
      </div>` : ''}
    </div>

    <!-- RIGHT: indicators -->
    <div class="info-block">
      <div class="section-title" style="margin-bottom:16px">Опережающие показатели</div>
      <div class="indicators-list">
        ${indicatorsArr.length
          ? indicatorsArr.map((ind, i) => `
            <div class="indicator-item">
              <span class="indicator-num">${i + 1}</span>
              <span class="indicator-text">${escapeHTML(ind)}</span>
            </div>
          `).join('')
          : '<div style="color:var(--text-dim);font-size:13px">—</div>'}
      </div>
    </div>
  `;
}

// ===== POPULATE DETAIL SELECT =====
export function populateDetailSelect(details) {
  const sel = document.getElementById('detailSelect');
  sel.innerHTML = '';

  const proj2026 = details.filter(d => d.deadline && d.deadline.split('.')[2] === String(CONFIG.year));
  const closed = proj2026.filter(d => CLOSED_STATUSES.has(d.status)).sort(byDeadline);
  const active = proj2026.filter(d => !CLOSED_STATUSES.has(d.status)).sort(byDeadline);

  closed.forEach(d => {
    const opt = document.createElement('option');
    opt.value = d.name;
    opt.textContent = '✓ ' + (d.is_priority ? '★ ' : '') + d.name;
    sel.appendChild(opt);
  });
  active.forEach(d => {
    const opt = document.createElement('option');
    opt.value = d.name;
    opt.textContent = (d.is_priority ? '★ ' : '') + d.name;
    sel.appendChild(opt);
  });

  const first = closed[0] || active[0];
  if (first) loadDetail(first.name);
}

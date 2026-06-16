function getMonday(d) {
  const day = d.getDay();
  const diff = (day === 0 ? -6 : 1 - day);
  const monday = new Date(d);
  monday.setDate(d.getDate() + diff);
  monday.setHours(0, 0, 0, 0);
  return monday;
}

export function renderDeadlineMap(tasks) {
  const map = document.getElementById('deadlineMap');
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const monday = getMonday(today);

  const weeks = [];
  for (let i = 0; i < 6; i++) {
    const start = new Date(monday);
    start.setDate(monday.getDate() + i * 7);
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    const sm = start.toLocaleString('ru', { day: 'numeric', month: 'short' });
    const em = end.toLocaleString('ru', { day: 'numeric', month: 'short' });
    const label = start.getMonth() === end.getMonth()
      ? `${start.getDate()}–${end.getDate()} ${start.toLocaleString('ru', { month: 'short' })}`
      : `${sm}–${em}`;
    weeks.push({ start, end, label, counts: [0, 0, 0, 0, 0, 0, 0], total: 0 });
  }

  tasks.forEach(t => {
    if (!t.deadline) return;
    const [dd, mm, yyyy] = t.deadline.split('.');
    const d = new Date(+yyyy, +mm - 1, +dd);
    weeks.forEach(w => {
      if (d >= w.start && d <= w.end) {
        const dayIdx = (d.getDay() + 6) % 7;
        w.counts[dayIdx]++;
        w.total++;
      }
    });
  });

  const days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
  map.innerHTML = `
    <div class="week-row">
      <div class="week-label"></div>
      <div class="week-bar-wrap">
        ${days.map(d => `<div style="flex:1;text-align:center;font-size:9px;color:var(--text-dim);letter-spacing:0.5px">${d}</div>`).join('')}
      </div>
      <div class="week-count"></div>
    </div>
  ` + weeks.map(w => {
    const maxDay = Math.max(...w.counts, 1);
    return `
      <div class="week-row">
        <div class="week-label">${w.label}</div>
        <div class="week-bar-wrap">
          ${w.counts.map(c => {
            const alpha = c > 0 ? (c / maxDay * 0.7 + 0.15) : 0;
            const col = c >= 5 ? `rgba(255,59,92,${alpha})` : c >= 3 ? `rgba(255,184,0,${alpha})` : `rgba(0,229,255,${alpha})`;
            return `<div class="day-cell" style="background:${col}" title="${c} задач"></div>`;
          }).join('')}
        </div>
        <div class="week-count" style="color:${w.total >= 15 ? 'var(--danger)' : w.total >= 8 ? 'var(--warn)' : 'var(--text-dim)'}">${w.total}</div>
      </div>
    `;
  }).join('') + `
    <div style="display:flex;gap:14px;padding:8px 0 2px;margin-top:4px;border-top:1px solid rgba(255,255,255,0.06)">
      <div style="display:flex;align-items:center;gap:5px;font-size:10px;color:var(--text-dim)">
        <span style="width:10px;height:10px;border-radius:2px;background:rgba(0,229,255,0.55);display:inline-block;flex-shrink:0"></span>1–2 задачи
      </div>
      <div style="display:flex;align-items:center;gap:5px;font-size:10px;color:var(--text-dim)">
        <span style="width:10px;height:10px;border-radius:2px;background:rgba(255,184,0,0.65);display:inline-block;flex-shrink:0"></span>3–4 задачи
      </div>
      <div style="display:flex;align-items:center;gap:5px;font-size:10px;color:var(--text-dim)">
        <span style="width:10px;height:10px;border-radius:2px;background:rgba(255,59,92,0.65);display:inline-block;flex-shrink:0"></span>5+ задач
      </div>
    </div>
  `;
}

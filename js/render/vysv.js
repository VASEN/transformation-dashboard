import { getGaugeColor } from '../helpers.js';
import { allCurators } from '../state.js';
import { CONFIG } from '../config.js';

function _gaugeSVG(pct_vysv) {
  const radius = 40, cx = 50, cy = 55;
  const color = getGaugeColor(pct_vysv);
  const pct = Math.min(pct_vysv, 200) / 200;
  const a0 = -Math.PI, a1 = a0 + pct * Math.PI;
  const x1 = cx + radius * Math.cos(a0), y1 = cy + radius * Math.sin(a0);
  const x2 = cx + radius * Math.cos(a1), y2 = cy + radius * Math.sin(a1);
  return `<svg class="gauge-svg" viewBox="0 0 100 65">
    <path d="M ${cx-radius},${cy} A ${radius},${radius} 0 0 1 ${cx+radius},${cy}"
      fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="8" stroke-linecap="round"/>
    <path d="M ${x1},${y1} A ${radius},${radius} 0 0 1 ${x2},${y2}"
      fill="none" stroke="${color}" stroke-width="8" stroke-linecap="round"
      style="filter:drop-shadow(0 0 6px ${color})"/>
    <text x="50" y="52" text-anchor="middle" font-family="Orbitron,sans-serif"
      font-size="13" font-weight="700" fill="${color}">${pct_vysv}%</text>
  </svg>`;
}

function _vysvDetailHTML(curator) {
  const fmtH = h => h != null ? Math.round(h).toLocaleString('ru') + ' ч' : '—';
  const fmtN = v => v != null ? v : '—';
  const planMinus20 = curator.plan_minus20 != null ? (Math.round(curator.plan_minus20 * 10) / 10) + ' шт.ед.' : '—';
  const vysvUnits   = curator.vysv_units   != null ? (Math.round(curator.vysv_units * 10) / 10)   + ' шт.ед.' : '—';

  const pct = curator.pct_vysv;
  const pctColor = pct === 100 ? 'var(--warn)' : pct > 100 ? 'var(--accent3)' : 'var(--danger)';
  const pctStr   = pct != null ? pct + '%' : '—';

  const intH = curator.vysv_internal_hours;
  const extH = curator.vysv_external_hours;

  const BASE = 'min-width:0;overflow:hidden;word-break:break-word;padding:5px 8px;background:rgba(255,255,255,0.03);border-radius:6px';
  const LBL  = 'font-size:10px;color:var(--text-dim)';
  const VAL  = 'font-size:13px;font-weight:700;color:var(--text)';

  // simple cell: label top, value bottom
  const cell = (lbl, val) =>
    `<div style="${BASE}">
      <div style="${LBL};margin-bottom:2px">${lbl}</div>
      <div style="${VAL}">${val}</div>
    </div>`;

  // combined cell: label + two sub-rows (e.g. ККП plan/fact)
  const cellDuo = (lbl, row1lbl, row1val, row2lbl, row2val) =>
    `<div style="${BASE}">
      <div style="${LBL};margin-bottom:4px">${lbl}</div>
      <div style="display:flex;justify-content:space-between;gap:4px;margin-bottom:2px">
        <span style="font-size:10px;color:var(--text-dim)">${row1lbl}</span>
        <span style="${VAL}">${row1val}</span>
      </div>
      <div style="display:flex;justify-content:space-between;gap:4px">
        <span style="font-size:10px;color:var(--text-dim)">${row2lbl}</span>
        <span style="${VAL}">${row2val}</span>
      </div>
    </div>`;

  // vysv cell: label, hours large, units small below
  const vysvCell = (lbl, h) => {
    const u = h != null ? (h / CONFIG.hoursPerUnit).toFixed(1) + ' шт.ед.' : null;
    return `<div style="${BASE}">
      <div style="${LBL};margin-bottom:4px">${lbl}</div>
      <div style="font-size:14px;font-weight:700;color:var(--text)">${h != null ? fmtH(h) : '—'}</div>
      ${u ? `<div style="font-size:10px;color:var(--text-dim);margin-top:2px">${u}</div>` : ''}
    </div>`;
  };

  return `
    <div class="vysv-detail-title">${curator.name}</div>

    <div style="font-size:9px;font-weight:700;letter-spacing:1px;color:var(--text-dim);text-transform:uppercase;margin-bottom:6px">Кадры</div>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:5px;margin-bottom:12px">
      ${cell('Штат', fmtN(curator.headcount))}
      ${cellDuo('ККП', 'Штат', fmtN(curator.kkp), 'Факт', fmtN(curator.kkp_fact))}
      ${cell('Итого факт', fmtN(curator.fact_total))}
      ${cellDuo('РЦТ', 'Штат', fmtN(curator.rct), 'Факт', fmtN(curator.rct_fact))}
      ${cell('План −20%', planMinus20)}
      ${cell('Вакансии', fmtN(curator.vacancies))}
    </div>

    <div style="font-size:9px;font-weight:700;letter-spacing:1px;color:var(--text-dim);text-transform:uppercase;margin-bottom:6px">Высвобождение</div>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:5px;margin-bottom:10px">
      ${vysvCell('Внутреннее', intH)}
      ${vysvCell('Внешнее', extH)}
    </div>

    <div class="vysv-detail-accent">
      <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:2px">
        <div style="font-family:'Orbitron',sans-serif;font-size:28px;font-weight:700;color:${pctColor}">${pctStr}</div>
        <div style="font-size:10px;color:var(--text-dim)">% высвобождения</div>
      </div>
      <div style="flex:1;display:flex;flex-direction:column;gap:5px;justify-content:center">
        <div style="font-size:11px;color:var(--text-dim)">План: <span style="color:var(--text);font-weight:600">${planMinus20}</span></div>
        <div style="font-size:11px;color:var(--text-dim)">Факт: <span style="color:var(--text);font-weight:600">${vysvUnits}</span></div>
      </div>
    </div>`;
}

export function renderVysvBlock(selectedName) {
  const grid = document.getElementById('vysvGrid');
  if (!grid || !allCurators || !allCurators.length) return;

  const norm = s => (s || '').toLowerCase().replace(/ё/g, 'е');
  const komitet = allCurators.find(c => c.name === 'Комитет и РЦТ') || allCurators[0];

  // Resolve target curator from owner filter name or curator name
  let target = komitet;
  if (selectedName && selectedName !== 'all') {
    const ln = norm(selectedName).split(' ')[0];
    target = allCurators.find(c => norm(c.name).includes(ln)) || komitet;
  }

  // 1. Render grid structure once (detail panel + all cards)
  if (!document.getElementById('vysvDetailPanel')) {
    let html = `<div class="vysv-detail" id="vysvDetailPanel" style="grid-column:1/-1"></div>`;
    allCurators.forEach(c => {
      html += `<div class="gauge-card" data-curator-name="${c.name}">
        <div class="gauge-name">${c.name}</div>
        <div class="gauge-wrap">${_gaugeSVG(c.pct_vysv)}</div>
      </div>`;
    });
    grid.innerHTML = html;

    // Attach click handlers once
    grid.querySelectorAll('.gauge-card').forEach(card => {
      card.addEventListener('click', () => {
        if (document.getElementById('ownerFilter').value !== 'all') return;
        renderVysvBlock(card.dataset.curatorName);
      });
    });
  }

  // 2. Update highlight — selected card gets accent border, others plain
  grid.querySelectorAll('.gauge-card').forEach(card => {
    card.classList.toggle('highlighted', card.dataset.curatorName === target.name);
  });

  // 3. Update detail panel content only
  const panel = document.getElementById('vysvDetailPanel');
  if (panel) panel.innerHTML = _vysvDetailHTML(target);
}

// ===== GAUGE HIGHLIGHT =====
export function highlightGauge(selectedOwner) {
  renderVysvBlock(selectedOwner);
}

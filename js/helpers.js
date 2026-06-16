export function escapeHTML(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

export function getProgressColor(pct) {
  if (pct <= 30) return '#ff3b5c';
  if (pct <= 70) return '#ffb800';
  return '#00ff9d';
}

export function getGaugeColor(pct) {
  if (pct >= 120) return '#00ff9d';
  if (pct >= 100) return '#00e5ff';
  return '#ff3b5c';
}

// Assign a stable color per project name
const PROJECT_PALETTE = [
  { bg: 'rgba(0,229,255,0.12)', color: '#00e5ff' },
  { bg: 'rgba(180,79,255,0.12)', color: '#b44fff' },
  { bg: 'rgba(0,255,157,0.12)', color: '#00ff9d' },
  { bg: 'rgba(255,184,0,0.12)', color: '#ffb800' },
  { bg: 'rgba(255,59,92,0.12)', color: '#ff3b5c' },
  { bg: 'rgba(100,180,255,0.12)', color: '#64b4ff' },
];
const projectColorCache = {};
let paletteIdx = 0;
export function getProjectStyle(name) {
  if (!projectColorCache[name]) {
    projectColorCache[name] = PROJECT_PALETTE[paletteIdx % PROJECT_PALETTE.length];
    paletteIdx++;
  }
  return projectColorCache[name];
}

// ===== HELPERS: parse date dd.mm.yyyy → Date =====
export function parseDate(str) {
  if (!str) return new Date(9999, 0, 1);
  const [dd, mm, yyyy] = str.split('.');
  return new Date(+yyyy, +mm - 1, +dd);
}

// ===== HELPERS: quarter from deadline =====
export function getQuarter(deadlineStr) {
  if (!deadlineStr) return null;
  const month = parseInt((deadlineStr.split('.'))[1], 10);
  if (!month) return null;
  return month <= 3 ? 1 : month <= 6 ? 2 : month <= 9 ? 3 : 4;
}

export const Q_COLORS = {
  1: { color: '#7c6af7', bg: 'rgba(124,106,247,0.12)', border: 'rgba(124,106,247,0.3)' },
  2: { color: '#00e5ff', bg: 'rgba(0,229,255,0.12)',   border: 'rgba(0,229,255,0.3)' },
  3: { color: '#00ff9d', bg: 'rgba(0,255,157,0.12)',   border: 'rgba(0,255,157,0.3)' },
  4: { color: '#ffb800', bg: 'rgba(255,184,0,0.12)',   border: 'rgba(255,184,0,0.3)' },
};
export const CLOSED_STATUSES = new Set(['Закрыта', 'Закрыто', 'Выполнено', 'Выполнена', 'Завершена']);
export const PRIORITY_STAR = '<span class="priority-marker" title="Приоритетный проект">★</span>';
export const byDeadline = (a, b) => parseDate(a.deadline) - parseDate(b.deadline);

// ===== STATUS BADGES =====
export const STATUS_COLORS = {
  'В работе':    '#00bcd4',
  'Новая':       '#7c6af7',
  'Закрыта':     '#4caf50',
  'Выполнено':   '#4caf50',
  'На проверке': '#ff9800',
};
export const STATUS_ORDER = ['В работе', 'Новая', 'На проверке', 'Выполнено', 'Закрыта'];

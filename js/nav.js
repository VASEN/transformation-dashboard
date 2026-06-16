import { loadDetail } from './render/detail.js';

// ===== TAB SWITCHING =====
export function showTab(name) {
  document.querySelectorAll('.tab, .bottom-tab').forEach(t => {
    const isActive = t.dataset.tab === name;
    t.classList.toggle('active', isActive);
    if (t.classList.contains('tab')) t.setAttribute('aria-selected', isActive ? 'true' : 'false');
    if (t.classList.contains('bottom-tab')) {
      if (isActive) t.setAttribute('aria-current', 'page');
      else t.removeAttribute('aria-current');
    }
  });
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  const screen = document.getElementById('screen-' + name);
  if (screen) screen.classList.add('active');
}

// ===== NAVIGATE TO DETAIL TAB WITH PROJECT FILTER =====
export function goToDetail(name) {
  showTab('detail');
  const sel = document.getElementById('detailSelect');
  if (sel) {
    sel.value = name;
    loadDetail(name);
  }
}

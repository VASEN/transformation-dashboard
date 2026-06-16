import { loadDetail } from './render/detail.js';

// ===== TAB SWITCHING =====
export function showTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.querySelector(`.tab[data-tab="${name}"]`).classList.add('active');
  document.getElementById('screen-' + name).classList.add('active');
}

// ===== NAVIGATE TO DETAIL TAB WITH PROJECT FILTER =====
export function goToDetail(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  const detailTab = document.querySelector('.tab[data-tab="detail"]');
  if (detailTab) detailTab.classList.add('active');
  document.getElementById('screen-detail').classList.add('active');
  const sel = document.getElementById('detailSelect');
  if (sel) {
    sel.value = name;
    loadDetail(name);
  }
}

# Фаза 2 · D4 — Модуляризация index.html (План реализации)

> **Для исполнителя (агента):** пошаговое выполнение; шаги — чекбоксы (`- [ ]`). Каждая задача завершается верификацией и коммитом.

**Goal:** Разбить монолит `index.html` (2019 строк) на `index.html` + `css/styles.css` + ES-модули `js/*` по функциям — **без изменения логики и внешнего вида**.

**Architecture:** Стратегия «строим рядом, переключаем последним»: сначала безопасно выносим CSS и весь JS в отдельные файлы (классический `<script>`, глобальная область — поведение 1:1). Затем создаём ES-модули (контент берём из вынесенного `app.js`), пока сайт продолжает работать на `app.js`. В финале переключаем `index.html` на `<script type="module" src="js/main.js">`, удаляем `app.js`, проверяем идентичность.

**Tech Stack:** статический HTML/CSS/vanilla-JS (ES-модули, без сборщика), Node для синтакс-проверки.

**Ветка:** `phase2-design` (создана; спека закоммичена).

**Критерий приёмки D4:** дашборд визуально и по цифрам идентичен (36/613/5, 17 просрочено, 122%); `node --check` каждого модуля чист; граф импортов резолвится (`node import('./js/main.js')`); 22 pytest Фазы 1 не затронуты.

> **Важно (ES-модули и `file://`):** после D4 `index.html` открывается только по http (локальный сервер / Amvera), не как файл. Это согласовано в спеке.

---

## Карта модулей (symbol → дом)

Эта таблица — контракт: где какой общий символ объявлен и экспортируется. Импортируй символ из его дома.

| Модуль | Экспортирует | Импортирует из |
|---|---|---|
| `js/config.js` | `CONFIG`, `applyConfig(data)` | — |
| `js/helpers.js` | `escapeHTML`, `getProgressColor`, `getGaugeColor`, `getProjectStyle`, `parseDate`, `getQuarter`, `byDeadline`, `Q_COLORS`, `CLOSED_STATUSES`, `PRIORITY_STAR`, `STATUS_COLORS`, `STATUS_ORDER` | — |
| `js/state.js` | `allProjects`, `allTasks`, `allTasks2026`, `allDetails`, `allCurators`, `setData(data)` | `config.js` (CONFIG) |
| `js/render/overview.js` | `renderProjTable`, `computeTaskKPIs`, `renderStatusBadges` | helpers, state, nav (`goToDetail`) |
| `js/render/vysv.js` | `renderVysvBlock`, `highlightGauge` | helpers (`getGaugeColor`), state (`allCurators`), config (`CONFIG`) |
| `js/render/deadlines.js` | `renderDeadlineMap` | helpers (`parseDate`, `getProjectStyle`), state |
| `js/render/tasks.js` | `renderTasks`, `filterTasksByStat`, `populateTaskFilter` | helpers, state, config (`CONFIG`) |
| `js/render/detail.js` | `loadDetail`, `populateDetailSelect` | helpers, state, config (`CONFIG`) |
| `js/render/projects.js` | `renderFullProjTable` | helpers, state, nav (`goToDetail`) |
| `js/filters.js` | `populateOwnerFilter`, `applyExecFilters` | helpers, state, render/* (вызывает рендеры) |
| `js/nav.js` | `showTab`, `goToDetail` | render/detail (`loadDetail`) |
| `js/main.js` | — (точка входа) | всё: config, state, render/*, filters, nav |

> `paletteIdx`, `projectColorCache`, `PROJECT_PALETTE` — внутренние для `helpers.js` (не экспортируются; нужны только `getProjectStyle`). `getMonday` — внутренняя для `deadlines.js`. `_gaugeSVG`/`_vysvDetailHTML` — внутренние для `vysv.js`.

---

## Task 1: Вынести CSS → `css/styles.css`

**Files:**
- Create: `css/styles.css`
- Modify: `index.html` (строки 7–789 — блок `<style>…</style>`)

- [ ] **Step 1: Создать каталог и перенести содержимое `<style>`**

Перенести содержимое между `<style>` (стр. 7) и `</style>` (стр. 789) — **без** самих тегов — в `css/styles.css` (включая `@import` Google Fonts первой строкой).

- [ ] **Step 2: Заменить блок `<style>` в `index.html` на ссылку**

В `<head>` вместо всего блока `<style>…</style>`:

```html
<link rel="stylesheet" href="css/styles.css">
```

- [ ] **Step 3: Проверка (сервер + глаза)**

Run: `python3 -m http.server 8347 --bind 127.0.0.1` (если не запущен) и открыть `http://127.0.0.1:8347/`.
Expected: дашборд выглядит идентично (стили подхватились).
Доп.: `grep -c "<style>" index.html` → `0`; `test -s css/styles.css && echo "css ok"` → `css ok`.

- [ ] **Step 4: Коммит**

```bash
git add index.html css/styles.css
git commit -m "refactor(ui): вынести CSS в css/styles.css [D4]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Вынести JS → `js/app.js` (классический script, безопасный чекпойнт)

**Files:**
- Create: `js/app.js`
- Modify: `index.html` (строки 1019–1995 — блок `<script>…</script>`)

- [ ] **Step 1: Перенести содержимое `<script>` в `js/app.js`**

Перенести код между `<script>` (стр. 1019) и `</script>` (стр. 1995) — **без** тегов — в `js/app.js`. Глобальная область сохраняется (классический скрипт), поведение 1:1.

- [ ] **Step 2: Заменить блок `<script>` в `index.html` на ссылку**

В конце `<body>` вместо всего блока `<script>…</script>`:

```html
<script src="js/app.js"></script>
```

- [ ] **Step 3: Синтаксис + идентичность**

Run: `node --check js/app.js && echo "JS SYNTAX OK"` → `JS SYNTAX OK`.
Открыть `http://127.0.0.1:8347/` — дашборд работает идентично (все вкладки, фильтры, гейджи, ссылки).
Доп.: `grep -c "<script>" index.html` → `0` (остался только `<script src=...>`).

- [ ] **Step 4: Коммит**

```bash
git add index.html js/app.js
git commit -m "refactor(ui): вынести JS в js/app.js (классический script) [D4]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Листовые ES-модули — `config.js`, `helpers.js`, `state.js`

> Создаём модули рядом; `index.html` пока работает на `js/app.js`. Контент берём из `js/app.js`.

**Files:**
- Create: `js/config.js`, `js/helpers.js`, `js/state.js`

- [ ] **Step 1: `js/config.js`**

```javascript
export const CONFIG = {
  year: 2026,
  hoursPerUnit: 1972,
  redmineBase: 'https://transformation.rm.mosreg.ru/#/issues',
};

export function applyConfig(data) {
  if (data && data.config) {
    CONFIG.year = data.config.year ?? CONFIG.year;
    CONFIG.hoursPerUnit = data.config.hours_per_unit ?? CONFIG.hoursPerUnit;
    CONFIG.redmineBase = data.config.redmine_base ?? CONFIG.redmineBase;
  }
}
```

> Это заменяет в `app.js` объявление `let CONFIG = {...}` и блок присваивания `CONFIG = {...}` из `initDashboard` (теперь — мутация на месте через `applyConfig`).

- [ ] **Step 2: `js/helpers.js`**

Перенести из `app.js` тела функций/констант: `escapeHTML`, `getProgressColor`, `getGaugeColor`, `PROJECT_PALETTE`, `projectColorCache`, `paletteIdx`, `getProjectStyle`, `parseDate`, `getQuarter`, `byDeadline`, `Q_COLORS`, `CLOSED_STATUSES`, `PRIORITY_STAR`, `STATUS_COLORS`, `STATUS_ORDER`. Добавить `export` перед каждым, что в таблице помечено как экспорт (`PROJECT_PALETTE`/`projectColorCache`/`paletteIdx` — БЕЗ export). Шаблон:

```javascript
export function escapeHTML(s) { /* тело без изменений */ }
export function getProgressColor(pct) { /* … */ }
export function getGaugeColor(pct) { /* … */ }
const PROJECT_PALETTE = [ /* … */ ];
const projectColorCache = {};
let paletteIdx = 0;
export function getProjectStyle(name) { /* … */ }
export function parseDate(str) { /* … */ }
export function getQuarter(deadlineStr) { /* … */ }
export const byDeadline = (a, b) => parseDate(a.deadline) - parseDate(b.deadline);
export const Q_COLORS = { /* … */ };
export const CLOSED_STATUSES = new Set(['Закрыта', 'Закрыто', 'Выполнено', 'Выполнена', 'Завершена']);
export const PRIORITY_STAR = '<span class="priority-marker" title="Приоритетный проект">★</span>';
export const STATUS_COLORS = { /* … */ };
export const STATUS_ORDER = ['В работе', 'Новая', 'На проверке', 'Выполнено', 'Закрыта'];
```

- [ ] **Step 3: `js/state.js`**

```javascript
import { CONFIG } from './config.js';

export let allProjects = [];
export let allTasks = [];
export let allTasks2026 = [];
export let allDetails = [];
export let allCurators = [];

export function setData(data) {
  allProjects = data.projects;
  allTasks = data.all_tasks || data.tasks;
  const proj2026Names = new Set(
    allProjects.filter(p => p.deadline && p.deadline.split('.')[2] === String(CONFIG.year))
               .map(p => p.name)
  );
  allTasks2026 = allTasks.filter(t => proj2026Names.has(t.project));
  allDetails = data.projects;
  allCurators = data.curators;
}
```

> Заменяет 5 `let all*` глобалов и блок их присваивания в `initDashboard`. Импортёры читают `all*` как live-binding; запись — только здесь, через `setData`.

- [ ] **Step 4: Синтаксис**

Run: `node --check js/config.js && node --check js/helpers.js && node --check js/state.js && echo "LEAVES OK"`
Expected: `LEAVES OK`.

- [ ] **Step 5: Коммит**

```bash
git add js/config.js js/helpers.js js/state.js
git commit -m "refactor(ui): листовые ES-модули config/helpers/state [D4]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Модули рендера, фильтров, навигации

**Files:**
- Create: `js/render/overview.js`, `js/render/vysv.js`, `js/render/deadlines.js`, `js/render/tasks.js`, `js/render/detail.js`, `js/render/projects.js`, `js/filters.js`, `js/nav.js`

- [ ] **Step 1: Создать каждый модуль, перенося соответствующие функции из `app.js`**

Для каждого модуля: перенеси тела функций (по таблице «Карта модулей»), поставь `export` перед экспортируемыми, добавь `import { … } from '…'` для всех символов, которые функция использует из других домов (см. таблицу). Относительные пути: из `js/render/*` — `'../helpers.js'`, `'../state.js'`, `'../config.js'`, `'../nav.js'`; из `js/filters.js`/`js/nav.js` — `'./helpers.js'` и т.д.

Распределение функций:
- `render/overview.js`: `renderProjTable`, `computeTaskKPIs`, `renderStatusBadges`
- `render/vysv.js`: `_gaugeSVG`, `_vysvDetailHTML`, `renderVysvBlock`, `highlightGauge` (экспорт — `renderVysvBlock`, `highlightGauge`)
- `render/deadlines.js`: `getMonday` (внутр.), `renderDeadlineMap`
- `render/tasks.js`: `renderTasks`, `filterTasksByStat`, `populateTaskFilter`
- `render/detail.js`: `loadDetail`, `populateDetailSelect`
- `render/projects.js`: `renderFullProjTable`
- `filters.js`: `populateOwnerFilter`, `applyExecFilters`
- `nav.js`: `showTab`, `goToDetail`

Пример (`js/render/projects.js`):
```javascript
import { escapeHTML, getProgressColor, byDeadline, getQuarter, CLOSED_STATUSES, Q_COLORS, PRIORITY_STAR } from '../helpers.js';
import { allTasks } from '../state.js';
import { goToDetail } from '../nav.js';

export function renderFullProjTable(projects, filter = 'all') { /* тело без изменений */ }
```

Пример (`js/nav.js`):
```javascript
import { loadDetail } from './render/detail.js';

export function showTab(name) { /* тело без изменений */ }
export function goToDetail(name) { /* тело без изменений */ }
```

> `CONFIG` нужен в `vysv.js` (деление на `hoursPerUnit`), `tasks.js` (URL `redmineBase`, год), `detail.js` (`hoursPerUnit`). Импортируй `import { CONFIG } from '../config.js'`.

- [ ] **Step 2: Синтаксис каждого модуля**

Run:
```bash
for f in js/render/overview.js js/render/vysv.js js/render/deadlines.js js/render/tasks.js js/render/detail.js js/render/projects.js js/filters.js js/nav.js; do node --check "$f" || exit 1; done && echo "MODULES SYNTAX OK"
```
Expected: `MODULES SYNTAX OK`.

- [ ] **Step 3: Коммит**

```bash
git add js/render js/filters.js js/nav.js
git commit -m "refactor(ui): модули рендера/фильтров/навигации [D4]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: `main.js`, переключение `index.html`, удаление `app.js`, приёмка

**Files:**
- Create: `js/main.js`
- Modify: `index.html` (тег скрипта)
- Delete: `js/app.js`

- [ ] **Step 1: Создать `js/main.js` (точка входа)**

Перенести из `app.js`: `initDashboard`, `setupEventListeners`, `loadData`. Добавить импорты всех используемых символов (config/state/render/*/filters/nav). В `initDashboard` заменить блок присваивания `CONFIG = {...}` на `applyConfig(data)`, а присваивания `allProjects/allTasks/...` — на `setData(data)`. Гард входа — чтобы модуль импортировался в Node без DOM:

```javascript
import { applyConfig, CONFIG } from './config.js';
import { setData, allProjects, allTasks, allTasks2026, allCurators } from './state.js';
import { renderProjTable, computeTaskKPIs, renderStatusBadges } from './render/overview.js';
import { renderVysvBlock, highlightGauge } from './render/vysv.js';
import { renderDeadlineMap } from './render/deadlines.js';
import { renderTasks, filterTasksByStat, populateTaskFilter } from './render/tasks.js';
import { loadDetail, populateDetailSelect } from './render/detail.js';
import { renderFullProjTable } from './render/projects.js';
import { populateOwnerFilter, applyExecFilters } from './filters.js';
import { showTab, goToDetail } from './nav.js';
// + другие символы helpers, если initDashboard/setupEventListeners их используют (escapeHTML и т.п.)

function initDashboard(data) {
  applyConfig(data);
  setData(data);
  /* остальное тело без изменений — yearLabel, KPI, renderVysvBlock(), бейджи, статы и т.д. */
}

function setupEventListeners() { /* тело без изменений */ }

async function loadData() { /* тело без изменений */ }

if (typeof document !== 'undefined') {
  loadData();
}
```

> Если рендер-функции/фильтры вызывают друг друга через имена, которые в браузере раньше были глобальными (например, `setupEventListeners` навешивает обработчики, зовущие `filterTasksByStat`, `applyExecFilters`, `showTab`, `goToDetail`, `renderTasks`) — все они импортированы выше, поэтому работают. Никаких `window.*` не требуется (инлайн-обработчиков в разметке нет).

- [ ] **Step 2: Проверить, что граф импортов резолвится в Node (без DOM)**

Run:
```bash
node -e "import('./js/main.js').then(()=>console.log('GRAPH OK')).catch(e=>{console.error(e.message);process.exit(1)})"
```
Expected: `GRAPH OK`. Если ошибка `does not provide an export named X` — поправить импорт/экспорт по таблице и повторить. (Гард `typeof document` не даёт `loadData()` выполниться в Node.)

- [ ] **Step 3: Переключить `index.html` на модуль и удалить `app.js`**

В `index.html`: `<script src="js/app.js"></script>` → `<script type="module" src="js/main.js"></script>`.
Затем: `git rm js/app.js`.

- [ ] **Step 4: Приёмка — сервер + глаза**

Run: `node --check js/main.js && echo "MAIN OK"`.
Открыть `http://127.0.0.1:8347/` — пройти все вкладки: **Обзор** (KPI, «Высвобождение %» 122%, дедлайны, таблица готовности), **Детализация** (выбор проекта, статус/цель/показатели), **Задачи** (таблица, фильтры по статусу, ссылки Redmine), **Проекты** (список, ★). Двойной клик по проекту → детализация. Цифры: 36/613/5, просрочено 17.
В консоли браузера (F12) — **нет ошибок** (особенно `does not provide an export` / `Failed to resolve module`).

- [ ] **Step 5: Тесты Фазы 1 не затронуты**

Run: `python3 -m pytest tests/ -q`
Expected: `22 passed` (пайплайн не зависит от UI).

- [ ] **Step 6: Коммит**

```bash
git add index.html js/main.js
git rm js/app.js
git commit -m "refactor(ui): точка входа js/main.js, index.html → ES-модуль [D4]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Документация D4

- [ ] **Step 1: Обновить `CLAUDE.md`**

- «Файлы»/«Архитектура»: новая структура — `index.html` (оболочка), `css/styles.css`, `js/` (config, helpers, state, render/*, filters, nav, main); соглашение «логика по ES-модулям, точка входа `js/main.js`»; пометка «открывать по http (ES-модули)».
- «История изменений»: записи D4 (формат `| 2026-06-16 | Файл: описание |`).

- [ ] **Step 2: Коммит**

```bash
git add CLAUDE.md
git commit -m "docs(phase2): CLAUDE.md — модульная структура UI [D4]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Самопроверка плана

- **Покрытие:** CSS-вынос (Task 1) · JS-вынос (Task 2) · все 26 функций и глобалы распределены по модулям (Tasks 3–5, таблица «Карта модулей») · точка входа + переключение (Task 5) · документация (Task 6).
- **Заглушки:** нет — тела функций переносятся без изменений (явно указано), новое — только export/import-обвязка и `applyConfig`/`setData`/гард входа (показаны полностью).
- **Согласованность:** symbol→дом зафиксирован таблицей; импорты строятся по ней; верификация графа `import('./js/main.js')` ловит расхождения экспортов/импортов.
- **Безопасность:** «строим рядом, переключаем последним» — сайт работает на `app.js` до Task 5; откат = вернуть тег `<script src="js/app.js">`.
- **Честная верификация:** браузера/JSDOM нет → статически проверяем `node --check` + резолвинг графа в Node (модули без top-level DOM, main.js под гардом); финально — ручная визуальная сверка идентичности.

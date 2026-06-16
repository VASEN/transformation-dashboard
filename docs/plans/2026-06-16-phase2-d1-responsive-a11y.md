# Фаза 2 · D1 — Адаптив + доступность (План реализации)

> **Для исполнителя (агента):** пошаговое выполнение; шаги — чекбоксы (`- [ ]`). Каждая задача завершается верификацией и коммитом. Каждая задача — самостоятельный коммит.

**Goal:** На уже чистой модульной базе (после D4) добавить полноценный адаптив на **три класса экранов** (телефон ≤640px / десктоп 641–1599px / крупные ≥1600px) и доступность (a11y: роли вкладок, клавиатура, фокус-стили, контраст, `aria-live`, `role="img"` на гейджах, семантика `nav/main/section`) — **не меняя эстетику** (палитра, шрифты Orbitron + Exo 2, тёмный фон).

**Architecture:** Решения **CSS-driven по умолчанию**. Десктопный диапазон (641–1599px) не трогаем — он остаётся «как сейчас». Адаптив добавляется отдельными медиа-блоками в конец `css/styles.css`, ничего из существующих правил не переписывая (только при необходимости — точечно). Две задачи требуют правок DOM/JS:
- **Нижняя навигация** — статичный `<nav>` в DOM, видимый только ≤640px (CSS), кнопки переиспользуют `showTab` (JS-обработчики вешаются в `setupEventListeners`). Без дубль-логики переключения вкладок.
- **Карточки задач/проектов на телефоне** — **CSS-reflow существующей `<table>`** через `display:block` + псевдоэлементы `td::before` с `content: attr(data-label)`. Требует одной правки в `js/render/tasks.js` (и `projects.js`) — добавить `data-label` на `<td>`. Отдельный рендер карточек НЕ вводим (см. обоснование в Task 4).

**Tech Stack:** статический HTML/CSS/vanilla-JS (ES-модули, без сборщика), Node 22 для синтакс-проверки, Python `http.server` для локального просмотра. Сети нет (jsdom/ruff не поставить) → проверка JS = `node --check` + резолвинг графа импортов; проверка CSS/разметки = ручная визуальная на 3 брейкпоинтах + скилл `web-design-guidelines`.

**Ветка:** `phase2-d1` (текущая).

**Критерий приёмки D1:**
- Цифры и десктопный вид (641–1599px) идентичны до-D1 (36 проектов / 613 задач / 5 кураторов, 17 просрочено, 121–122%).
- Телефон ≤640px: всё в одну колонку; KPI и гейджи стопкой; таблицы «Задачи» и «Проекты — Готовность» / «Все проекты» → карточки; детализация — стопка; фильтры — на всю ширину; навигация — нижняя панель (верхние вкладки скрыты).
- Крупные ≥1600px: контент ограничен `max-width`, типографика/отступы чуть крупнее.
- a11y: вкладки имеют роли `tablist/tab/tabpanel` + `aria-selected` + управление стрелками; у всех `select` есть доступное имя; у кнопок-вкладок осмысленные имена; виден `:focus-visible` (cyan-обводка); `aria-live="polite"` на KPI и счётчиках задач; SVG-гейджи — `role="img"` + `aria-label` с процентом; `--text-dim` поднят до WCAG AA.
- `node --check` всех затронутых модулей чист; граф импортов резолвится (`node --input-type=module -e "import('./js/main.js')"`); 22 pytest Фазы 1 не затронуты.
- Аудит `web-design-guidelines` без блокирующих замечаний (или замечания зафиксированы как осознанно отложенные).

> **Важно:** ES-модули работают только по http — открывать через `python3 -m http.server 8347 --bind 127.0.0.1` → `http://127.0.0.1:8347/`. Это согласовано в спеке/D4.

---

## Брейкпоинты (контракт)

| Класс | Ширина | Поведение |
|---|---|---|
| Телефон | `≤ 640px` | 1 колонка; `.exec-grid`/`.tasks-stats` стопкой; `.two-col`/`.detail-grid`/`.vysv-grid`/`.hours-visual` → 1fr; таблицы `.task-table`/`.proj-table` → карточки; верхняя `.nav`-вкладки скрыты, видна нижняя панель; `.filter-bar` колонкой, `select` — на всю ширину |
| Десктоп | `641–1599px` | **как сейчас, не трогаем** (существующий `@media (max-width:1100px)` остаётся) |
| Крупные | `≥ 1600px` | `.app` ограничен `max-width:1560px` по центру; чуть крупнее типографика (`.kpi-value`, `.stat-pill-val`) и отступы `.screen` |

> Существующий `@media (max-width: 1100px)` (строки 777–781 в `css/styles.css`) — промежуточная адаптация внутри десктопного диапазона; **оставляем как есть**. Новые блоки D1 добавляются ПОСЛЕ него и используют узкие границы (`max-width:640px`, `min-width:1600px`), чтобы не конфликтовать.

---

## Task 1: Крупные экраны ≥1600px (`max-width` + типографика)

Самый изолированный шаг — ничего не ломает на десктопе/телефоне. Делаем первым как «разогрев».

**Files:** Modify `css/styles.css` (добавить блок в конец файла).

- [ ] **Step 1: Добавить медиа-блок крупных экранов**

В конец `css/styles.css` (после существующего `@media (max-width: 1100px)`):

```css
/* === LARGE SCREENS (≥1600px): meeting / projector === */
@media (min-width: 1600px) {
  .app { max-width: 1560px; margin: 0 auto; }
  .screen { padding: 32px 40px; }
  .nav { padding: 20px 40px 0; }
  .kpi-value { font-size: 42px; }
  .stat-pill-val { font-size: 34px; }
  .section-title { font-size: 12px; }
  .proj-table td, .task-table td { font-size: 14px; }
  .exec-grid { gap: 20px; }
}
```

> `.app` — корневой контейнер (один на странице, обёртка всех экранов). Центрирование + `max-width` решают «контент растянут на весь 4K-экран».

- [ ] **Step 2: Проверка**

`python3 -m http.server 8347 --bind 127.0.0.1`, открыть в окне шириной ≥1600px (или DevTools responsive `1920×1080`).
Expected: контент по центру с полями, цифры/заголовки чуть крупнее. На десктопе 1280px и телефоне — без изменений.
`node --check js/main.js` не требуется (CSS-only задача), но прогон ничего не ломает.

- [ ] **Step 3: Коммит**

```bash
git add css/styles.css
git commit -m "feat(ui): адаптив крупных экранов ≥1600px (max-width + типографика) [D1]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Телефон ≤640px — общий layout (одна колонка, стопки, фильтры)

Грид-лейауты в стопку + фильтр-бар колонкой. Таблицы → карточки выносим в Task 4 (отдельный коммит). Навигацию — в Task 3.

**Files:** Modify `css/styles.css`.

- [ ] **Step 1: Добавить базовый мобильный медиа-блок**

В конец `css/styles.css`:

```css
/* === PHONE (≤640px): single column === */
@media (max-width: 640px) {
  /* layout in one column */
  .screen { padding: 16px 12px; }
  .exec-grid { grid-template-columns: 1fr; gap: 12px; margin-bottom: 20px; }
  .two-col { grid-template-columns: 1fr; gap: 14px; }
  .detail-grid { grid-template-columns: 1fr; gap: 14px; }
  .vysv-grid { grid-template-columns: 1fr; }
  .hours-visual { grid-template-columns: 1fr 1fr; }   /* 2×3 ещё читаемо на телефоне */
  .tasks-stats { grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .vysv-detail-grid { grid-template-columns: repeat(2, 1fr); }

  /* KPI чуть компактнее */
  .kpi-card { padding: 16px; }
  .kpi-value { font-size: 30px; }
  .stat-pill-val { font-size: 24px; }

  /* фильтр-бар колонкой, select на всю ширину */
  .filter-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  .filter-bar .separator { display: none; }
  .filter-select { width: 100%; }
  .badge-row { flex-wrap: wrap; }

  /* секция-хедеры переносят бейджи */
  .section-header { flex-wrap: wrap; gap: 8px; }
}
```

> `.tasks-stats` → 2 колонки (5 pill'ов 1-в-строку нечитаемы; 2×3 с последним растянутым — компромисс; при желании можно `repeat(1,1fr)` для строгой стопки, но 2 колонки экономят высоту). Спека требует «KPI стопкой» — это про `.exec-grid` (5 KPI-карточек), он стопкой `1fr`. `.tasks-stats` — вторичные pill-счётчики, для них 2 колонки приемлемы; если владелец на проверке захочет строгую стопку — поменять на `1fr`.

- [ ] **Step 2: Запас под нижнюю навигацию**

Чтобы контент не перекрывался нижней панелью (появится в Task 3), добавить нижний отступ телу экранов в тот же мобильный блок:

```css
@media (max-width: 640px) {
  /* ... (из Step 1) ... */
  .app { padding-bottom: 64px; }   /* высота нижней навигации */
}
```

- [ ] **Step 3: Проверка**

DevTools responsive `390×844` (iPhone 12). Expected: KPI стопкой, две колонки Обзора одна под другой, гейджи стопкой, детализация стопкой, фильтр-бар вертикальный, `select` на всю ширину. Таблицы пока «как есть» (горизонтальный скролл) — карточки в Task 4.
`grep -n "max-width: 640px" css/styles.css` → блоки на месте.

- [ ] **Step 4: Коммит**

```bash
git add css/styles.css
git commit -m "feat(ui): адаптив телефона ≤640px — одна колонка, стопки, фильтры [D1]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Нижняя навигация на телефоне (DOM + CSS + обработчики)

**Подход (обоснование):** нижняя панель — **статичный элемент в DOM**, видимый только ≤640px через CSS (на десктопе `display:none`). Кнопки **переиспользуют существующую логику** `showTab(name)` — никакой второй системы переключения вкладок. Связь верхних и нижних вкладок (active-состояние) обеспечивается тем, что `showTab` уже снимает/ставит `.active` по `.tab[data-tab="…"]` — расширим селектор, чтобы он покрывал и нижние кнопки.

**Files:**
- Modify `index.html` (добавить `<nav class="bottom-nav">` перед `</div>` закрытия `.app`, обернуть верхнюю навигацию в семантику)
- Modify `css/styles.css` (стили `.bottom-nav`, показ/скрытие по брейкпоинту)
- Modify `js/nav.js` (`showTab` — обновлять active и у нижних кнопок)
- Modify `js/main.js` (`setupEventListeners` — повесить обработчики на `.bottom-tab`)

- [ ] **Step 1: Разметка нижней панели в `index.html`**

В самый конец `.app` (перед строкой `</div>` закрытия `.app`, т.е. перед `<script type="module" ...>`) добавить:

```html
  <!-- BOTTOM NAV (phone only) -->
  <nav class="bottom-nav" aria-label="Мобильная навигация">
    <button class="bottom-tab active" data-tab="exec" aria-label="Обзор">
      <span class="bottom-tab-ico" aria-hidden="true">▣</span>
      <span class="bottom-tab-lbl">Обзор</span>
    </button>
    <button class="bottom-tab" data-tab="detail" aria-label="Детализация">
      <span class="bottom-tab-ico" aria-hidden="true">≣</span>
      <span class="bottom-tab-lbl">Детали</span>
    </button>
    <button class="bottom-tab" data-tab="tasks" aria-label="Задачи">
      <span class="bottom-tab-ico" aria-hidden="true">✓</span>
      <span class="bottom-tab-lbl">Задачи</span>
    </button>
  </nav>
```

> Только 3 вкладки (`exec`/`detail`/`tasks`) — экран `projects` (`#screen-projects`) не имеет верхней вкладки и в текущем UI открывается только программно (не из навигации), поэтому в нижнюю панель его тоже не добавляем — паритет с верхней навигацией.

- [ ] **Step 2: Стили `.bottom-nav`**

В конец `css/styles.css` (вне медиа — базовое скрытие; показ — в мобильном блоке):

```css
/* === BOTTOM NAV (mobile) === */
.bottom-nav { display: none; }   /* hidden on desktop */

@media (max-width: 640px) {
  .bottom-nav {
    display: flex;
    position: fixed;
    left: 0; right: 0; bottom: 0;
    z-index: 50;
    background: rgba(10,10,26,0.96);
    backdrop-filter: blur(10px);
    border-top: 1px solid var(--card-border);
    padding: 6px 4px env(safe-area-inset-bottom, 4px);
  }
  .bottom-tab {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 6px 4px;
    background: transparent;
    border: none;
    color: var(--text-dim);
    font-family: 'Exo 2', sans-serif;
    cursor: pointer;
  }
  .bottom-tab .bottom-tab-ico { font-size: 18px; line-height: 1; }
  .bottom-tab .bottom-tab-lbl {
    font-size: 10px; letter-spacing: 0.5px; text-transform: uppercase; font-weight: 600;
  }
  .bottom-tab.active { color: var(--accent); text-shadow: var(--glow); }

  /* скрыть верхние вкладки-кнопки на телефоне, оставив логотип + timestamp */
  .nav .tab { display: none; }
}
```

> Верхние `.tab` скрываются на телефоне; `.nav-logo`, `.separator`, `#updated-at` остаются (тонкая шапка). Нижняя панель `fixed` — `.app { padding-bottom: 64px }` (Task 2 Step 2) даёт ей место.

- [ ] **Step 3: `showTab` — синхронизировать active нижних кнопок**

В `js/nav.js` функция `showTab` сейчас:
```js
export function showTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.querySelector(`.tab[data-tab="${name}"]`).classList.add('active');
  document.getElementById('screen-' + name).classList.add('active');
}
```
Заменить на (добавлены `.bottom-tab` + `aria-selected`):
```js
export function showTab(name) {
  document.querySelectorAll('.tab, .bottom-tab').forEach(t => {
    const isActive = t.dataset.tab === name;
    t.classList.toggle('active', isActive);
    if (t.classList.contains('tab')) t.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  const screen = document.getElementById('screen-' + name);
  if (screen) screen.classList.add('active');
}
```

> `aria-selected` ставится только на верхние `.tab` (они получат `role="tab"` в Task 5). `.bottom-tab` — обычные кнопки навигации с `aria-label`, им роль tab не нужна (паттерн «нижняя панель приложения», не tablist). Active-подсветка — через класс.
>
> Аналогично обновить `goToDetail` в `js/nav.js`: после установки `.active` верхней вкладке detail — продублировать на `.bottom-tab[data-tab="detail"]`. Проще — переиспользовать `showTab('detail')` внутри `goToDetail` вместо ручного дублирования снятия/установки классов:
> ```js
> export function goToDetail(name) {
>   showTab('detail');
>   const sel = document.getElementById('detailSelect');
>   if (sel) { sel.value = name; loadDetail(name); }
> }
> ```
> Это убирает 4 строки ручного манипулирования классами и автоматически синхронизирует обе навигации.

- [ ] **Step 4: Обработчики нижних кнопок в `setupEventListeners`**

В `js/main.js`, в `setupEventListeners`, рядом с блоком верхних вкладок добавить:
```js
  // Bottom nav (mobile) — reuse showTab
  document.querySelectorAll('.bottom-tab[data-tab]').forEach(btn => {
    btn.addEventListener('click', () => showTab(btn.dataset.tab));
  });
```
(`showTab` уже импортирован в `main.js`.)

- [ ] **Step 5: Проверка**

```bash
node --check js/nav.js && node --check js/main.js && echo "JS OK"
node --input-type=module -e "import('./js/main.js').then(()=>console.log('import OK')).catch(e=>{console.error(e);process.exit(1)})"
```
> Второй прогон проверяет резолвинг графа импортов; `loadData()` внутри `main.js` обёрнут в `if (typeof document !== 'undefined')`, поэтому в Node ничего не выполняется — только проверяется, что все импорты резолвятся.

Визуально (`390×844`): внизу панель с 3 кнопками; тап переключает экран и подсвечивает кнопку; верхние вкладки скрыты, логотип/timestamp видны. На десктопе панели нет, верхние вкладки работают. Двойной клик по строке проекта (desktop) → переход в Детализацию по-прежнему работает (`goToDetail`).

- [ ] **Step 6: Коммит**

```bash
git add index.html css/styles.css js/nav.js js/main.js
git commit -m "feat(ui): нижняя навигация на телефоне ≤640px (переиспользует showTab) [D1]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Таблицы «Задачи» и «Проекты» → карточки на телефоне (CSS-reflow + data-label)

**Подход (выбран, обоснование):** **CSS-reflow существующей `<table>`** — `display:block` на `table/thead/tbody/tr/td`, `thead` скрыт (`position:absolute;left:-9999px`), каждая `<td>` получает «строку метки» через `td::before { content: attr(data-label) }`. Метки берутся из атрибута `data-label`, который мы добавляем в рендерах.

Почему этот вариант, а не отдельный рендер карточек:
- **Один источник истины** — нет дубль-логики (`renderTasks` + `renderTaskCards`), нет рассинхрона при будущей виртуализации (D2 работает с одной структурой).
- Сортировки/фильтры/ссылки (`.task-link`, `data-name` для dblclick) продолжают работать — DOM тот же, меняется только раскладка.
- Цена — по одному `data-label` на тип ячейки (статическая строка). На десктопе `::before` не рендерится (правило только в мобильном медиа).

**Files:**
- Modify `js/render/tasks.js` (`data-label` на `<td>` в `renderTasks`)
- Modify `js/render/projects.js` (`data-label` в `renderFullProjTable`)
- Modify `js/render/overview.js` (`data-label` в `renderProjTable` — мини-таблица Обзора)
- Modify `css/styles.css` (reflow-правила в мобильном медиа)

- [ ] **Step 1: `data-label` в `js/render/tasks.js`**

В `renderTasks` каждая `<td>` получает `data-label` (заголовок столбца). Текущий шаблон (строки 33–40) → с метками:
```js
    return `
      <tr>
        <td data-label="Проект"><span class="project-tag" style="background:${ps.bg};color:${ps.color}">${escapeHTML(t.project)}</span></td>
        <td data-label="Тема" style="max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${t.id ? `<a href="${CONFIG.redmineBase}/${t.id}" target="_blank" rel="noopener noreferrer" class="task-link">${escapeHTML(t.theme)}</a>` : escapeHTML(t.theme)}</td>
        <td data-label="Статус"><span style="color:${statusColor};font-size:12px">${escapeHTML(t.status)}</span></td>
        <td data-label="Назначена" style="color:var(--text-dim);font-size:12px">${escapeHTML(t.executor_short || t.person || '—')}</td>
        <td data-label="Срок"><span class="deadline-chip ${urgencyLabel}">${urgencyIcon}${t.deadline || '—'}</span></td>
        <td data-label="Осталось" style="font-size:12px;text-align:right;padding-right:8px">${daysLeft}</td>
      </tr>
    `;
```

> Инлайн `max-width`/`white-space:nowrap` на «Теме» переопределяется в мобильном медиа (Step 4) на `white-space:normal`, иначе длинная тема обрежется в карточке.

- [ ] **Step 2: `data-label` в `js/render/projects.js` (Все проекты)**

В `renderFullProjTable` шаблон строки (строки 17–32) — добавить `data-label`:
```js
        <td data-label="#" style="color:var(--text-dim);font-size:11px">${i + 1}</td>
        <td data-label="Проект">${p.is_priority ? PRIORITY_STAR : ''}${escapeHTML(p.name)}</td>
        <td data-label="Статус"><span class="status-badge ${isActive ? 'active' : 'done'}">${escapeHTML(p.status)}</span></td>
        <td data-label="Назначена" style="color:var(--text-dim);font-size:12px">${escapeHTML(p.owner_short || p.person || '—')}</td>
        <td data-label="Срок" style="color:var(--text-dim);font-size:12px">${p.deadline || '—'}</td>
        <td data-label="Готовность">
          <div class="progress-wrap"> ... </div>
        </td>
```
(тело `progress-wrap` без изменений.)

- [ ] **Step 3: `data-label` в `js/render/overview.js` (мини-таблица Обзора)**

В `renderProjTable` → `renderRow` (строки 25–31):
```js
      <tr data-name="${escapeHTML(p.name)}"${rowClass ? ` class="${rowClass}"` : ''} style="cursor:pointer" title="Двойной клик — детализация">
        <td data-label="Тема">${p.is_priority ? PRIORITY_STAR : ''}${escapeHTML(p.name)}</td>
        <td data-label="Назначена" style="color:var(--text-dim);font-size:12px">${escapeHTML(p.owner_short || p.person || '—')}</td>
        <td data-label="Срок" style="color:var(--text-dim);font-size:12px">${p.deadline || '—'}</td>
        <td data-label="Готовность">${pctDisplay}</td>
      </tr>
```

- [ ] **Step 4: CSS-reflow в мобильном медиа**

В мобильный блок `@media (max-width: 640px)` в `css/styles.css` добавить (общее правило для обеих таблиц):
```css
@media (max-width: 640px) {
  /* ... layout из Task 2 ... */

  /* table → cards reflow */
  .task-table, .proj-table { border-collapse: collapse; }
  .task-table thead, .proj-table thead {
    position: absolute; left: -9999px; top: -9999px;   /* visually hide, keep for SR */
  }
  .task-table tr, .proj-table tr {
    display: block;
    margin: 0 12px 12px;
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 8px 4px;
  }
  .task-table td, .proj-table td {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 6px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    text-align: right;
    white-space: normal;          /* override inline nowrap on "Тема" */
    max-width: none;
    overflow: visible;
    text-overflow: clip;
  }
  .task-table td:last-child, .proj-table td:last-child {
    border-bottom: none;
    width: auto;                  /* override desktop fixed width on last col */
  }
  .task-table td::before, .proj-table td::before {
    content: attr(data-label);
    flex: 0 0 auto;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--text-dim);
    text-align: left;
  }
  /* ячейки без метки (нет data-label) — не показывать пустой ::before */
  .task-table td:not([data-label])::before,
  .proj-table td:not([data-label])::before { content: none; }

  /* hover/sticky thead неактуальны на карточках */
  .task-table th { position: static; }

  /* прогресс-бар в карточке — даём ему ширину */
  .proj-table .progress-wrap { min-width: 140px; }
}
```

> `text-align:right` на `td` + `::before` слева даёт раскладку «Метка ……… Значение». `.table-scroll` (`max-height:calc(100vh-320px)`) на телефоне можно оставить — карточки скроллятся внутри; при желании в этом же блоке `.table-scroll { max-height:none; overflow:visible }`, чтобы скроллилась вся страница (рекомендуется для нижней навигации — единый скролл). Добавить:
> ```css
>   .table-scroll { max-height: none; overflow: visible; }
> ```

- [ ] **Step 5: Проверка**

```bash
node --check js/render/tasks.js && node --check js/render/projects.js && node --check js/render/overview.js && echo "JS OK"
node --input-type=module -e "import('./js/main.js').then(()=>console.log('import OK')).catch(e=>{console.error(e);process.exit(1)})"
```
Визуально (`390×844`): вкладка «Задачи» — список карточек, в каждой строки «Проект / Тема / Статус / Назначена / Срок / Осталось» с метками слева; ссылка на тему кликабельна. Вкладка «Все проекты» и мини-таблица Обзора — аналогично. Десктоп 1280px: таблицы как раньше (`::before` не виден, `thead` на месте).

- [ ] **Step 6: Коммит**

```bash
git add js/render/tasks.js js/render/projects.js js/render/overview.js css/styles.css
git commit -m "feat(ui): таблицы Задачи/Проекты → карточки на телефоне (CSS-reflow + data-label) [D1]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: a11y — роли вкладок + клавиатура + семантика

**Files:**
- Modify `index.html` (роли `tablist/tab/tabpanel`, `aria-*`, семантика `main`)
- Modify `js/nav.js` (`aria-selected` уже в Task 3; здесь — клавиатура)
- Modify `js/main.js` (обработчик клавиатуры для tablist)

- [ ] **Step 1: Роли и семантика в `index.html`**

1. Верхняя `<nav class="nav">` — добавить `role="tablist"` и `aria-label`:
   ```html
   <nav class="nav" aria-label="Основная навигация">
   ```
   > `role="tablist"` ставим на сам `<nav>` (он содержит вкладки). Логотип/timestamp внутри — не интерактивны, скринридер их прочитает как текст; допустимо. Если строго — вынести вкладки в отдельный `<div role="tablist">`, но для минимальной правки оставляем на `<nav>`.

2. Каждая верхняя вкладка-кнопка:
   ```html
   <button class="tab active" data-tab="exec" role="tab" aria-selected="true" aria-controls="screen-exec" id="tab-exec">Обзор</button>
   <button class="tab" data-tab="detail" role="tab" aria-selected="false" aria-controls="screen-detail" id="tab-detail">Детализация</button>
   <button class="tab" data-tab="tasks" role="tab" aria-selected="false" aria-controls="screen-tasks" id="tab-tasks">Задачи</button>
   ```

3. Обернуть экраны в `<main>`:
   ```html
   <main id="main-content">
     <div class="screen active" id="screen-exec"> ... </div>
     ... остальные .screen ...
   </main>
   ```
   > `<main>` — сразу после `</nav>` верхней навигации, охватывает все `.screen`. Нижнюю `.bottom-nav` оставить ВНЕ `<main>` (это навигация, не контент).

4. Панели-экраны, связанные с вкладками, помечаем `role="tabpanel"` + `aria-labelledby`:
   ```html
   <div class="screen active" id="screen-exec" role="tabpanel" aria-labelledby="tab-exec" tabindex="0"> ... </div>
   <div class="screen" id="screen-detail" role="tabpanel" aria-labelledby="tab-detail" tabindex="0"> ... </div>
   <div class="screen" id="screen-tasks" role="tabpanel" aria-labelledby="tab-tasks" tabindex="0"> ... </div>
   ```
   > `#screen-projects` не связан с верхней вкладкой — оставляем без `role="tabpanel"` (это отдельный экран, открываемый программно). `tabindex="0"` на панелях — чтобы при переходе с вкладки фокус мог попасть в панель.

- [ ] **Step 2: Клавиатура для tablist (стрелки + Home/End)**

WAI-ARIA tabs pattern: ←/→ переключают вкладки, Home/End — на первую/последнюю, фокус следует за выбором. Без roving-tabindex (все 3 кнопки остаются в обычном Tab-порядке — проще и корректно). Добавить в `js/main.js` функцию и вызвать из `setupEventListeners`:
```js
function setupTablistKeyboard() {
  const tabs = [...document.querySelectorAll('.nav .tab[role="tab"]')];
  tabs.forEach((tab, i) => {
    tab.addEventListener('keydown', (e) => {
      const map = {
        ArrowRight: (i + 1) % tabs.length,
        ArrowLeft: (i - 1 + tabs.length) % tabs.length,
        Home: 0,
        End: tabs.length - 1,
      };
      if (!(e.key in map)) return;
      e.preventDefault();
      const next = tabs[map[e.key]];
      showTab(next.dataset.tab);   // showTab обновит aria-selected (раздел «Нижняя навигация», Step 3)
      next.focus();
    });
  });
}
```
В `setupEventListeners` — после click-обработчиков `.tab` добавить вызов `setupTablistKeyboard();`. Enter/Space на кнопке-вкладке срабатывают нативно (click-обработчик `.tab` сохраняется).

- [ ] **Step 3: Проверка**

```bash
node --check js/nav.js && node --check js/main.js && echo "JS OK"
node --input-type=module -e "import('./js/main.js').then(()=>console.log('import OK')).catch(e=>{console.error(e);process.exit(1)})"
```
Визуально/клавиатура (desktop): Tab доводит фокус до вкладок; стрелки ←/→ переключают экран, Home/End — край; `aria-selected` меняется (DevTools → Accessibility tree); двойной клик по проекту → Детализация работает.

- [ ] **Step 4: Коммит**

```bash
git add index.html js/nav.js js/main.js
git commit -m "feat(a11y): роли tablist/tab/tabpanel + клавиатура вкладок + семантика main [D1]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: a11y — доступные имена select/кнопок + фокус-стили + контраст

**Files:**
- Modify `index.html` (`aria-label` на `select`, `<label>`-связки через `aria-labelledby` с существующими `.filter-label`)
- Modify `css/styles.css` (`:focus-visible`, `--text-dim` контраст)

- [ ] **Step 1: Доступные имена `select`-фильтров**

Сейчас рядом с `select` есть текстовые `.filter-label` (`<span>`), но программной связи нет. Простейшее — `aria-label` прямо на `select`:
```html
<!-- screen-exec -->
<select class="filter-select" id="ownerFilter" aria-label="Фильтр по ответственному"><option value="all">Все</option></select>

<!-- screen-projects -->
<select class="filter-select" id="projectStatusFilter" aria-label="Фильтр по статусу проекта"> ... </select>

<!-- screen-tasks -->
<select class="filter-select" id="taskProjectFilter" aria-label="Фильтр по проекту"> ... </select>

<!-- screen-detail -->
<select class="filter-select" id="detailSelect" aria-label="Выбор проекта для детализации"> ... </select>
```
> `#yearLabel` — это `<span class="filter-select">` (не интерактивен, `pointer-events:none`), ему имя не нужно.

- [ ] **Step 2: Фокус-стили `:focus-visible`**

В `css/styles.css` (вне медиа, после `.filter-select`/`.tab` правил) добавить единый видимый фокус в теме (cyan):
```css
/* === FOCUS (keyboard) === */
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 6px;
}
.tab:focus-visible,
.bottom-tab:focus-visible,
.stat-pill:focus-visible,
.gauge-card:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
/* select/кнопки уже попадают под :focus-visible выше */
```
> Не трогаем `:focus` без `-visible`, чтобы мышиные клики не давали обводку. `outline` (не `box-shadow`) — не сдвигает layout.

- [ ] **Step 3: Контраст `--text-dim` (WCAG AA)**

Текущий `--text-dim: rgba(232,234,246,0.5)` на фоне `#06060f` — контраст ниже 4.5:1 для мелкого текста. Поднять альфу:
```css
:root {
  /* ... */
  --text-dim: rgba(232,234,246,0.72);   /* было 0.5 — поднято до WCAG AA для мелкого текста */
}
```
> 0.72 даёт ~`#a7a9b8`-эффект на тёмном фоне → контраст ≈ 5–6:1 (проходит AA для обычного текста). Проверить визуально, что тёмно-серый не «спорит» с основным `--text`; при необходимости 0.68–0.75. Бейджи `.status-badge`/`.deadline-chip` используют насыщенные цвета на полупрозрачном фоне — визуально проверить читаемость; критичные (`.deadline-chip.ok` = `rgba(0,255,157,0.7)`) при провале поднять до `0.85`.

- [ ] **Step 4: Проверка**

Визуально (desktop): Tab по странице даёт cyan-обводку на вкладках, `select`, stat-pill, гейджах; мышиный клик — без обводки. Подписи (`--text-dim`) читаемее. Скринридер (если доступен VoiceOver: Cmd+F5) проговаривает имена фильтров.
`grep -n "focus-visible" css/styles.css` и `grep -n "aria-label" index.html` → правки на месте.

- [ ] **Step 5: Коммит**

```bash
git add index.html css/styles.css
git commit -m "feat(a11y): доступные имена select, фокус-стили :focus-visible, контраст text-dim [D1]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: a11y — `aria-live` на KPI/счётчики + `role="img"` на гейджах

**Files:**
- Modify `index.html` (`aria-live` на KPI-карточках и tasks-stats)
- Modify `js/render/vysv.js` (`role="img"` + `aria-label` на SVG-гейдже)

- [ ] **Step 1: `aria-live="polite"` на динамических счётчиках**

KPI и счётчики задач обновляются при смене фильтра (`applyExecFilters`, `filterTasksByStat`) — скринридер должен объявлять изменения. Пометить контейнеры:

В `index.html`:
1. KPI-сетка:
   ```html
   <div class="exec-grid" aria-live="polite">
   ```
2. Tasks-stats:
   ```html
   <div class="tasks-stats" aria-live="polite">
   ```
3. Бейджи-счётчики (Обзор) — `#status-badges-row` и `#qBadgesRow` обновляются динамически:
   ```html
   <div class="badge-row" id="status-badges-row" aria-live="polite"></div>
   ```
   ```html
   <div id="qBadgesRow" style="display:flex;gap:6px;flex-wrap:wrap" aria-live="polite"></div>
   ```
> `aria-live="polite"` на контейнере → SR объявляет изменения текста внутри, не прерывая. Достаточно контейнера; отдельные `#kpi-*` не помечаем (иначе двойные объявления).

- [ ] **Step 2: `role="img"` + `aria-label` на SVG-гейдже**

В `js/render/vysv.js`, функция `_gaugeSVG(pct_vysv)` — добавить роль и описание на `<svg>`. Текущая первая строка SVG:
```js
  return `<svg class="gauge-svg" viewBox="0 0 100 65">
```
заменить на:
```js
  return `<svg class="gauge-svg" viewBox="0 0 100 65" role="img" aria-label="Высвобождение ${pct_vysv}%">
```
> Внутренний `<text>...${pct_vysv}%</text>` остаётся как визуальная метка; для SR `aria-label` даёт цельное «Высвобождение N процентов». Карточка-обёртка `.gauge-card` кликабельна — она остаётся `<div>` с click-обработчиком; для полноты её можно сделать фокусируемой (`tabindex="0"` + keydown Enter), но это вне минимума D1 — гейджи дублируют данные панели, основной путь (owner-фильтр) клавиатурно доступен. **Отложить как опционально** (зафиксировать в самопроверке).

- [ ] **Step 3: Проверка**

```bash
node --check js/render/vysv.js && echo "JS OK"
node --input-type=module -e "import('./js/main.js').then(()=>console.log('import OK')).catch(e=>{console.error(e);process.exit(1)})"
```
Визуально: смена owner-фильтра меняет KPI/гейдж; DevTools → Accessibility: у `<svg>` гейджа имя «Высвобождение N%»; контейнеры KPI/stats имеют `aria-live=polite`.

- [ ] **Step 4: Коммит**

```bash
git add index.html js/render/vysv.js
git commit -m "feat(a11y): aria-live на KPI/счётчиках, role=img+aria-label на SVG-гейджах [D1]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Финальная верификация D1 + аудит web-design-guidelines + документация

**Files:** Modify `CLAUDE.md` (раздел «История изменений» + при необходимости «Файлы»/брейкпоинты).

- [ ] **Step 1: Синтаксис всех затронутых модулей + граф импортов**

```bash
for f in js/main.js js/nav.js js/render/tasks.js js/render/projects.js js/render/overview.js js/render/vysv.js; do node --check "$f" && echo "OK $f"; done
node --input-type=module -e "import('./js/main.js').then(()=>console.log('import graph OK')).catch(e=>{console.error(e);process.exit(1)})"
```
Expected: все `OK`, `import graph OK`.

- [ ] **Step 2: Пайплайн-тесты Фазы 1 не затронуты**

```bash
python3 -m pytest -q
```
Expected: 22 passed (D1 не трогает Python-пайплайн; прогон — страховка от случайных правок).

- [ ] **Step 3: Аудит a11y скиллом `web-design-guidelines`**

Прогнать скилл `web-design-guidelines` по `index.html` + `css/styles.css` + `js/*` (фокус: роли вкладок, имена контролов, фокус-видимость, контраст, `aria-live`, alt/role у SVG). Зафиксировать замечания; блокирующие — починить (доп. шаг/коммит), не-блокирующие/осознанно отложенные — записать в самопроверку плана.

- [ ] **Step 4: Ручная визуальная проверка на 3 брейкпоинтах**

`python3 -m http.server 8347 --bind 127.0.0.1` → `http://127.0.0.1:8347/`, DevTools responsive.

**Телефон (≤640px, напр. 390×844):**
- [ ] KPI-карточки стопкой (1 колонка); цифры читаемы.
- [ ] Обзор: «Проекты — Готовность» и «Высвобождение/Дедлайны» одна под другой; гейджи стопкой.
- [ ] Вкладка «Задачи»: список карточек с метками слева; ссылка на тему открывает Redmine; stat-pill переключают фильтр.
- [ ] Вкладка «Все проекты»: карточки; прогресс-бар виден.
- [ ] Детализация: 3 колонки → стопка; блоки читаемы.
- [ ] Фильтр-бар вертикальный; `select` на всю ширину.
- [ ] Нижняя навигация видна, 3 кнопки, тап переключает + подсвечивает; верхние вкладки скрыты; контент не уходит под панель.

**Десктоп (641–1599px, напр. 1280×800):**
- [ ] Вид и цифры идентичны до-D1 (36/613, 17 просрочено, % высвобождения).
- [ ] Таблицы — обычные (не карточки); `thead` виден, sticky-заголовок «Задач» работает.
- [ ] Нижней панели нет; верхние вкладки работают (клик + стрелки клавиатуры).
- [ ] Двойной клик по строке проекта → Детализация.

**Крупные (≥1600px, напр. 1920×1080):**
- [ ] Контент по центру с полями (`max-width`); типографика чуть крупнее; всё читаемо «с расстояния».

- [ ] **Step 5: Обновить `CLAUDE.md`**

Добавить в «История изменений» записи (по регламенту `| ГГГГ-ММ-ДД | Файл: описание |`), напр.:
```
| 2026-06-16 | css/styles.css: D1 — брейкпоинты телефон ≤640 / десктоп 641–1599 / крупные ≥1600; reflow таблиц в карточки; :focus-visible; контраст --text-dim 0.5→0.72 |
| 2026-06-16 | index.html: D1 — нижняя навигация (mobile), роли tablist/tab/tabpanel, <main>, aria-label фильтров, aria-live на KPI/счётчиках |
| 2026-06-16 | js/nav.js, js/main.js: D1 — showTab синхронит .bottom-tab + aria-selected; клавиатура вкладок (стрелки/Home/End); goToDetail через showTab |
| 2026-06-16 | js/render/{tasks,projects,overview}.js: D1 — data-label на <td> для reflow в карточки; js/render/vysv.js: role=img+aria-label на гейдже |
```
При желании — добавить в раздел «Файлы»/новый подраздел краткую сводку брейкпоинтов (контракт из этого плана).

- [ ] **Step 6: Коммит документации**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md — история и брейкпоинты D1 (адаптив + a11y) [D1]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Самопроверка плана (покрытие спеки D1)

**Брейкпоинты (спека §D1):**
- [x] Телефон ≤640px: одна колонка (Task 2: `.exec-grid`/`.two-col`/`.detail-grid`/`.vysv-grid` → 1fr), KPI стопкой (Task 2), гейджи стопкой (Task 2: `.vysv-grid 1fr`), таблицы «Задачи» и «Проекты» → карточки (Task 4), навигация → нижняя панель (Task 3), детализация 3-кол → стопка (Task 2: `.detail-grid 1fr`), фильтры на всю ширину (Task 2).
- [x] Десктоп 641–1599px: не трогаем — новые медиа узкие (`max-width:640`, `min-width:1600`), существующий `@media(max-width:1100)` сохранён.
- [x] Крупные ≥1600px: `max-width` контейнера + крупнее типографика/отступы (Task 1).

**Доступность (спека §D1):**
- [x] Роли вкладок `tablist/tab/tabpanel`, `aria-selected`, клавиатура (Task 5).
- [x] `aria-label` на select-фильтрах и осмысленные имена кнопок (Task 6 + нижние кнопки в Task 3).
- [x] `:focus-visible` cyan-обводка (Task 6).
- [x] Контраст WCAG AA — `--text-dim` поднят, бейджи проверяются (Task 6).
- [x] `aria-live="polite"` на KPI/счётчиках (Task 7).
- [x] `role="img"` + `aria-label` с процентом на SVG-гейджах (Task 7).
- [x] Семантика `nav`/`main`/`section` — `<main>` обёртка (Task 5), `<nav>` верх/низ (Task 3/5); `.section-card` визуальные секции уже структурны.

**CSS-driven предпочтение:** reflow таблиц (Task 4) и показ нижней навигации (Task 3) — через `@media`; единственная JS-правка для карточек — статичные `data-label` (без дубль-рендера); нижняя навигация переиспользует `showTab` (без второй системы вкладок).

**Верификация без сети:** `node --check` + резолвинг `import('./js/main.js')` для JS; pytest (есть) для пайплайна; ручная визуалка на 3 брейкпоинтах + скилл `web-design-guidelines` для a11y. jsdom/ruff не используются (нет сети) — зафиксировано.

**Заглушек нет:** все шаги содержат реальный код (CSS с настоящими классами `.exec-grid`/`.two-col`/`.vysv-grid`/`.detail-grid`/`.task-table`/`.proj-table`/`.tab`/`.filter-select`; конкретные правки `showTab`/`goToDetail`/`setupEventListeners`/`_gaugeSVG`/`renderTasks`/`renderFullProjTable`/`renderProjTable`; конкретная разметка ролей и `aria-*`).

**Осознанно отложенное (не блокирует приёмку D1):**
- Полная клавиатурная фокусируемость кликабельных `.gauge-card` (`tabindex`+Enter) и `.stat-pill` — отмечена как опциональная (Task 7 Step 2): данные дублируются доступными путями (owner-фильтр, stat — это фильтр, дублирующий KPI). Если аудит `web-design-guidelines` пометит как блокер — добавить `tabindex="0"`+keydown отдельным шагом/коммитом.
- `.tasks-stats` на телефоне — 2 колонки (а не строгая стопка); решение по высоте, при возражении владельца → `1fr`.

**Связь с соседними под-фазами:** D1 сохраняет единый DOM таблицы (карточки = CSS-reflow), что не мешает D2 (виртуализация одной структуры). Финальные адаптивные/доступные компоненты — вход в D3 (дизайн-система).

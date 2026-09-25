"""Сторож: строки из data.json попадают в разметку только через escapeHTML.

Статический разбор шаблонных строк в js/: каждая интерполяция ${…}, которая
читает строковое поле data.json (d.owner, c.name, t.deadline…) или берёт
строку из данных целиком (status, s, m…), обязана быть обёрнута в escapeHTML.
Прецеденты потери экранирования: R5 (16.06.2026, 52018cc) и повторно при
разрезе на js/render/* (исправлено 25.09.2026).

Чего сторож НЕ видит по построению: склейку через `+` без шаблонов
(`'<b>' + d.owner`), промежуточные переменные с другим именем
(`const who = d.owner; …${who}`) и доступ по ключу (`d['owner']`).
На 25.09.2026 таких приёмников innerHTML в js/ нет — новый код держать так же.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS_DIR = ROOT / 'js'

# Строковые поля data.json, включая те, что появляются только после
# еженедельного process_report (current_status, report_updated_at): в данных
# после автопрогона они null. Новый строковый ключ в data.json валит
# test_data_fields_cover_data_json — решить, попадает ли он в разметку.
DATA_FIELDS = {
    'closed_at', 'current_status', 'deadline', 'defense_at', 'executor',
    'executor_short', 'goal', 'indicators', 'manager', 'manager_short', 'name',
    'owner', 'owner_short', 'person', 'problem', 'project', 'project_type',
    'redmine_base', 'report_updated_at', 'start_date', 'status', 'team',
    'theme', 'updated_at', 'urgency', 'url',
    'message',  # err.message: при ошибке разбора несёт фрагмент data.json
}

# Переменные, которые в render-коде несут строку из данных целиком
# (элемент списка этапов/команды/показателей, статус-ключ, фрагмент data.json).
DATA_VARS = {'status', 's', 'm', 'ind', 'name', 'label', 'theme', 'owner',
             'project', 'snippet'}

# Осознанные исключения: (файл, выражение) → почему безопасно.
ALLOWED = {
    ('js/main.js', 'resp.status'): 'HTTP-код ответа fetch, число',
    ('js/main.js', 'parseErr.message'): 'текст new Error(); в разметку идёт через escapeHTML(err.message)',
    ('js/main.js', 'snippet'): 'то же: часть текста new Error()',
}

_FIELD_RX = re.compile(r'\.(' + '|'.join(sorted(DATA_FIELDS)) + r')\b(?!\s*\()')
_VAR_RX = re.compile(r'(?<![\w.$\[])(' + '|'.join(sorted(DATA_VARS)) + r')(?![\w$\[.(])')
# Символ перед `/`, после которого `/` открывает регулярное выражение, а не деление.
_REGEX_PREV = set('(,=:[!&|?{};+-*%<>~^') | {''}


def interpolations(src):
    """[(строка, выражение)] для каждого ${…} в шаблонных строках, включая вложенные."""
    out = []
    n = len(src)

    def skip_str(i, q):
        i += 1
        while i < n and src[i] != q:
            i += 2 if src[i] == '\\' else 1
        return i + 1

    def skip_regex(i):
        i += 1
        in_class = False
        while i < n and src[i] != '\n':
            ch = src[i]
            if ch == '\\':
                i += 2
                continue
            if ch == '[':
                in_class = True
            elif ch == ']':
                in_class = False
            elif ch == '/' and not in_class:
                return i + 1
            i += 1
        return i

    def scan_template(i):
        i += 1
        while i < n:
            ch = src[i]
            if ch == '\\':
                i += 2
                continue
            if ch == '`':
                return i + 1
            if ch == '$' and src[i + 1:i + 2] == '{':
                start = i + 2
                i = scan_code(start, until_brace=True)
                out.append((src.count('\n', 0, start) + 1, src[start:i].strip()))
                i += 1
                continue
            i += 1
        return i

    def scan_code(i, until_brace=False):
        depth = 0
        prev = ''  # последний значащий символ кода — отличить регэксп от деления
        while i < n:
            ch = src[i]
            if ch in '\'"':
                i = skip_str(i, ch)
                prev = ch
                continue
            if ch == '`':
                i = scan_template(i)
                prev = '`'
                continue
            if src.startswith('//', i):
                j = src.find('\n', i)
                i = n if j < 0 else j
                continue
            if src.startswith('/*', i):
                j = src.find('*/', i + 2)
                i = n if j < 0 else j + 2
                continue
            if ch == '/' and (prev in _REGEX_PREV or re.search(r'\breturn\s*$', src[max(0, i - 8):i])):
                i = skip_regex(i)
                prev = '/'
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                if depth == 0 and until_brace:
                    return i
                depth -= 1
            if not ch.isspace():
                prev = ch
            i += 1
        return i

    scan_code(0)
    return out


def _strip_balanced(expr, opener):
    """Вырезать все вызовы вида `opener(...)` со сбалансированными скобками."""
    while True:
        k = expr.find(opener)
        if k < 0:
            return expr
        depth, j = 0, k + len(opener) - 1
        while j < len(expr):
            if expr[j] == '(':
                depth += 1
            elif expr[j] == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        expr = expr[:k] + ' ' + expr[j + 1:]


def _residue(expr):
    """Выражение без вложенных шаблонов, строковых литералов и escapeHTML(...)."""
    expr = re.sub(r'`(?:\\.|[^`\\])*`', ' ', expr)  # вложенные шаблоны проверяются сами
    expr = re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", ' ', expr)
    return _strip_balanced(expr, 'escapeHTML(')


def is_unsafe(expr):
    rest = _residue(expr)
    if _FIELD_RX.search(rest):
        return True
    # В `.map(s => `…`)` голые имена — параметры и аргументы проверок, а разметку
    # строит вложенный шаблон, который проверяется сам. Поля (d.owner) ловятся всегда.
    return '=>' not in rest and bool(_VAR_RX.search(rest))


def violations():
    found = []
    for f in sorted(JS_DIR.rglob('*.js')):
        rel = f.relative_to(ROOT).as_posix()
        for line, expr in interpolations(f.read_text(encoding='utf-8')):
            if is_unsafe(expr) and (rel, expr) not in ALLOWED:
                found.append(f'{rel}:{line}: ${{{expr}}}')
    return found


def test_scanner_sees_nested_templates():
    src = "x.innerHTML = `<b>${a ? `<i>${d.owner}</i>` : ''}</b>${escapeHTML(t.theme)}`;"
    exprs = [e for _, e in interpolations(src)]
    assert 'd.owner' in exprs
    assert 'escapeHTML(t.theme)' in exprs


def test_scanner_survives_regex_literals():
    src = ("const r = /`/g; const q = /[/*]/; const z = s.replace(/\"/g, '');\n"
           "el.innerHTML = `${d.owner}`;")
    assert [e for _, e in interpolations(src)] == ['d.owner']


def test_rule_flags_data_strings_and_passes_escaped():
    for bad in ("d.owner_short || d.owner || '—'", 'c.name', 'status', 's',
                "t.id ? `<a>${escapeHTML(t.theme)}</a>` : t.theme",
                'escapeHTML(a) + d.owner', "escapeHTML(x) ? d.owner : ''",
                'x ? d.owner : `—`', 'd.current_status', 'err.message'):
        assert is_unsafe(bad), bad
    for ok in ("escapeHTML(d.owner_short || d.owner || '—')", 'p.pct',
               'counts[status]', 'm[1]', 's.projects_active', "isStage?'s':'status'",
               "t.id ? `<a>${escapeHTML(t.theme)}</a>` : escapeHTML(t.theme)"):
        assert not is_unsafe(ok), ok


def test_scanner_sees_every_interpolation():
    # Если разбор сбился (регэксп, комментарий), часть шаблонов тихо выпадает.
    for f in sorted(JS_DIR.rglob('*.js')):
        src = f.read_text(encoding='utf-8')
        assert len(interpolations(src)) == src.count('${'), f'разбор {f.name} сбился'


def test_data_strings_are_escaped_in_markup():
    bad = violations()
    assert not bad, (
        'строка из data.json в шаблоне разметки без escapeHTML '
        '(обернуть в escapeHTML или внести в ALLOWED с причиной):\n' + '\n'.join(bad)
    )


def test_data_fields_cover_data_json():
    data = json.loads((ROOT / 'data.json').read_text(encoding='utf-8'))
    keys = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str):
                    keys.add(k)
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(data)
    missing = keys - DATA_FIELDS
    assert not missing, f'новые строковые поля data.json — добавить в DATA_FIELDS: {sorted(missing)}'

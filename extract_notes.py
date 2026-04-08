#!/usr/bin/env python3
"""
extract_notes.py — Извлечение «Последних примечаний» из ежедневной выгрузки Redmine.

Читает файл issues_*.xlsx, фильтрует строки с трекером «Паспорт проекта»
и сохраняет поля, нужные для еженедельного отчёта.

Использование:
    python3 extract_notes.py issues_08_04.xlsx
    python3 extract_notes.py issues_08_04.xlsx --output notes.json
    python3 extract_notes.py issues_08_04.xlsx --text          # человекочитаемый вывод
    python3 extract_notes.py issues_08_04.xlsx --only-with-notes  # только с непустыми примечаниями
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Колонки в выгрузке (0-based индексы, актуально на 08.04.2026)
# ---------------------------------------------------------------------------
COL = {
    "id":            0,   # #
    "project":       1,   # Проект
    "tracker":       2,   # Трекер
    "status":        5,   # Статус
    "subject":       7,   # Тема
    "assigned_to":  28,   # Ответственный
    "done_ratio":   18,   # Готовность (%)
    "due_date":     14,   # Срок завершения
    "updated_on":   10,   # Обновлено
    "url":         146,   # Ссылка на акцептованную идею
    "notes":       189,   # Последние примечания
}

PASSPORT_TRACKER = "Паспорт проекта"


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def strip_html(text: str) -> str:
    """Убрать HTML-теги и нормализовать пробелы."""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "\n• ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fmt_date(value) -> str:
    """Привести дату к строке ДД.ММ.ГГГГ или вернуть пустую строку."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    return str(value)


def fmt_int(value) -> str:
    if value is None:
        return ""
    try:
        return str(int(value))
    except (ValueError, TypeError):
        return str(value)


# ---------------------------------------------------------------------------
# Чтение файла
# ---------------------------------------------------------------------------

def read_passports(xlsx_path: str) -> list[dict]:
    try:
        import openpyxl
    except ImportError:
        print("Установите openpyxl: pip install openpyxl", file=sys.stderr)
        sys.exit(1)

    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)
    headers = next(rows_iter)  # пропустить заголовок

    # Проверяем, что нужные колонки на месте
    def check(idx, expected):
        actual = headers[idx] if idx < len(headers) else None
        if actual != expected:
            print(
                f"  ВНИМАНИЕ: колонка {idx} = «{actual}», ожидалось «{expected}»",
                file=sys.stderr,
            )

    check(COL["tracker"], "Трекер")
    check(COL["notes"], "Последние примечания")
    check(COL["assigned_to"], "Ответственный")

    results = []
    for row in rows_iter:
        if len(row) <= COL["notes"]:
            continue
        if row[COL["tracker"]] != PASSPORT_TRACKER:
            continue

        notes_raw = row[COL["notes"]]
        notes_clean = strip_html(str(notes_raw)) if notes_raw else ""

        results.append(
            {
                "id":          fmt_int(row[COL["id"]]),
                "project":     row[COL["project"]] or "",
                "subject":     row[COL["subject"]] or "",
                "status":      row[COL["status"]] or "",
                "done_ratio":  fmt_int(row[COL["done_ratio"]]),
                "due_date":    fmt_date(row[COL["due_date"]]),
                "updated_on":  fmt_date(row[COL["updated_on"]]),
                "assigned_to": row[COL["assigned_to"]] or "",
                "url":         row[COL["url"]] or "",
                "notes":       notes_clean,
                "has_notes":   bool(notes_clean),
            }
        )

    wb.close()
    return results


# ---------------------------------------------------------------------------
# Форматирование вывода
# ---------------------------------------------------------------------------

def print_text(passports: list[dict], only_with_notes: bool) -> None:
    items = [p for p in passports if p["has_notes"]] if only_with_notes else passports
    total = len(passports)
    with_notes = sum(1 for p in passports if p["has_notes"])

    print(f"Паспортов всего: {total}  |  С примечаниями: {with_notes}  |  Без примечаний: {total - with_notes}")
    print("=" * 60)

    for p in items:
        marker = "✓" if p["has_notes"] else "○"
        print(f"\n{marker} #{p['id']}  {p['project']}")
        print(f"  Статус: {p['status']}  |  Готовность: {p['done_ratio']}%  |  Срок: {p['due_date']}")
        print(f"  Ответственный: {p['assigned_to']}")
        if p["url"]:
            print(f"  Ссылка: {p['url']}")
        if p["notes"]:
            print(f"  Примечания:")
            for line in p["notes"].splitlines():
                print(f"    {line}")
        else:
            print(f"  Примечания: —")
        print("  " + "-" * 56)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Извлечение примечаний паспортов из выгрузки Redmine")
    parser.add_argument("xlsx", help="Путь к файлу выгрузки (issues_*.xlsx)")
    parser.add_argument("--output", "-o", help="Куда сохранить JSON (по умолчанию — в консоль)")
    parser.add_argument("--text", action="store_true", help="Вывод в читаемом текстовом формате")
    parser.add_argument("--only-with-notes", action="store_true", help="Показывать только паспорта с примечаниями")
    args = parser.parse_args()

    xlsx_path = args.xlsx
    if not Path(xlsx_path).exists():
        print(f"Файл не найден: {xlsx_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Читаю: {xlsx_path}", file=sys.stderr)
    passports = read_passports(xlsx_path)
    print(f"Найдено паспортов: {len(passports)}", file=sys.stderr)

    if args.only_with_notes:
        passports_out = [p for p in passports if p["has_notes"]]
    else:
        passports_out = passports

    if args.text:
        print_text(passports, args.only_with_notes)
        return

    result = {
        "extracted_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "source": str(Path(xlsx_path).name),
        "total": len(passports),
        "with_notes": sum(1 for p in passports if p["has_notes"]),
        "passports": passports_out,
    }

    json_str = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(json_str, encoding="utf-8")
        print(f"Сохранено: {args.output}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()

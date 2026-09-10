#!/usr/bin/env python3
"""Это выгрузка Redmine или посторонний файл? — проверка ДО того, как файл
пойдёт в работу.

Вынесено из `watch_pipeline.sh` 10.09.2026: тем же вопросом задаётся Telegram-бот,
принимая файл из чата (`shared/bin/telegram-bot.py`), и второй копии проверки
быть не должно — иначе бот и автопрогон начнут расходиться в том, что считать
выгрузкой. Требования те же, что у пайплайна: `extract_data.REDMINE_REQUIRED`.

    python3 check_source.py issues.xlsx

Коды возврата (на них держатся оба вызывающих):
  0 — выгрузка Redmine;
  4 — файл действительно чужой: нет обязательных колонок. Печатает суть
      (без перечисления всех колонок файла — текст уходит в Telegram);
  3 — проверку НЕ удалось выполнить (рассинхрон numpy/pandas, файл недоступен).
      Это не диагноз файлу: помечать его обработанным нельзя.

Почему «чужой» — 4, а не 2 (найдено независимым ревью 10.09.2026): код 2
отдаёт сам интерпретатор, когда не может открыть файл скрипта — нет его,
нет прав. Стой на 2 вердикт «чужой файл», и отсутствие check_source.py
(например, коммит, в который скрипт не попал) читалось бы как «в выгрузке
нет колонок Redmine»: автопрогон пометил бы настоящую выгрузку обработанной,
а бот удалил бы присланный файл. Любой код, кроме 0 и 4, — «не проверилось».
"""
import sys


def main(path: str) -> int:
    try:
        import pandas as pd
        from extract_data import validate_source_columns, REDMINE_REQUIRED
    except Exception as exc:          # numpy/pandas рассинхронизированы и т.п.
        print(f'проверка не выполнилась: {exc!r}')
        return 3
    try:
        df = pd.read_excel(path)
        validate_source_columns(df, REDMINE_REQUIRED, path)
    except OSError as exc:            # файл занят, права, диск
        print(f'проверка не выполнилась: {exc!r}')
        return 3
    except Exception as exc:
        print(str(exc).split('. Есть:')[0])
        return 4
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('использование: check_source.py <файл.xlsx>')
        sys.exit(3)
    sys.exit(main(sys.argv[1]))

from __future__ import annotations
import re
import warnings
from typing import NamedTuple
import pandas as pd
from src.constants import (
    CHILD_ID_PATTERN,
    PROGRESS_FLAG_ALIASES,
    REQUIRED_COLUMNS,
    SCORE_MAX,
    SCORE_MIN,
    VALID_PROGRESS_FLAGS,
    VALID_SPECIALIST_TYPES,
)
from src.schema import enforce_schema

"""
Валидация и очистка исходных данных сессий.
Две публичные точки входа
--
* ``validate(df)``  – возвращает ``(cleaned_df, issues_df)``
* ``load_and_validate(path)`` – удобная обертка: читает, валидирует
  и выводит сводку.

Решения по дизайну
--
* **Никогда не удаляем** строки молча. Строки, которые нельзя исправить,
  помечаются ``_validation_status = "invalid"``; вызывающий код решает,
  что с ними делать.
* Исправление сдвига колонок: в исходных данных систематическая проблема —
  ``specialist_type`` попадает в колонку ``progress_flag`` для ~85 % строк.
  Автоматически исправляем этот паттерн для чистоты downstream логики.
* Нормализация опечаток: значения ``progress_flag`` типа ``"импровед"``
  мапятся в канонические формы через ``constants.PROGRESS_FLAG_ALIASES``.
* Проверка псевдонимизации: принимаются только коды с префиксом ``СП``.
"""

# Контейнер результата
class ValidationResult(NamedTuple):
    """Тип возвращаемого значения :func:`validate`."""

    cleaned: pd.DataFrame
    """Очищенный DataFrame, соответствующий схеме (все строки, помечены статусом)."""

    issues: pd.DataFrame
    """Строки или ячейки с проблемами с описаниями ``issue_type``."""

# Внутренние вспомогательные функции
def _repair_column_shift(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Исправляет строки, где значение specialist_type попало в progress_flag.
    Наблюдаемый паттерн: ~85 % строк содержат корректное имя специалиста
    (``логопед`` / ``дефектолог`` / ``ПА``) в ``progress_flag``, а
    ``specialist_type`` = ``NaN``. Переносим значение в правильную колонку
    и устанавливаем ``progress_flag`` = ``pd.NA``.
    Возвращает
    --
    tuple[pd.DataFrame, list[dict]]
        Исправленный DataFrame и список записей об ошибках.
    """
    df = df.copy()
    issues: list[dict] = []

    shifted_mask = df["progress_flag"].isin(VALID_SPECIALIST_TYPES)

    for idx in df[shifted_mask].index:
        issues.append(
            {
                "row_index": idx,
                "child_id": df.at[idx, "child_id"],
                "issue_type": "column_shift",
                "detail": (
                    f"progress_flag='{df.at[idx, 'progress_flag']}' похож на "
                    f"тип специалиста; перенесено в specialist_type."
                ),
            }
        )
        # Исправление: перезаписываем specialist_type только если он отсутствует
        if pd.isna(df.at[idx, "specialist_type"]):
            df.at[idx, "specialist_type"] = df.at[idx, "progress_flag"]
        df.at[idx, "progress_flag"] = pd.NA

    return df, issues

def _normalise_progress_flags(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Нормализует опечатки / альтернативные значения progress_flag."""
    df = df.copy()
    issues: list[dict] = []

    for idx, raw_val in df["progress_flag"].items():
        if pd.isna(raw_val):
            continue
        normalised = PROGRESS_FLAG_ALIASES.get(str(raw_val), str(raw_val))
        if normalised != raw_val:
            issues.append(
                {
                    "row_index": idx,
                    "child_id": df.at[idx, "child_id"],
                    "issue_type": "flag_typo",
                    "detail": f"progress_flag '{raw_val}' нормализовано в '{normalised}'.",
                }
            )
            df.at[idx, "progress_flag"] = normalised

    return df, issues

def _check_child_ids(df: pd.DataFrame) -> list[dict]:
    """Возвращает записи об ошибках для child_id, не соответствующих паттерну ``СПxx``"""
    pattern = re.compile(CHILD_ID_PATTERN)
    issues: list[dict] = []
    for idx, cid in df["child_id"].items():
        if pd.isna(cid) or not pattern.match(str(cid)):
            issues.append(
                {
                    "row_index": idx,
                    "child_id": cid,
                    "issue_type": "invalid_child_id",
                    "detail": f"child_id '{cid}' не соответствует паттерну {CHILD_ID_PATTERN}.",
                }
            )
    return issues

def _check_score_range(df: pd.DataFrame) -> list[dict]:
    """Возвращает записи об ошибках для оценок вне диапазона ``[SCORE_MIN, SCORE_MAX]``"""
    out_of_range = df[
        (df["assessment_score"] < SCORE_MIN) | (df["assessment_score"] > SCORE_MAX)
    ]
    return [
        {
            "row_index": idx,
            "child_id": df.at[idx, "child_id"],
            "issue_type": "score_out_of_range",
            "detail": (
                f"assessment_score={row['assessment_score']} вне "
                f"диапазона [{SCORE_MIN}, {SCORE_MAX}]."
            ),
        }
        for idx, row in out_of_range.iterrows()
    ]

def _check_dates(df: pd.DataFrame) -> list[dict]:
    """Возвращает записи об ошибках для непарсимых или null значений session_date."""
    bad = df[df["session_date"].isna()]
    return [
        {
            "row_index": idx,
            "child_id": df.at[idx, "child_id"],
            "issue_type": "invalid_date",
            "detail": "session_date не удалось распарсить.",
        }
        for idx in bad.index
    ]

def _deduplicate(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Удаляет точные дубликаты строк, сохраняя первое вхождение."""
    dupes = df[df.duplicated(keep="first")]
    issues = [
        {
            "row_index": idx,
            "child_id": df.at[idx, "child_id"],
            "issue_type": "duplicate_row",
            "detail": "Точная копия предыдущей строки; удалена.",
        }
        for idx in dupes.index
    ]
    return df.drop_duplicates(keep="first"), issues

# Публичный API
def validate(df: pd.DataFrame) -> ValidationResult:
    """Валидирует и очищает исходный DataFrame сессий.
    Этапы (по порядку)
    --
    1. Применение канонической схемы / типов данных.
    2. Удаление точных дубликатов.
    3. Исправление сдвига ``specialist_type → progress_flag``.
    4. Нормализация опечаток в ``progress_flag``.
    5. Проверка формата псевдонимизации ``child_id``.
    6. Проверка диапазона ``assessment_score``.
    7. Проверка парсимости ``session_date``.
    Параметры
    --
    df:
        Исходный DataFrame из ``pd.read_excel``.
    Возвращает
    --
    ValidationResult
        Именованный кортеж с ``cleaned`` DataFrame и ``issues`` DataFrame.
        В ``cleaned`` содержатся **все** строки (включая невалидные)
        с колонкой ``_validation_status``:
        ``"ok"`` | ``"repaired"`` | ``"invalid"``.
    """
    all_issues: list[dict] = []

    # 1 Схема
    df = enforce_schema(df)

    # 2 Дедупликация
    df, dup_issues = _deduplicate(df)
    all_issues.extend(dup_issues)

    # 3 Исправление сдвига колонок
    df, shift_issues = _repair_column_shift(df)
    all_issues.extend(shift_issues)

    # 4 Нормализация опечаток
    df, typo_issues = _normalise_progress_flags(df)
    all_issues.extend(typo_issues)

    # 5-7 Проверки
    all_issues.extend(_check_child_ids(df))
    all_issues.extend(_check_score_range(df))
    all_issues.extend(_check_dates(df))

    # Формируем колонку _validation_status
    invalid_indices: set[int] = {
        iss["row_index"]
        for iss in all_issues
        if iss["issue_type"] in {"invalid_child_id", "score_out_of_range", "invalid_date"}
    }
    repaired_indices: set[int] = {
        iss["row_index"]
        for iss in all_issues
        if iss["issue_type"] in {"column_shift", "flag_typo"}
    } - invalid_indices

    df["_validation_status"] = "ok"
    df.loc[list(repaired_indices), "_validation_status"] = "repaired"
    df.loc[list(invalid_indices), "_validation_status"] = "invalid"

    issues_df = pd.DataFrame(all_issues) if all_issues else pd.DataFrame(
        columns=["row_index", "child_id", "issue_type", "detail"]
    )

    return ValidationResult(cleaned=df, issues=issues_df)

def load_and_validate(path: str) -> ValidationResult:
    """Загружает Excel файл, валидирует его и выводит сводку валидации.
    Параметры
    --
    path:
        Путь к входному файлу ``.xlsx``.
    Возвращает
    --
    ValidationResult
        То же, что и :func:`validate`.
    """
    raw = pd.read_excel(path)
    result = validate(raw)

    total = len(result.cleaned)
    ok = (result.cleaned["_validation_status"] == "ok").sum()
    repaired = (result.cleaned["_validation_status"] == "repaired").sum()
    invalid = (result.cleaned["_validation_status"] == "invalid").sum()

    print(f"[Валидация] {total} строк: {ok} ok / {repaired} исправлено / {invalid} невалидно")
    if not result.issues.empty:
        counts = result.issues["issue_type"].value_counts().to_dict()
        for itype, cnt in counts.items():
            print(f"  • {itype}: {cnt}")

    if invalid > 0:
        warnings.warn(
            f"{invalid} строк(а) не прошли валидацию и помечены 'invalid'. "
            "Они включены в очищенный фрейм, но исключены из анализа стагнации.",
            stacklevel=2,
        )

    return result
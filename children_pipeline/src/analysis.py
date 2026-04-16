from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.constants import (
    DEFAULT_STAGNATION_DAYS,
    HIGH_RISK_DAYS,
    MINIMUM_SESSIONS_FOR_ANALYSIS,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
)

"""
Обнаружение стагнации в индивидуальных программах развития.
--
Основная функция
``detect_stagnation(df, min_days)`` - определяет пары (ребенок, область)
где не наблюдалось улучшения баллов за последние ``min_days``
календарных дней и возвращает структурированный отчет с контекстом.

Правило стагнации (простыми словами)
--
Для каждой группы (child_id, domain):

1. Сортируем сессии по ``session_date`` по возрастанию.
2. Определяем **аналитическое окно** как диапазон дат
   ``[latest_date − min_days, latest_date]``.
3. Пара считается **стагнирующей**, когда:
   a. Есть только ОДНА сессия всего (недостаточно данных для тренда), ИЛИ
   b. Максимальный ``assessment_score`` в окне **НЕ ПРЕВЫШАЕТ**
      балл в начале окна (нет движения вверх).
4. **Уровень риска** назначается следующим образом:
   - ``HIGH``   → балл стабилен или падает ≥ HIGH_RISK_DAYS дней.
   - ``MEDIUM`` → балл стабилен ≥ min_days дней.
   - ``LOW``    → только одна сессия в окне; тренд определить невозможно.

Компромисс: "отсутствие прогресса" = "отсутствие положительной дельты балла"
в окне. Ненumeric прокси (комментарии, заметки специалиста) выводятся в отчете,
но не влияют на бинарный флаг стагнации.
"""

# Внутренние вспомогательные функции
def _compute_group_stagnation(
    group: pd.DataFrame,
    min_days: int,
) -> dict[str, Any] | None:
    """Анализирует одну группу (child_id, domain).
    Параметры
    --
    group:
        Подмножество DataFrame сессий для одной пары (child_id, domain).
    min_days:
        Количество календарных дней без улучшения, вызывающее флаг стагнации.

    Возвращает
    --
    dict или None
        Словарь с данными о стагнации, если группа стагнирует, иначе ``None``.
    """
    group = group.sort_values("session_date")

    child_id: str = group["child_id"].iloc[0]
    domain: str = group["domain"].iloc[0]
    age: int = int(group["age"].iloc[0])
    diagnosis: str = group["diagnosis"].iloc[0]

    latest_date: pd.Timestamp = group["session_date"].max()
    window_start: pd.Timestamp = latest_date - pd.Timedelta(days=min_days)

    window_sessions = group[group["session_date"] >= window_start]

    # Недостаточно данных
    if len(group) < MINIMUM_SESSIONS_FOR_ANALYSIS:
        return {
            "child_id": child_id,
            "domain": domain,
            "age": age,
            "diagnosis": diagnosis,
            "risk_level": RISK_LOW,
            "stagnation_days": None,
            "score_at_window_start": int(group["assessment_score"].iloc[0]),
            "score_latest": int(group["assessment_score"].iloc[-1]),
            "score_delta": 0,
            "first_session_date": group["session_date"].min().date(),
            "last_session_date": latest_date.date(),
            "sessions_in_window": len(window_sessions),
            "last_comment": group["comment"].iloc[-1],
            "specialist_type": group["specialist_type"].iloc[-1],
            "reason": "insufficient_data",
        }

    # Балл на границе окна
    # Используем балл сессии, ближайшей к window_start.
    before_window = group[group["session_date"] < window_start]
    score_at_window_start: int = int(
        before_window["assessment_score"].iloc[-1]
        if not before_window.empty
        else window_sessions["assessment_score"].iloc[0]
    )

    score_latest: int = int(group["assessment_score"].iloc[-1])
    score_delta: int = score_latest - score_at_window_start

    # Проверка на ухудшение
    max_score_in_window: int = int(window_sessions["assessment_score"].max())
    is_stagnant: bool = max_score_in_window <= score_at_window_start

    if not is_stagnant:
        return None

    # Длительность ухудшения
    # Сколько дней прошло с последнего ПОЛОЖИТЕЛЬНОГО улучшения балла
    scores = group[["session_date", "assessment_score"]].reset_index(drop=True)
    last_improvement_idx = None
    for i in range(len(scores) - 1, 0, -1):
        if scores.at[i, "assessment_score"] > scores.at[i - 1, "assessment_score"]:
            last_improvement_idx = i
            break

    if last_improvement_idx is not None:
        stagnation_days = int(
            (latest_date - scores.at[last_improvement_idx, "session_date"]).days
        )
    else:
        # Никогда не улучшался → считаем от первой сессии
        stagnation_days = int((latest_date - group["session_date"].min()).days)

    # Уровень риска
    if stagnation_days >= HIGH_RISK_DAYS:
        risk = RISK_HIGH
    elif len(window_sessions) >= MINIMUM_SESSIONS_FOR_ANALYSIS:
        risk = RISK_MEDIUM
    else:
        risk = RISK_LOW

    return {
        "child_id": child_id,
        "domain": domain,
        "age": age,
        "diagnosis": diagnosis,
        "risk_level": risk,
        "stagnation_days": stagnation_days,
        "score_at_window_start": score_at_window_start,
        "score_latest": score_latest,
        "score_delta": score_delta,
        "first_session_date": group["session_date"].min().date(),
        "last_session_date": latest_date.date(),
        "sessions_in_window": len(window_sessions),
        "last_comment": group["comment"].iloc[-1],
        "specialist_type": group["specialist_type"].iloc[-1],
        "reason": "flat_score",
    }

# Публичный API
def detect_stagnation(
    df: pd.DataFrame,
    min_days: int = DEFAULT_STAGNATION_DAYS,
) -> pd.DataFrame:
    """Определяет пары (ребенок, область) без улучшения баллов.
    Параметры
    --
    df:
        Очищенный DataFrame сессий, подготовленный
        :func:`src.validator.validate`. Должен содержать колонки:
        ``child_id``, ``domain``, ``session_date``,
        ``assessment_score``, ``comment``, ``age``, ``diagnosis``,
        ``specialist_type``.
    min_days:
        Минимальное количество календарных дней без улучшения баллов
        для пометки случая как стагнирующий. По умолчанию 28 (4 недели).

    Возвращает
    --
    pd.DataFrame
        Структурированный отчет о стагнации со столбцами:

        * ``child_id``             - псевдоним ребенка (СПxx)
        * ``domain``               - область навыков
        * ``age``                  - возраст ребенка
        * ``diagnosis``            - основной диагноз
        * ``risk_level``           - HIGH / MEDIUM / LOW
        * ``stagnation_days``      - дней с последнего улучшения
        * ``score_at_window_start``- балл в начале аналитического окна
        * ``score_latest``         - последний балл
        * ``score_delta``          - последний − балл начала окна
        * ``first_session_date``   - дата первой сессии
        * ``last_session_date``    - дата последней сессии
        * ``sessions_in_window``   - сессий в аналитическом окне
        * ``last_comment``         - последняя заметка специалиста
        * ``specialist_type``      - тип специалиста
        * ``reason``               - ``flat_score`` | ``insufficient_data``

        Отсортирован по ``risk_level`` (HIGH → MEDIUM → LOW), затем по
        ``stagnation_days`` по убыванию.

    Примеры
    --
    >>> import pandas as pd
    >>> from src.analysis import detect_stagnation
    >>> df = pd.read_excel("data/children_sessions.xlsx")
    >>> report = detect_stagnation(df, min_days=28)
    >>> print(report[["child_id", "domain", "risk_level", "stagnation_days"]])
    """
    if df.empty:
        return pd.DataFrame()

    # Исключаем строки, не прошедшие жесткую валидацию
    if "_validation_status" in df.columns:
        df = df[df["_validation_status"] != "invalid"].copy()

    records: list[dict] = []

    for (child_id, domain), group in df.groupby(
        ["child_id", "domain"], observed=True
    ):
        result = _compute_group_stagnation(group, min_days)
        if result is not None:
            records.append(result)

    if not records:
        return pd.DataFrame(
            columns=[
                "child_id", "domain", "age", "diagnosis", "risk_level",
                "stagnation_days", "score_at_window_start", "score_latest",
                "score_delta", "first_session_date", "last_session_date",
                "sessions_in_window", "last_comment", "specialist_type", "reason",
            ]
        )

    report = pd.DataFrame(records)

    # Сортировка: HIGH → MEDIUM → LOW, затем stagnation_days по убыванию
    risk_order = {RISK_HIGH: 0, RISK_MEDIUM: 1, RISK_LOW: 2}
    report["_risk_sort"] = report["risk_level"].map(risk_order)
    report = (
        report.sort_values(
            ["_risk_sort", "stagnation_days"],
            ascending=[True, False],
            na_position="last",
        )
        .drop(columns=["_risk_sort"])
        .reset_index(drop=True)
    )

    return report

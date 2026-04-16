from __future__ import annotations
import pandas as pd

"""
Типизированные определения схемы для пайплайна сессий детей.
Централизованное определение типов данных здесь делает downstream код
детерминированным и позволяет mypy / pandas-stubs ловить опечатки в
названиях колонок на этапе линтинга.
"""

SESSION_DTYPES: dict[str, str] = {
    "child_id": "string",
    "age": "int64",
    "diagnosis": "string",
    "domain": "string",
    "assessment_score": "int64",
    "comment": "string",
    "progress_flag": "string",
    "specialist_type": "string",
}

def enforce_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Приводит колонки DataFrame к каноническим типам данных.
    Параметры
    --
    df:
        Исходный DataFrame из ``pd.read_excel``.
    Возвращает
    --
    pd.DataFrame
        DataFrame с правильными типами данных. ``session_date`` приводится
        к ``datetime64[ns]``; все строковые колонки используют nullable
        ``StringDtype``.
    """
    df = df.copy()

    for col, dtype in SESSION_DTYPES.items():
        if col in df.columns:
            df[col] = df[col].astype(dtype)

    if "session_date" in df.columns:
        df["session_date"] = pd.to_datetime(df["session_date"], errors="coerce")

    return df
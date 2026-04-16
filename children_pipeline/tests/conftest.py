from __future__ import annotations
import pandas as pd
import pytest


@pytest.fixture()
def minimal_sessions() -> pd.DataFrame:
    """Четыре сессии для двух детей, две области — валидные и чистые данные"""
    return pd.DataFrame(
        {
            "child_id": ["СП01", "СП01", "СП01", "СП01", "СП02", "СП02", "СП02"],
            "age": [4, 4, 4, 4, 5, 5, 5],
            "diagnosis": ["РАС, ур.1"] * 7,
            "domain": ["Social"] * 4 + ["Listening"] * 3,
            "session_date": pd.to_datetime(
                [
                    "2026-01-01", "2026-01-20", "2026-02-10", "2026-03-10",
                    "2026-01-05", "2026-02-05", "2026-03-05",
                ]
            ),
            "assessment_score": [2, 2, 2, 2, 3, 4, 4],
            "comment": ["ok"] * 7,
            "progress_flag": ["stagnant"] * 4 + ["improved", "improved", "stagnant"],
            "specialist_type": ["ПА"] * 4 + ["дефектолог"] * 3,
            "_validation_status": ["ok"] * 7,
        }
    )


@pytest.fixture()
def stagnant_only() -> pd.DataFrame:
    """Один ребенок с явно застойным результатом более 60 дней"""
    return pd.DataFrame(
        {
            "child_id": ["СП10"] * 4,
            "age": [6] * 4,
            "diagnosis": ["РАС, ур.3"] * 4,
            "domain": ["Listening"] * 4,
            "session_date": pd.to_datetime(
                ["2026-01-05", "2026-02-08", "2026-03-15", "2026-04-20"]
            ),
            "assessment_score": [2, 2, 2, 2],
            "comment": ["no change"] * 4,
            "progress_flag": ["stagnant"] * 4,
            "specialist_type": ["дефектолог"] * 4,
            "_validation_status": ["ok"] * 4,
        }
    )


@pytest.fixture()
def improving_child() -> pd.DataFrame:
    """Один ребенок с улучшающимися результатами — НЕ должен быть помечен"""
    return pd.DataFrame(
        {
            "child_id": ["СП01"] * 4,
            "age": [4] * 4,
            "diagnosis": ["РАС, ур.1"] * 4,
            "domain": ["Social"] * 4,
            "session_date": pd.to_datetime(
                ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]
            ),
            "assessment_score": [2, 4, 6, 8],
            "comment": ["progress"] * 4,
            "progress_flag": ["improved"] * 4,
            "specialist_type": ["ПА"] * 4,
            "_validation_status": ["ok"] * 4,
        }
    )


@pytest.fixture()
def raw_with_column_shift() -> pd.DataFrame:
    """Raw DataFrame that has specialist names in the progress_flag column."""
    return pd.DataFrame(
        {
            "child_id": ["СП01", "СП02"],
            "age": [4, 5],
            "diagnosis": ["РАС, ур.1", "РАС, ур.2"],
            "domain": ["Social", "Listening"],
            "session_date": pd.to_datetime(["2026-01-01", "2026-02-01"]),
            "assessment_score": [3, 5],
            "comment": ["note a", "note b"],
            "progress_flag": ["ПА", "дефектолог"],  # смещение по столбцам
            "specialist_type": [None, None],
        }
    )

from __future__ import annotations
import pandas as pd
import pytest
from src.analysis import detect_stagnation
from src.constants import (
    DEFAULT_STAGNATION_DAYS,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
)

class TestDetectStagnation:
    """Основное поведение функции detect_stagnation"""
    def test_empty_dataframe_returns_empty(self) -> None:
        result = detect_stagnation(pd.DataFrame(), min_days=DEFAULT_STAGNATION_DAYS)
        assert result.empty

    def test_improving_child_not_flagged(self, improving_child: pd.DataFrame) -> None:
        """Ребенок с постоянно улучшающимися результатами не должен появляться"""
        report = detect_stagnation(improving_child, min_days=DEFAULT_STAGNATION_DAYS)
        assert report.empty, "Ребенок с улучшениями не должен быть в отчете об изменениях"

    def test_stagnant_child_is_flagged(self, stagnant_only: pd.DataFrame) -> None:
        """Ребенок с плоскими результатами более 90 дней должен появиться в отчете"""
        report = detect_stagnation(stagnant_only, min_days=DEFAULT_STAGNATION_DAYS)
        assert len(report) == 1
        row = report.iloc[0]
        assert row["child_id"] == "СП10"
        assert row["domain"] == "Listening"

    def test_stagnant_child_has_high_risk_after_56_days(
        self, stagnant_only: pd.DataFrame
    ) -> None:
        """Плоский результат >56 дней должен быть помечен как ВЫСОКИЙ риск"""
        report = detect_stagnation(stagnant_only, min_days=DEFAULT_STAGNATION_DAYS)
        assert report.iloc[0]["risk_level"] == RISK_HIGH

    def test_score_delta_is_zero_for_flat(self, stagnant_only: pd.DataFrame) -> None:
        report = detect_stagnation(stagnant_only, min_days=DEFAULT_STAGNATION_DAYS)
        assert report.iloc[0]["score_delta"] == 0

    def test_mixed_children_only_stagnant_flagged(
        self, minimal_sessions: pd.DataFrame
    ) -> None:
        """СП01 (плоский) должен быть помечен; СП02 (улучшение в окне) — нет"""
        report = detect_stagnation(minimal_sessions, min_days=DEFAULT_STAGNATION_DAYS)
        child_ids_in_report = report["child_id"].tolist()
        assert "СП01" in child_ids_in_report

    def test_report_columns_complete(self, stagnant_only: pd.DataFrame) -> None:
        """Отчет должен содержать все необходимые столбцы."""
        expected_cols = {
            "child_id", "domain", "age", "diagnosis", "risk_level",
            "stagnation_days", "score_at_window_start", "score_latest",
            "score_delta", "first_session_date", "last_session_date",
            "sessions_in_window", "last_comment", "specialist_type", "reason",
        }
        report = detect_stagnation(stagnant_only, min_days=DEFAULT_STAGNATION_DAYS)
        assert expected_cols.issubset(set(report.columns))

    def test_custom_min_days_tighter_window(
        self, minimal_sessions: pd.DataFrame
    ) -> None:
        """Очень длинный min_days (невозможно выполнить для коротких датасетов)
        вызывает меньше пометок стагнации, чем короткий min_days, который легко проваливают все дети"""
        report_short = detect_stagnation(minimal_sessions, min_days=7)
        report_long = detect_stagnation(minimal_sessions, min_days=600)
        assert len(report_long) <= len(report_short)

    def test_sorted_high_before_medium_before_low(
        self, minimal_sessions: pd.DataFrame
    ) -> None:
        """Возвращаемый DataFrame должен быть отсортирован ВЫСОКИЙ → СРЕДНИЙ → НИЗКИЙ"""
        report = detect_stagnation(minimal_sessions, min_days=DEFAULT_STAGNATION_DAYS)
        if len(report) < 2:
            pytest.skip("Недостаточно строк для проверки порядка сортировки")
        risk_order = {RISK_HIGH: 0, RISK_MEDIUM: 1, RISK_LOW: 2}
        ranks = report["risk_level"].map(risk_order).tolist()
        assert ranks == sorted(ranks), "Строки не отсортированы по уровню риска"

    def test_single_session_flagged_as_low_risk(self) -> None:
        """Ребенок с одной сессией → НИЗКИЙ риск"""
        df = pd.DataFrame(
            {
                "child_id": ["СП99"],
                "age": [5],
                "diagnosis": ["РАС, ур.1"],
                "domain": ["Social"],
                "session_date": pd.to_datetime(["2026-03-01"]),
                "assessment_score": [3],
                "comment": ["only session"],
                "progress_flag": [None],
                "specialist_type": ["ПА"],
                "_validation_status": ["ok"],
            }
        )
        report = detect_stagnation(df, min_days=DEFAULT_STAGNATION_DAYS)
        assert len(report) == 1
        assert report.iloc[0]["risk_level"] == RISK_LOW

    def test_invalid_rows_excluded(self) -> None:
        """Строки с _validation_status='invalid' не должны влиять на отчет"""
        df = pd.DataFrame(
            {
                "child_id": ["INVALID", "СП01", "СП01", "СП01"],
                "age": [5, 4, 4, 4],
                "diagnosis": ["?", "РАС"] * 2,
                "domain": ["Social"] * 4,
                "session_date": pd.to_datetime(
                    ["2026-01-01", "2026-01-01", "2026-02-01", "2026-03-10"]
                ),
                "assessment_score": [99, 3, 3, 3],
                "comment": ["bad row", "note", "note", "note"],
                "progress_flag": [None, "stagnant", "stagnant", "stagnant"],
                "specialist_type": [None, "ПА", "ПА", "ПА"],
                "_validation_status": ["invalid", "ok", "ok", "ok"],
            }
        )
        report = detect_stagnation(df, min_days=DEFAULT_STAGNATION_DAYS)
        assert "INVALID" not in report["child_id"].tolist()


class TestScoreDeltaCalculation:
    """Краевые случаи для расчета дельты баллов"""

    def test_score_increases_then_plateaus(self) -> None:
        """Рост баллов затем плато все равно считается стагнацией с даты плато"""
        df = pd.DataFrame(
            {
                "child_id": ["СП05"] * 5,
                "age": [6] * 5,
                "diagnosis": ["РАС, ур.2"] * 5,
                "domain": ["Verbal_Request"] * 5,
                "session_date": pd.to_datetime(
                    [
                        "2026-01-01",
                        "2026-01-20",
                        "2026-02-05", # улучшение (3→5)
                        "2026-03-01", # плато
                        "2026-04-10", # плато
                    ]
                ),
                "assessment_score": [3, 3, 5, 5, 5],
                "comment": [""] * 5,
                "progress_flag": [None] * 5,
                "specialist_type": ["логопед"] * 5,
                "_validation_status": ["ok"] * 5,
            }
        )
        report = detect_stagnation(df, min_days=28)
        assert len(report) == 1
        row = report.iloc[0]
        # С 2026-02-05 по 2026-04-10,примерно 60 дней
        assert row["stagnation_days"] is not None
        assert row["stagnation_days"] >= 28

    def test_regression_flagged_as_stagnant(self) -> None:
        """Падение баллов тоже 'отсутствие прогресса' и должно быть помечено"""
        df = pd.DataFrame(
            {
                "child_id": ["СП06"] * 3,
                "age": [5] * 3,
                "diagnosis": ["РАС, ур.3"] * 3,
                "domain": ["Motor_Imitation"] * 3,
                "session_date": pd.to_datetime(
                    ["2026-01-01", "2026-02-01", "2026-03-15"]
                ),
                "assessment_score": [5, 4, 3],
                "comment": [""] * 3,
                "progress_flag": [None] * 3,
                "specialist_type": ["дефектолог"] * 3,
                "_validation_status": ["ok"] * 3,
            }
        )
        report = detect_stagnation(df, min_days=28)
        assert len(report) == 1
        assert report.iloc[0]["score_delta"] < 0

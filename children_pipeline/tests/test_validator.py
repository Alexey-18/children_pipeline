from __future__ import annotations
import pandas as pd
import pytest
from src.validator import validate
from src.constants import VALID_SPECIALIST_TYPES

class TestColumnShiftRepair:
    """Значения specialist-type ошибочно находятся в столбце progress_flag."""
    def test_specialist_moved_to_correct_column(
        self, raw_with_column_shift: pd.DataFrame
    ) -> None:
        result, _ = validate(raw_with_column_shift)
        assert result["specialist_type"].iloc[0] == "ПА"
        assert result["specialist_type"].iloc[1] == "дефектолог"

    def test_progress_flag_cleared_after_shift(
        self, raw_with_column_shift: pd.DataFrame
    ) -> None:
        result, _ = validate(raw_with_column_shift)
        # progress_flag должен быть NA после исправления
        assert pd.isna(result["progress_flag"].iloc[0])
        assert pd.isna(result["progress_flag"].iloc[1])

    def test_shift_issues_recorded(
        self, raw_with_column_shift: pd.DataFrame
    ) -> None:
        _, issues = validate(raw_with_column_shift)
        shift_issues = issues[issues["issue_type"] == "column_shift"]
        assert len(shift_issues) == 2

class TestProgressFlagNormalisation:
    """Нормализация опечаток и алиасов для progress_flag."""
    def test_improv_alias_normalised(self) -> None:
        df = pd.DataFrame(
            {
                "child_id": ["СП01"],
                "age": [4],
                "diagnosis": ["РАС"],
                "domain": ["Social"],
                "session_date": pd.to_datetime(["2026-01-01"]),
                "assessment_score": [3],
                "comment": ["ok"],
                "progress_flag": ["импровед"],
                "specialist_type": ["ПА"],
            }
        )
        cleaned, issues = validate(df)
        assert cleaned["progress_flag"].iloc[0] == "improved"
        typo_issues = issues[issues["issue_type"] == "flag_typo"]
        assert len(typo_issues) == 1

    def test_valid_flag_unchanged(self) -> None:
        df = pd.DataFrame(
            {
                "child_id": ["СП02"],
                "age": [5],
                "diagnosis": ["РАС, ур.1"],
                "domain": ["Listening"],
                "session_date": pd.to_datetime(["2026-01-01"]),
                "assessment_score": [5],
                "comment": ["ok"],
                "progress_flag": ["stagnant"],
                "specialist_type": ["дефектолог"],
            }
        )
        cleaned, issues = validate(df)
        assert cleaned["progress_flag"].iloc[0] == "stagnant"
        typo_issues = issues[issues["issue_type"] == "flag_typo"]
        assert typo_issues.empty

class TestChildIdValidation:
    """Применение шаблона псевдонимизации СПxx."""
    def test_valid_child_id_accepted(self) -> None:
        df = _make_single_row(child_id="СП01")
        cleaned, issues = validate(df)
        id_issues = issues[issues["issue_type"] == "invalid_child_id"]
        assert id_issues.empty

    def test_invalid_child_id_flagged(self) -> None:
        df = _make_single_row(child_id="CHILD_001")
        _, issues = validate(df)
        id_issues = issues[issues["issue_type"] == "invalid_child_id"]
        assert len(id_issues) == 1

    def test_null_child_id_flagged(self) -> None:
        df = _make_single_row(child_id=None)
        _, issues = validate(df)
        id_issues = issues[issues["issue_type"] == "invalid_child_id"]
        assert len(id_issues) == 1

    def test_validation_status_invalid_for_bad_id(self) -> None:
        df = _make_single_row(child_id="BAD")
        cleaned, _ = validate(df)
        assert cleaned["_validation_status"].iloc[0] == "invalid"

class TestScoreRangeValidation:
    """Баллы должны быть в диапазоне [SCORE_MIN, SCORE_MAX]."""
    @pytest.mark.parametrize("bad_score", [0, 11, -1, 100])
    def test_out_of_range_score_flagged(self, bad_score: int) -> None:
        df = _make_single_row(score=bad_score)
        _, issues = validate(df)
        range_issues = issues[issues["issue_type"] == "score_out_of_range"]
        assert len(range_issues) == 1

    @pytest.mark.parametrize("good_score", [1, 5, 10])
    def test_valid_score_not_flagged(self, good_score: int) -> None:
        df = _make_single_row(score=good_score)
        _, issues = validate(df)
        range_issues = issues[issues["issue_type"] == "score_out_of_range"]
        assert range_issues.empty

class TestDeduplication:
    """Точные дублирующиеся строки должны удаляться."""
    def test_duplicate_row_removed(self) -> None:
        df = pd.concat([_make_single_row(), _make_single_row()], ignore_index=True)
        cleaned, issues = validate(df)
        assert len(cleaned) == 1
        dup_issues = issues[issues["issue_type"] == "duplicate_row"]
        assert len(dup_issues) == 1

class TestValidationStatus:
    """Столбец _validation_status устанавливается корректно."""
    def test_ok_row_has_ok_status(self) -> None:
        df = _make_single_row()
        cleaned, _ = validate(df)
        assert cleaned["_validation_status"].iloc[0] == "ok"

    def test_repaired_row_has_repaired_status(
        self, raw_with_column_shift: pd.DataFrame
    ) -> None:
        cleaned, _ = validate(raw_with_column_shift)
        assert (cleaned["_validation_status"] == "repaired").all()

# Вспомогательные функции
def _make_single_row(
    child_id: str | None = "СП01",
    score: int = 5,
) -> pd.DataFrame:
    """Возвращает минимальный валидный DataFrame с одной строкой."""
    return pd.DataFrame(
        {
            "child_id": [child_id],
            "age": [4],
            "diagnosis": ["РАС, ур.1"],
            "domain": ["Social"],
            "session_date": pd.to_datetime(["2026-01-15"]),
            "assessment_score": [score],
            "comment": ["test comment"],
            "progress_flag": ["stagnant"],
            "specialist_type": ["ПА"],
        }
    )
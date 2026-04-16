# Псевдонымы
CHILD_ID_PATTERN: str = r"^СП\d{2,}$"

# Score
SCORE_MIN: int = 1
SCORE_MAX: int = 10

# Флаги
FLAG_IMPROVED: str = "improved"
FLAG_STAGNANT: str = "stagnant"
VALID_PROGRESS_FLAGS: frozenset[str] = frozenset({FLAG_IMPROVED, FLAG_STAGNANT})

# Опечатки
PROGRESS_FLAG_ALIASES: dict[str, str] = {
    "импровед": FLAG_IMPROVED,
    "improved": FLAG_IMPROVED,
    "stagnant": FLAG_STAGNANT,
}

# Специализированные типы
VALID_SPECIALIST_TYPES: frozenset[str] = frozenset({"логопед", "дефектолог", "ПА"})

# Пороговые значения
DEFAULT_STAGNATION_DAYS: int = 28 # 4 недели (требование к пользовательской истории)
HIGH_RISK_DAYS: int = 56 # 8 недель 
MINIMUM_SESSIONS_FOR_ANALYSIS: int = 2  # требуется ≥2 баллов для измерения дельты

# Уровни риска
RISK_HIGH: str = "HIGH"
RISK_MEDIUM: str = "MEDIUM"
RISK_LOW: str = "LOW"

# Выходные названия файлов
REPORT_CSV: str = "stagnation_report.csv"
REPORT_XLSX: str = "stagnation_report.xlsx"
SUMMARY_MD: str = "summary.md"
PLOTS_DIR: str = "plots"

# Required DataFrame columns
REQUIRED_COLUMNS: tuple[str, ...] = (
    "child_id",
    "age",
    "diagnosis",
    "domain",
    "session_date",
    "assessment_score",
    "comment",
    "progress_flag",
    "specialist_type",
)

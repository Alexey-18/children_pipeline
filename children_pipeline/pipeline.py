from __future__ import annotations
import sys
from pathlib import Path
import click
from src.analysis import detect_stagnation
from src.constants import DEFAULT_STAGNATION_DAYS
from src.reporting import export_report, generate_summary, plot_dynamics
from src.validator import load_and_validate

DEFAULT_INPUT = str(Path(__file__).parent / "data" / "children_sessions.xlsx")
DEFAULT_OUTPUT = str(Path(__file__).parent / "outputs")

"""
Командная строка для пайплайна выявления стагнации сессий детей.
Примеры использования
--
Запуск полного пайплайна с параметрами по умолчанию::

    python pipeline.py run

Указание пользовательских порогов и директории вывода::

    python pipeline.py run --min-days 14 --output-dir /tmp/report

Построение графиков только для конкретных детей::

    python pipeline.py plot --child-ids СП01 СП02

Только валидация входных данных::

    python pipeline.py validate
"""

@click.group()
def cli() -> None:
    """Пайплайн выявления стагнации сессий детей."""

@cli.command()
@click.option(
    "--input", "input_path",
    default=DEFAULT_INPUT,
    show_default=True,
    help="Путь к входному файлу .xlsx.",
    type=click.Path(exists=True),
)
@click.option(
    "--output-dir",
    default=DEFAULT_OUTPUT,
    show_default=True,
    help="Директория для всех выходных файлов.",
)
@click.option(
    "--min-days",
    default=DEFAULT_STAGNATION_DAYS,
    show_default=True,
    help="Минимальное количество дней без улучшения для пометки как стагнация.",
    type=int,
)
@click.option(
    "--no-plots",
    is_flag=True,
    default=False,
    help="Пропустить генерацию графиков (быстрее для CI).",
)
def run(
    input_path: str,
    output_dir: str,
    min_days: int,
    no_plots: bool,
) -> None:
    """Запуск полного пайплайна: валидация → анализ → экспорт → графики."""
    click.echo(f"📂 Вход: {input_path}")
    click.echo(f"📁 Выход: {output_dir}")
    click.echo(f"⏱ Окно: {min_days} дней")
    click.echo("")

    # 1 Валидация
    validation_result = load_and_validate(input_path)
    cleaned = validation_result.cleaned

    # 2 Анализ
    report = detect_stagnation(cleaned, min_days=min_days)
    click.echo(f"[Анализ] Обнаружено {len(report)} случаев стагнации.")

    if report.empty:
        click.echo("Случаев стагнации не найдено.")
    else:
        high = (report["risk_level"] == "HIGH").sum()
        med = (report["risk_level"] == "MEDIUM").sum()
        low = (report["risk_level"] == "LOW").sum()
        click.echo(f"   🔴 ВЫСОКИЙ: {high}  🟡 СРЕДНИЙ: {med}  🔵 НИЗКИЙ: {low}")

    # 3 Экспорт
    export_report(report, output_dir=output_dir)

    # 4 Графики
    if not no_plots:
        stagnant_ids = report["child_id"].dropna().unique().tolist() if not report.empty else []
        plot_dynamics(cleaned, child_ids=stagnant_ids or None, output_dir=output_dir)

    # 5 Сводка
    generate_summary(report, output_dir=output_dir, min_days=min_days)

    click.echo("\nПайплайн завершен.")

@cli.command()
@click.option(
    "--input", "input_path",
    default=DEFAULT_INPUT,
    show_default=True,
    type=click.Path(exists=True),
)
def validate(input_path: str) -> None:
    """Валидация входных данных и вывод отчета о качестве."""
    result = load_and_validate(input_path)
    issues = result.issues
    if issues.empty:
        click.echo("Проблем не найдено.")
    else:
        click.echo("\nОбнаружены проблемы:")
        click.echo(issues.to_string(index=False))

@cli.command()
@click.option(
    "--input", "input_path",
    default=DEFAULT_INPUT,
    show_default=True,
    type=click.Path(exists=True),
)
@click.option(
    "--child-ids",
    multiple=True,
    help="Коды конкретных детей для графиков (например, --child-ids СП01 --child-ids СП02).",
)
@click.option(
    "--output-dir",
    default=DEFAULT_OUTPUT,
    show_default=True,
)
def plot(input_path: str, child_ids: tuple[str, ...], output_dir: str) -> None:
    """Генерация графиков динамики баллов для указанных детей."""
    result = load_and_validate(input_path)
    ids = list(child_ids) if child_ids else None
    plot_dynamics(result.cleaned, child_ids=ids, output_dir=output_dir)

if __name__ == "__main__":
    cli()
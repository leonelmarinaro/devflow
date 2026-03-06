from datetime import datetime
from zoneinfo import ZoneInfo

from daily_standup import esc, format_markdown, format_telegram

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
NOW = datetime(2025, 1, 14, 10, 0, tzinfo=TZ)  # Martes


def test_format_markdown_structure(sample_data):
    result = format_markdown(sample_data, "ayer", "2025-01-14", NOW)
    assert "# Daily Standup" in result
    assert "martes" in result
    assert "## Ayer hice" in result
    assert "### Commits (1)" in result
    assert "### PRs (1)" in result
    assert "Fix bug" in result
    assert "Add feature" in result


def test_format_markdown_empty(empty_data):
    result = format_markdown(empty_data, "ayer", "2025-01-14", NOW)
    assert "_Sin commits en el periodo._" in result
    assert "_Sin PRs en el periodo._" in result


def test_format_telegram_escaping(sample_data):
    result = format_telegram(sample_data, "ayer", "2025-01-14", NOW)
    assert "*Daily Standup" in result
    assert "martes" in result


def test_esc_special_chars():
    assert esc("hello_world") == r"hello\_world"
    assert esc("test.py") == r"test\.py"
    assert esc("(foo)") == r"\(foo\)"

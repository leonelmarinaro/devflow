from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from daily_standup import get_date_range

TZ = "America/Argentina/Buenos_Aires"


def test_monday_looks_back_3_days():
    """Lunes debe mirar 3 dias atras (desde viernes)."""
    monday = datetime(2025, 1, 13, 10, 0, tzinfo=ZoneInfo(TZ))  # Lunes
    with patch("daily_standup.datetime") as mock_dt:
        mock_dt.now.return_value = monday
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        since, period_label, _today_str, _now = get_date_range(TZ)

    assert period_label == "Viernes a Lunes"
    assert (monday - since).days == 3


def test_tuesday_looks_back_1_day():
    """Martes debe mirar 1 dia atras."""
    tuesday = datetime(2025, 1, 14, 10, 0, tzinfo=ZoneInfo(TZ))  # Martes
    with patch("daily_standup.datetime") as mock_dt:
        mock_dt.now.return_value = tuesday
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        since, period_label, _today_str, _now = get_date_range(TZ)

    assert period_label == "ayer"
    assert (tuesday - since).days == 1


def test_today_str_format():
    """today_str debe tener formato YYYY-MM-DD."""
    _, _, today_str, _ = get_date_range(TZ)
    parts = today_str.split("-")
    assert len(parts) == 3
    assert len(parts[0]) == 4

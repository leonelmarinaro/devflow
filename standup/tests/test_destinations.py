from unittest.mock import MagicMock, patch

from daily_standup import send_telegram, write_obsidian


def test_send_telegram_success():
    mock_resp = MagicMock()
    mock_resp.ok = True
    with patch("daily_standup.requests.post", return_value=mock_resp) as mock_post:
        result = send_telegram("token", "123", "Hello")
    assert result is True
    mock_post.assert_called_once()


def test_send_telegram_failure():
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 400
    mock_resp.text = "Bad Request"
    with patch("daily_standup.requests.post", return_value=mock_resp):
        result = send_telegram("token", "123", "Hello")
    assert result is False


def test_send_telegram_chunking():
    """Mensajes largos se dividen en chunks de 4000."""
    mock_resp = MagicMock()
    mock_resp.ok = True
    long_text = "x" * 8500
    with patch("daily_standup.requests.post", return_value=mock_resp) as mock_post:
        result = send_telegram("token", "123", long_text)
    assert result is True
    assert mock_post.call_count == 3  # 8500 / 4000 = 3 chunks


def test_write_obsidian_success(tmp_path):
    vault = tmp_path / "vault"
    inbox = vault / "00-Inbox"
    inbox.mkdir(parents=True)
    result = write_obsidian(str(vault), "2025-01-14", "# Report")
    assert result is True
    written = (inbox / "daily_report_2025-01-14.md").read_text()
    assert "# Report" in written


def test_write_obsidian_creates_inbox(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    result = write_obsidian(str(vault), "2025-01-14", "# Report")
    assert result is True
    assert (vault / "00-Inbox" / "daily_report_2025-01-14.md").exists()

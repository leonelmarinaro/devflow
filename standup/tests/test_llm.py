from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from daily_standup import (
    _build_llm_prompt,
    _call_llm,
    format_markdown,
    format_slack,
    generate_summary,
)

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
NOW = datetime(2025, 1, 14, 10, 0, tzinfo=TZ)

LLM_CONFIG = {
    "LLM_API_KEY": "fake-key-for-testing",
    "LLM_BASE_URL": "https://api.groq.com/openai/v1",
    "LLM_MODEL": "llama-3.3-70b-versatile",
}


# ---------------------------------------------------------------------------
# _build_llm_prompt
# ---------------------------------------------------------------------------
class TestBuildLlmPrompt:
    def test_with_data(self, sample_data):
        prompt = _build_llm_prompt(sample_data, "ayer")
        assert "Periodo: ayer" in prompt
        assert "Commits (1):" in prompt
        assert "my-repo: Fix bug" in prompt
        assert "PRs (1):" in prompt
        assert "Add feature" in prompt
        assert "Issues cerrados (1):" in prompt
        assert "Issues abiertos (1):" in prompt

    def test_with_empty_data(self, empty_data):
        prompt = _build_llm_prompt(empty_data, "Viernes a Lunes")
        assert "Periodo: Viernes a Lunes" in prompt
        assert "Commits (0):" in prompt
        assert "PRs (0):" in prompt

    def test_filters_merge_commits(self, sample_data):
        sample_data["commits"].append(
            {"repo": "r", "message": "Merge pull request #1 from x", "sha": "aaa", "date": ""}
        )
        prompt = _build_llm_prompt(sample_data, "ayer")
        assert "Commits (1):" in prompt
        assert "Merge pull request" not in prompt


# ---------------------------------------------------------------------------
# _call_llm
# ---------------------------------------------------------------------------
class TestCallLlm:
    @patch("daily_standup.requests.post")
    def test_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Ayer trabaje en bugs."}}]
        }
        mock_post.return_value = mock_resp

        result = _call_llm("test prompt", LLM_CONFIG)
        assert result == "Ayer trabaje en bugs."
        mock_post.assert_called_once()
        url_arg = mock_post.call_args[0][0]
        assert "chat/completions" in url_arg

    @patch("daily_standup.requests.post")
    def test_http_error(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException("Connection error")
        result = _call_llm("test", LLM_CONFIG)
        assert result is None

    @patch("daily_standup.requests.post")
    def test_timeout(self, mock_post):
        import requests

        mock_post.side_effect = requests.Timeout("Timeout")
        result = _call_llm("test", LLM_CONFIG)
        assert result is None

    @patch("daily_standup.requests.post")
    def test_invalid_json_response(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"unexpected": "format"}
        mock_post.return_value = mock_resp

        result = _call_llm("test", LLM_CONFIG)
        assert result is None


# ---------------------------------------------------------------------------
# generate_summary
# ---------------------------------------------------------------------------
class TestGenerateSummary:
    def test_no_api_key_returns_none(self, sample_data):
        config = {"LLM_API_KEY": "", "LLM_BASE_URL": "x", "LLM_MODEL": "y"}
        result = generate_summary(sample_data, "ayer", config)
        assert result is None

    @patch("daily_standup._call_llm", return_value="Resumen generado.")
    def test_with_api_key_calls_llm(self, mock_call, sample_data):
        result = generate_summary(sample_data, "ayer", LLM_CONFIG)
        assert result == "Resumen generado."
        mock_call.assert_called_once()


# ---------------------------------------------------------------------------
# Formatters con summary
# ---------------------------------------------------------------------------
class TestFormattersWithSummary:
    def test_markdown_with_summary(self, sample_data):
        result = format_markdown(sample_data, "ayer", "2025-01-14", NOW, summary="Resumen test.")
        assert "## Resumen" in result
        assert "Resumen test." in result
        idx_resumen = result.index("## Resumen")
        idx_ayer = result.index("## Ayer hice")
        assert idx_resumen < idx_ayer

    def test_markdown_without_summary(self, sample_data):
        result = format_markdown(sample_data, "ayer", "2025-01-14", NOW)
        assert "## Resumen" not in result

    def test_slack_with_summary(self, sample_data):
        blocks = format_slack(sample_data, "ayer", "2025-01-14", NOW, summary="Resumen test.")
        texts = [b.get("text", {}).get("text", "") for b in blocks if b.get("type") == "section"]
        assert any("Resumen test." in t for t in texts)

    def test_slack_without_summary(self, sample_data):
        blocks = format_slack(sample_data, "ayer", "2025-01-14", NOW)
        texts = [b.get("text", {}).get("text", "") for b in blocks if b.get("type") == "section"]
        assert not any("Resumen" in t for t in texts)

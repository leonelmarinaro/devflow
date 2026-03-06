import json
import subprocess
from unittest.mock import patch

from daily_standup import run_gh


def _mock_result(stdout="[]", returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_run_gh_success():
    data = [{"sha": "abc", "repository": {"name": "repo"}}]
    with patch("daily_standup.subprocess.run", return_value=_mock_result(json.dumps(data))):
        result = run_gh(["search", "commits"], "/usr/bin/gh")
    assert len(result) == 1
    assert result[0]["sha"] == "abc"


def test_run_gh_error_returns_empty():
    with patch(
        "daily_standup.subprocess.run",
        return_value=_mock_result(returncode=1, stderr="error"),
    ):
        result = run_gh(["search", "commits"], "/usr/bin/gh")
    assert result == []


def test_run_gh_timeout_returns_empty():
    with patch("daily_standup.subprocess.run", side_effect=subprocess.TimeoutExpired("gh", 30)):
        result = run_gh(["search", "commits"], "/usr/bin/gh")
    assert result == []


def test_run_gh_invalid_json_returns_empty():
    with patch("daily_standup.subprocess.run", return_value=_mock_result("not json")):
        result = run_gh(["search", "commits"], "/usr/bin/gh")
    assert result == []


def test_run_gh_empty_stdout():
    with patch("daily_standup.subprocess.run", return_value=_mock_result("")):
        result = run_gh(["search", "commits"], "/usr/bin/gh")
    assert result == []

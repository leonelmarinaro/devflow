import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Asegurar que standup/ este en el path para imports
standup_dir = str(Path(__file__).parent.parent)
if standup_dir not in sys.path:
    sys.path.insert(0, standup_dir)

# Mockear sys.argv antes de importar daily_standup para evitar DRY_RUN = True
with patch.object(sys, "argv", ["daily_standup.py"]):
    import importlib

    import daily_standup

    importlib.reload(daily_standup)


@pytest.fixture
def sample_data():
    return {
        "commits": [
            {"repo": "my-repo", "message": "Fix bug", "sha": "abc1234", "date": "2025-01-15"},
        ],
        "prs_done": [
            {
                "number": 42,
                "title": "Add feature",
                "state": "MERGED",
                "repo": "my-repo",
                "url": "https://github.com/org/my-repo/pull/42",
                "created_at": "2025-01-15",
                "closed_at": "2025-01-15",
            },
        ],
        "issues_closed": [
            {
                "number": 10,
                "title": "Fix login",
                "repo": "my-repo",
                "url": "https://github.com/org/my-repo/issues/10",
            },
        ],
        "prs_to_review": [
            {
                "number": 50,
                "title": "Refactor auth",
                "repo": "other-repo",
                "author": "dev2",
                "url": "https://github.com/org/other-repo/pull/50",
            },
        ],
        "issues_open": [
            {
                "number": 20,
                "title": "Implement search",
                "repo": "my-repo",
                "url": "https://github.com/org/my-repo/issues/20",
            },
        ],
    }


@pytest.fixture
def empty_data():
    return {
        "commits": [],
        "prs_done": [],
        "issues_closed": [],
        "prs_to_review": [],
        "issues_open": [],
    }

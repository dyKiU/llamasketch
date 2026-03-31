import os
import tempfile

import pytest

os.environ.setdefault("PENCIL_DEV_MODE", "true")
os.environ.setdefault("PENCIL_USAGE_SALT", "test-salt")
os.environ.setdefault("PENCIL_CORS_ORIGINS", "*")
os.environ.setdefault("PENCIL_DAILY_FREE_LIMIT", "20")
os.environ.setdefault("PENCIL_USAGE_DB", os.path.join(tempfile.mkdtemp(), "conftest.db"))


@pytest.fixture()
def tmp_db(tmp_path):
    """Return a path to a temporary SQLite database."""
    return str(tmp_path / "test_usage.db")

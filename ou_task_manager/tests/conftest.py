from collections.abc import Iterator
from pathlib import Path

import pytest

import app


@pytest.fixture
def isolated_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point all persistence and configuration at an empty temporary directory."""
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(app, "DB_PATH", database)
    monkeypatch.setattr(app, "ENV_PATH", tmp_path / ".env")
    app.init_db()
    yield database

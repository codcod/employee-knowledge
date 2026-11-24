import pytest


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    """CLI defaults (config/sources.toml, config/policy.toml) are relative to the
    working directory; never let a developer's local files leak into a test."""
    monkeypatch.chdir(tmp_path)

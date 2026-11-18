"""EK-011: the built wheel carries the ontology and ingests without the source tree."""

import os
import shutil
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


@pytest.fixture(scope="module")
def wheel(tmp_path_factory) -> Path:
    # Build from a clean copy: a stale build/ or egg-info in a dev tree lets
    # setuptools reuse old files, so the test would pass with package-data removed.
    src = tmp_path_factory.mktemp("project")
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy(ROOT / name, src)
    shutil.copytree(
        ROOT / "src",
        src / "src",
        ignore=shutil.ignore_patterns("*.egg-info", "__pycache__"),
    )
    out = tmp_path_factory.mktemp("dist")
    proc = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(out)],
        check=False,
        cwd=src,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    (whl,) = out.glob("*.whl")
    return whl


def test_wheel_contains_ontology(wheel):
    names = zipfile.ZipFile(wheel).namelist()
    assert "ek/ontology/employees.ttl" in names
    assert "ek/ontology/shapes.ttl" in names


def test_wheel_carries_licence(wheel):
    whl = zipfile.ZipFile(wheel)
    names = whl.namelist()
    assert any(n.endswith(".dist-info/licenses/LICENSE") for n in names)
    (metadata,) = [n for n in names if n.endswith(".dist-info/METADATA")]
    assert "License-Expression: MIT" in whl.read(metadata).decode()


def test_ingests_from_built_wheel(wheel, tmp_path):
    site = tmp_path / "site"
    zipfile.ZipFile(wheel).extractall(site)
    store = tmp_path / "store.trig"
    script = textwrap.dedent(
        f"""
        import sys
        from pathlib import Path
        sys.path.insert(0, {str(site)!r})
        import ek
        assert Path(ek.__file__).resolve().is_relative_to(Path({str(site)!r}).resolve()), ek.__file__
        from typer.testing import CliRunner
        from ek.cli import app
        result = CliRunner().invoke(app, [
            "ingest-excel", {str(EXAMPLES / "employees.xlsx")!r},
            "--source-id", "hr-export",
            "--config", {str(EXAMPLES / "sources.toml")!r},
        ])
        assert result.exit_code == 0, result.output
        """
    )
    env = {**os.environ, "EMPLOYEE_KNOWLEDGE_STORE": str(store)}
    proc = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert store.stat().st_size > 0

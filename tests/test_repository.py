"""Architecture §11 step 12: no real data, stores, reports or credentials are tracked."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PATHS = [
    re.compile(p)
    for p in (
        r"^data/",
        r"^reports/",
        r"^config/sources\.toml$",
        r"(^|/)\.env$",
        r"\.(trig|nq|nt|jsonld|csv|xlsx?|xlsm|pem|key|p12|pfx)$",
    )
]
ALLOWED = {"examples/employees.xlsx", "examples/employees-directory.xlsx"}
SECRETS = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\b(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"][^'\"\s]{6,}"
    r"|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bxox[abp]-[A-Za-z0-9-]{10,}",
    re.IGNORECASE,
)


def tracked() -> list[str]:
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return out.stdout.split()


def test_no_stores_reports_configs_or_workbooks_outside_examples():
    bad = [
        path
        for path in tracked()
        if path not in ALLOWED and any(p.search(path) for p in FORBIDDEN_PATHS)
    ]
    assert bad == []


def test_no_credentials_in_tracked_text_files():
    hits = []
    for path in tracked():
        try:
            text = (ROOT / path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue  # binary, or deleted but not yet committed
        hits += [f"{path}:{m.group(0)[:20]}" for m in SECRETS.finditer(text)]
    assert hits == []


@pytest.mark.parametrize("name", sorted(ALLOWED))
def test_example_workbooks_use_reserved_email_domains(name):
    """A cheap guard against a real export being dropped in as an example."""
    wb = load_workbook(ROOT / name, read_only=True)
    emails = [
        str(cell)
        for ws in wb
        for row in ws.iter_rows(values_only=True)
        for cell in row
        if isinstance(cell, str) and "@" in cell
    ]
    assert emails
    assert all(re.search(r"@[\w.-]*\.(invalid|example|test)$", e) for e in emails), name

"""CLI output prints external text as written (EK-015), on synthetic data only:
no Rich markup or emoji is interpreted, and control characters other than tab are
shown as visible escapes."""

import json
import re
from datetime import UTC, datetime

import pytest
from openpyxl import Workbook
from typer.testing import CliRunner

from ek.adapters.base import EmployeeRecord, ReadResult
from ek.cli import _clean, app
from ek.config import SourceConfig
from ek.constants import FIELD_PREDICATES
from ek.graph.store import KnowledgeStore
from ek.ingest import ingest

# (value, how the CLI must show it)
HOSTILE = [
    ("[/x]", "[/x]"),
    ("[bold]x", "[bold]x"),
    (":warning:x", ":warning:x"),
    ("Eng\x1b[31mRED", "Eng\\x1b[31mRED"),
    ("a\x9b2Jb", "a\\x9b2Jb"),
    ("two\nlines", "two\\nlines"),
]
ESC = "Eng\x1b[31mRED"
RAW = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]")  # Cc except tab; \n checked apart


def load(store, source, emp, dept, ref):
    cfg = SourceConfig(
        source,
        "excel",
        issuer="example-hr",
        mapping_version="1",
        mapping={"employee_id": "id", **{f: f for f in FIELD_PREDICATES}},
    )
    rows = [EmployeeRecord(emp, {"department": dept}, ref)]
    ingest(store, cfg, ReadResult(f"{source}.xlsx", "a" * 64, rows), datetime.now(UTC))


def conflict_store(tmp_path, monkeypatch, value, hr="hr"):
    path = tmp_path / "s.trig"
    monkeypatch.setenv("EMPLOYEE_KNOWLEDGE_STORE", str(path))
    store = KnowledgeStore(path)
    load(store, hr, value, value, f"hr.xlsx#{value}!2")
    load(store, "directory", value, "Product", "directory.xlsx#People!2")
    store.save()


def assert_safe(run, shown, exit_code=0):
    assert run.exit_code == exit_code, run.output
    assert "Traceback" not in run.output
    assert shown in run.output
    lines = run.output.replace("\n", "")  # Rich's own line breaks
    assert not RAW.search(lines)
    assert "⚠" not in run.output


@pytest.mark.parametrize(("value", "shown"), HOSTILE)
def test_report_and_query_show_source_text_as_written(
    tmp_path, monkeypatch, value, shown
):
    conflict_store(tmp_path, monkeypatch, value)
    run = CliRunner().invoke
    result = run(app, ["report"])
    assert_safe(result, shown)
    assert f"{shown} department: no authority policy" in result.output
    # Table cells too: the ID in both rows, the hr value, and the policy line.
    assert result.output.count(shown) == 4
    result = run(app, ["query", "--scope", "all", "--employee-id", value])
    assert_safe(result, shown)
    assert f"hr.xlsx#{shown}!2" in result.output  # the source reference
    result = run(app, ["query", "--scope", "trusted", "--employee-id", value])
    assert_safe(result, f"{shown} (example-hr) department: no trusted value.")


@pytest.mark.parametrize(("value", "shown"), HOSTILE)
def test_config_error_echoes_source_id_as_written(tmp_path, monkeypatch, value, shown):
    monkeypatch.setenv("EMPLOYEE_KNOWLEDGE_STORE", str(tmp_path / "s.trig"))
    config = tmp_path / "sources.toml"
    config.write_text(
        '[[sources]]\nid = "hr"\nkind = "excel"\nissuer = "example-hr"\n'
        'mapping_version = "1"\n[sources.mapping]\nemployee_id = "id"\n',
        encoding="utf-8",
    )
    (tmp_path / "x.xlsx").write_bytes(b"")
    args = ["ingest", "x.xlsx", "--config", str(config), "--source-id", value]
    assert_safe(CliRunner().invoke(app, args), f"Unknown source id '{shown}'", 1)


@pytest.mark.parametrize(("value", "shown"), HOSTILE)
def test_review_error_echoes_argument_as_written(tmp_path, monkeypatch, value, shown):
    conflict_store(tmp_path, monkeypatch, "E1")
    args = ["review", "accept", value, "--reviewer", "r", "--reason", "Checked"]
    assert_safe(CliRunner().invoke(app, args), f"Unknown assertion {shown}", 1)


@pytest.mark.parametrize(("value", "shown"), HOSTILE)
def test_report_json_output_path_is_shown_as_written(
    tmp_path, monkeypatch, value, shown
):
    conflict_store(tmp_path, monkeypatch, "E1")
    out = tmp_path / f"{value}.json"
    result = CliRunner().invoke(app, ["report-json", "--output", str(out)])
    assert_safe(result, f"{shown}.json")
    assert json.loads(out.read_text())["discrepancies"]


def test_quarantine_reference_is_shown_as_written(tmp_path, monkeypatch):
    # openpyxl refuses "[" and ":" in sheet titles: the file name carries the markup.
    monkeypatch.setenv("EMPLOYEE_KNOWLEDGE_STORE", str(tmp_path / "s.trig"))
    wb = Workbook()
    wb.active.title = "a\x9b2J"
    wb.active.append(["id", "Dept"])
    wb.active.append(["E-1", "Eng"])
    wb.active.append([None, "Eng"])
    wb.save(tmp_path / "[bold]hr.xlsx")
    config = tmp_path / "sources.toml"
    config.write_text(
        '[[sources]]\nid = "hr"\nkind = "excel"\nissuer = "example-hr"\n'
        'sheet = "a\\u009b2J"\nmapping_version = "1"\n'
        '[sources.mapping]\nemployee_id = "id"\ndepartment = "Dept"\n',
        encoding="utf-8",
    )
    args = ["ingest-excel", "[bold]hr.xlsx", "--config", str(config)]
    result = CliRunner().invoke(app, [*args, "--source-id", "hr"])
    assert_safe(result, "Quarantined [bold]hr.xlsx#a\\x9b2J!3: missing employee ID")


def test_policy_text_is_shown_as_written(tmp_path, monkeypatch):
    """A policy has no rationale field: "[/x]" enters the rationale as a source id."""
    conflict_store(tmp_path, monkeypatch, "E1", hr="[/x]")
    config = tmp_path / "sources.toml"
    config.write_text(
        "".join(
            f'[[sources]]\nid = "{s}"\nkind = "jira"\nenabled = false\n'
            "allowed_projects = []\n"
            for s in ("[/x]", "directory")
        ),
        encoding="utf-8",
    )
    rows = (
        '[[properties]]\nproperty = "department"\nauthoritative = ["[/x]"]\n'
        'conflict_rule = "prefer-authoritative"\n'
    )
    run = CliRunner().invoke
    for start, expected in (
        ("2026-01-01", "E1 department: policy v:warning:1: recommend: [/x] is"),
        ("2999-01-01", "Policy v:warning:1 is not in force until 2999-01-01"),
    ):
        pol = tmp_path / "policy.toml"
        pol.write_text(
            f'version = "v:warning:1"\neffective_from = {start}\n{rows}',
            encoding="utf-8",
        )
        result = run(app, ["report", "--policy", str(pol), "--config", str(config)])
        assert_safe(result, expected)


def test_query_json_carries_the_original_text(tmp_path, monkeypatch):
    conflict_store(tmp_path, monkeypatch, ESC)
    result = CliRunner().invoke(app, ["query", "--scope", "all", "--json"])
    assert result.exit_code == 0, result.output
    assert "\x1b" not in result.output
    values = {f["value"] for f in json.loads(result.output)[0]["facts"]}
    assert values == {ESC, "Product"}


def test_clean_escapes_controls_and_keeps_the_rest():
    assert _clean("a\tb") == "a\tb"
    assert _clean("\x00\x1b\x7f\x9b\n") == "\\x00\\x1b\\x7f\\x9b\\n"
    assert _clean("Ann\u202e\u200dé[b]:x:") == "Ann\u202e\u200dé[b]:x:"

"""Excel adapter (ADR-0003, ADR-0007), on synthetic workbooks."""

import hashlib
from datetime import datetime
from pathlib import Path

import pytest
from openpyxl import Workbook
from typer.testing import CliRunner

from ek.adapters.base import SourceError
from ek.adapters.excel import ExcelAdapter
from ek.cli import app
from ek.config import SourceConfig

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
MAPPING = {"employee_id": "Emp ID", "full_name": "Name", "department": "Dept"}


def source(sheet=None, mapping=MAPPING):
    return SourceConfig(
        "hr",
        "excel",
        issuer="example-hr",
        mapping_version="1",
        mapping=mapping,
        options={} if sheet is None else {"sheet": sheet},
    )


def workbook(tmp_path, *rows, title="People", extra_sheet=False):
    wb = Workbook()
    ws = wb.active
    ws.title = title
    for row in rows:
        ws.append(row)
    if extra_sheet:
        other = wb.create_sheet("Other")
        other.append(["Emp ID", "Name", "Dept"])
        other.append(["X-9", "Other Person", "Other"])
    path = tmp_path / "input.xlsx"
    wb.save(path)
    return path


HEADER = ["Emp ID", "Name", "Dept", "Unmapped"]


def test_reads_records_keyed_by_employee_id(tmp_path):
    path = workbook(tmp_path, HEADER, [" E-1 ", " Taylor Example ", "Finance", "zz"])
    result = ExcelAdapter(path, source()).read()
    assert result.file_name == "input.xlsx"
    assert result.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result.quarantined == []
    [record] = result.records
    assert record.employee_id == "E-1"
    assert record.source_reference == "input.xlsx#People!2"
    # Raw text is kept for provenance; unmapped columns are not read.
    assert record.values == {"full_name": " Taylor Example ", "department": "Finance"}
    assert record.observed_at is None


def test_row_reference_does_not_change_record_key(tmp_path):
    a = workbook(tmp_path, HEADER, ["E-1", "A", "F"])
    first = ExcelAdapter(a, source()).read().records[0]
    b = workbook(tmp_path, HEADER, ["E-0", "B", "F"], ["E-1", "A", "F"])
    second = ExcelAdapter(b, source()).read().records[1]
    assert first.employee_id == second.employee_id == "E-1"
    assert first.source_reference != second.source_reference


def test_integer_id_is_accepted(tmp_path):
    path = workbook(tmp_path, HEADER, [1001, "A", "F"])
    assert ExcelAdapter(path, source()).read().records[0].employee_id == "1001"


@pytest.mark.parametrize(
    ("bad_id", "reason"),
    [
        (None, "missing employee ID"),
        ("   ", "missing employee ID"),
        (10.5, "employee ID is not text or a whole number"),
        (datetime(2026, 1, 1), "employee ID is not text or a whole number"),
        (True, "employee ID is not text or a whole number"),
    ],
)
def test_bad_ids_are_quarantined_with_reason(tmp_path, bad_id, reason):
    path = workbook(tmp_path, HEADER, ["E-1", "A", "F"], [bad_id, "B", "G"])
    result = ExcelAdapter(path, source()).read()
    assert [r.employee_id for r in result.records] == ["E-1"]
    assert [(q.source_reference, q.reason) for q in result.quarantined] == [
        ("input.xlsx#People!3", reason)
    ]
    assert "B" not in result.quarantined[0].reason


def test_blank_rows_and_blank_cells_are_skipped(tmp_path):
    path = workbook(tmp_path, HEADER, ["E-1", None, "  "], [None, None, None])
    result = ExcelAdapter(path, source()).read()
    assert result.quarantined == []
    assert result.records[0].values == {}


def test_configured_sheet_is_read_from_multi_sheet_workbook(tmp_path):
    path = workbook(tmp_path, HEADER, ["E-1", "A", "F"], extra_sheet=True)
    other = ExcelAdapter(path, source(sheet="Other")).read()
    assert [(r.employee_id, r.source_reference) for r in other.records] == [
        ("X-9", "input.xlsx#Other!2")
    ]
    active = ExcelAdapter(path, source()).read()
    assert [r.employee_id for r in active.records] == ["E-1"]


@pytest.mark.parametrize(
    ("rows", "src", "error"),
    [
        ((), source(), "sheet is empty"),
        ((["Emp ID", "Name", "Name", "Dept"],), source(), "duplicate headers"),
        ((["Emp ID", "Name"],), source(), r"missing mapped columns \['Dept'\]"),
        ((HEADER,), source(sheet="Nope"), "no sheet named 'Nope'"),
    ],
)
def test_unreadable_sheet_raises(tmp_path, rows, src, error):
    path = workbook(tmp_path, *rows)
    with pytest.raises(SourceError, match=error):
        ExcelAdapter(path, src).read()


def test_malformed_file_raises(tmp_path):
    path = tmp_path / "broken.xlsx"
    path.write_bytes(b"not a zip file")
    with pytest.raises(SourceError, match="not a readable .xlsx"):
        ExcelAdapter(path, source()).read()


def test_cli_ingests_example_and_refuses_unknown_source(tmp_path, monkeypatch):
    monkeypatch.setenv("EMPLOYEE_KNOWLEDGE_STORE", str(tmp_path / "store.trig"))
    args = [
        "ingest-excel",
        str(EXAMPLES / "employees.xlsx"),
        "--config",
        str(EXAMPLES / "sources.toml"),
    ]
    ok = CliRunner().invoke(app, [*args, "--source-id", "hr-export"])
    assert ok.exit_code == 0, ok.output
    assert "completed" in ok.output
    bad = CliRunner().invoke(app, [*args, "--source-id", "unknown"])
    assert bad.exit_code == 1
    assert "Unknown source id" in bad.output
    missing = CliRunner().invoke(
        app, [*args[:2], "--config", str(tmp_path / "x.toml"), "--source-id", "hr"]
    )
    assert missing.exit_code == 1


def test_duplicate_ids_quarantine_every_row(tmp_path):
    path = workbook(
        tmp_path, HEADER, ["E-1", "A", "F"], ["E-2", "B", "G"], [" E-1", "C", "H"]
    )
    result = ExcelAdapter(path, source()).read()
    assert [r.employee_id for r in result.records] == ["E-2"]
    assert [(q.source_reference, q.reason) for q in result.quarantined] == [
        ("input.xlsx#People!2", "duplicate employee ID"),
        ("input.xlsx#People!4", "duplicate employee ID"),
    ]

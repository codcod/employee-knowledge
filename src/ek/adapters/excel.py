import hashlib
import io
import zipfile
from collections import Counter
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from ..config import SourceConfig
from .base import EmployeeRecord, QuarantinedRecord, ReadResult, SourceError


class ExcelAdapter:
    """Reads one sheet of a workbook using a configured mapping. Never writes."""

    def __init__(self, path: Path, source: SourceConfig):
        self.path = Path(path)
        self.source = source

    def read(self) -> ReadResult:
        # Hash and parse the same bytes, so the recorded sha256 is what was read.
        data = self.path.read_bytes()
        try:
            workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError) as exc:
            raise SourceError(f"{self.path.name}: not a readable .xlsx file") from exc
        result = ReadResult(self.path.name, hashlib.sha256(data).hexdigest())
        try:
            self._read_sheet(workbook, result)
        finally:
            workbook.close()
        return result

    def _read_sheet(self, workbook, result: ReadResult) -> None:
        name = self.source.sheet
        if name is not None and name not in workbook.sheetnames:
            raise SourceError(f"{self.path.name}: no sheet named '{name}'")
        sheet = workbook[name] if name else workbook.active
        rows = sheet.iter_rows(values_only=True)
        header = next(rows, None)
        if header is None:
            raise SourceError(f"{self.path.name}#{sheet.title}: sheet is empty")
        headers = [str(v).strip() for v in header if v is not None and str(v).strip()]
        if dupes := sorted({h for h in headers if headers.count(h) > 1}):
            raise SourceError(
                f"{self.path.name}#{sheet.title}: duplicate headers {dupes}"
            )
        positions = {str(v).strip(): i for i, v in enumerate(header) if v is not None}
        if missing := sorted(set(self.source.mapping.values()) - set(positions)):
            raise SourceError(
                f"{self.path.name}#{sheet.title}: missing mapped columns {missing}"
            )
        columns = {f: positions[c] for f, c in self.source.mapping.items()}

        records = []
        for row_num, row in enumerate(rows, start=2):
            ref = f"{self.path.name}#{sheet.title}!{row_num}"
            cells = {f: row[i] if i < len(row) else None for f, i in columns.items()}
            if all(v is None or not str(v).strip() for v in row):
                continue  # a blank row carries no information
            raw_id = cells.pop("employee_id")
            # Decimals, dates and booleans are not IDs; refuse to guess. A whole number
            # in xlsx reads back as int (1001.0 is stored as 1001), so it is accepted;
            # leading zeros in numeric cells are already lost and cannot be detected.
            if isinstance(raw_id, bool) or not isinstance(raw_id, str | int | None):
                result.quarantined.append(
                    QuarantinedRecord(ref, "employee ID is not text or a whole number")
                )
                continue
            employee_id = "" if raw_id is None else str(raw_id).strip()
            if not employee_id:
                result.quarantined.append(QuarantinedRecord(ref, "missing employee ID"))
                continue
            values = {
                f: str(v) for f, v in cells.items() if v is not None and str(v).strip()
            }
            records.append(EmployeeRecord(employee_id, values, ref))

        # Two rows with one ID would make the source contradict itself; keep neither.
        counts = Counter(r.employee_id for r in records)
        for record in records:
            if counts[record.employee_id] > 1:
                reason = "duplicate employee ID"
                result.quarantined.append(
                    QuarantinedRecord(record.source_reference, reason)
                )
            else:
                result.records.append(record)

import typing as tp
from dataclasses import dataclass, field


class SourceError(ValueError):
    """The source cannot be read as configured. Nothing is ingested."""


@dataclass(frozen=True)
class EmployeeRecord:
    employee_id: str  # trimmed; the source record key
    values: dict[str, str]  # field -> raw source text (untrimmed); blank cells omitted
    source_reference: str
    observed_at: str | None = None


@dataclass(frozen=True)
class QuarantinedRecord:
    source_reference: str
    reason: str  # must not contain employee data


@dataclass(frozen=True)
class ReadResult:
    file_name: str
    sha256: str
    records: list[EmployeeRecord] = field(default_factory=list)
    quarantined: list[QuarantinedRecord] = field(default_factory=list)


class SourceAdapter(tp.Protocol):
    def read(self) -> ReadResult: ...

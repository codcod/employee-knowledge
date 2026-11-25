import typing as tp
from dataclasses import dataclass, field
from pathlib import Path

from ..config import SourceConfig


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


class AdapterPlugin(tp.Protocol):
    """A source kind, registered as an entry point (ADR-0011)."""

    def parse_options(
        self, options: dict[str, object], where: str
    ) -> dict[str, object]:
        """Validate the entry's non-common keys. Raise ConfigError on any unknown or
        invalid key; return the options the adapter will read."""
        ...

    def read(self, path: Path, source: SourceConfig) -> ReadResult:
        """Read ``path`` without changing it. Return the file name and the sha256 of
        the bytes read. Raise SourceError when the source cannot be read."""
        ...

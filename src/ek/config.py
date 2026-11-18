"""Source configuration loaded from TOML (ADR-0007). Read-only."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .constants import FIELD_PREDICATES

DEFAULT_CONFIG = Path("config/sources.toml")

_COMMON = {"id", "kind", "enabled"}
_KIND_KEYS = {
    "excel": {"issuer", "sheet", "mapping_version", "mapping"},
    "confluence": {"allowed_spaces"},
    "jira": {"allowed_projects"},
    "powerbi": {"workspace_id", "dataset_id"},
}
_MAPPABLE = {"employee_id", *FIELD_PREDICATES}


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SourceConfig:
    id: str
    kind: str
    enabled: bool = True
    issuer: str | None = None
    sheet: str | None = None
    mapping_version: str | None = None
    mapping: dict[str, str] = field(default_factory=dict)


def load_sources(path: Path) -> dict[str, SourceConfig]:
    if not path.exists():
        raise ConfigError(
            f"Source configuration {path} not found. "
            "Copy examples/sources.toml to config/sources.toml and edit it."
        )
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: invalid TOML: {exc}") from exc
    if unknown := set(data) - {"sources"}:
        raise ConfigError(f"{path}: unknown top-level keys: {sorted(unknown)}")
    entries = data.get("sources", [])
    if not isinstance(entries, list):
        raise ConfigError(f"{path}: 'sources' must be an array of tables")
    sources: dict[str, SourceConfig] = {}
    for n, entry in enumerate(entries, start=1):
        source = _parse(entry, f"{path}: source #{n}")
        if source.id in sources:
            raise ConfigError(f"{path}: duplicate source id '{source.id}'")
        sources[source.id] = source
    return sources


def get_source(sources: dict[str, SourceConfig], source_id: str) -> SourceConfig:
    source = sources.get(source_id)
    if source is None:
        raise ConfigError(
            f"Unknown source id '{source_id}'. Configured: {sorted(sources)}"
        )
    if not source.enabled:
        raise ConfigError(f"Source '{source_id}' is disabled")
    return source


def _parse(entry: object, where: str) -> SourceConfig:
    if not isinstance(entry, dict):
        raise ConfigError(f"{where}: must be a table")
    source_id = _text(entry, "id", where)
    where = f"{where} ('{source_id}')"
    kind = _text(entry, "kind", where)
    if kind not in _KIND_KEYS:
        raise ConfigError(f"{where}: unknown kind '{kind}'")
    if unknown := set(entry) - _COMMON - _KIND_KEYS[kind]:
        raise ConfigError(f"{where}: unknown keys {sorted(unknown)}")
    enabled = entry.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigError(f"{where}: 'enabled' must be true or false")
    if kind != "excel":
        if enabled:
            raise ConfigError(f"{where}: {kind} sources are not implemented yet")
        return SourceConfig(source_id, kind, enabled)
    mapping = entry.get("mapping")
    if not isinstance(mapping, dict) or "employee_id" not in mapping:
        raise ConfigError(f"{where}: 'mapping' must be a table with employee_id")
    if unknown := set(mapping) - _MAPPABLE:
        raise ConfigError(f"{where}: unknown mapping fields {sorted(unknown)}")
    return SourceConfig(
        id=source_id,
        kind=kind,
        enabled=enabled,
        issuer=_text(entry, "issuer", where),
        sheet=_text(entry, "sheet", where) if "sheet" in entry else None,
        mapping_version=_text(entry, "mapping_version", where),
        mapping={f: _text(mapping, f, f"{where} mapping") for f in mapping},
    )


def _text(table: dict, key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where}: '{key}' must be a non-blank string")
    return value.strip()

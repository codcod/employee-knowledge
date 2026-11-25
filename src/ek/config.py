"""Source configuration loaded from TOML (ADR-0007, ADR-0011). Read-only."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .constants import FIELD_PREDICATES

DEFAULT_CONFIG = Path("config/sources.toml")

_COMMON = {"id", "kind", "enabled", "issuer", "mapping_version", "mapping"}
# Disabled placeholders, used only while no plugin registers the kind (ADR-0011).
_PLACEHOLDER_KEYS = {
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
    mapping_version: str | None = None
    mapping: dict[str, str] = field(default_factory=dict)
    options: dict[str, object] = field(default_factory=dict)  # validated by the plugin


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
    enabled = entry.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigError(f"{where}: 'enabled' must be true or false")
    # Imported here: adapters import this module.
    from .adapters.registry import load_adapter

    plugin = load_adapter(kind)
    if plugin is None:
        if kind not in _PLACEHOLDER_KEYS:
            raise ConfigError(f"{where}: unknown kind '{kind}'")
        if unknown := set(entry) - {"id", "kind", "enabled"} - _PLACEHOLDER_KEYS[kind]:
            raise ConfigError(f"{where}: unknown keys {sorted(unknown)}")
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
        mapping_version=_text(entry, "mapping_version", where),
        mapping={f: _text(mapping, f, f"{where} mapping") for f in mapping},
        options=plugin.parse_options(
            {k: v for k, v in entry.items() if k not in _COMMON}, where
        ),
    )


def _text(table: dict, key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where}: '{key}' must be a non-blank string")
    return value.strip()

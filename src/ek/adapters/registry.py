"""Source kinds registered as entry points (ADR-0011). Loaded only when configured."""

from importlib.metadata import entry_points

from ..config import ConfigError
from .base import AdapterPlugin

GROUP = "employee_knowledge.adapters"


def load_adapter(kind: str) -> AdapterPlugin | None:
    """The plugin for ``kind``, or None when no entry point registers it."""
    found = [ep for ep in entry_points(group=GROUP) if ep.name == kind]
    if not found:
        return None
    if len(found) > 1:
        dists = sorted(ep.dist.name if ep.dist else ep.value for ep in found)
        raise ConfigError(f"source kind '{kind}' is registered twice: {dists}")
    (ep,) = found
    try:
        return ep.load()
    except Exception as exc:
        raise ConfigError(
            f"source kind '{kind}': cannot load {ep.name} = {ep.value} "
            f"({type(exc).__name__})"
        ) from exc

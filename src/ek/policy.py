"""Source-authority policy (architecture §6, ADR-0010). Read-only.

A policy recommends; it never decides. Nothing here writes to the graph, and trust
state changes only through a review event (ADR-0002).
"""

import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from rdflib import URIRef

from .constants import FIELD_PREDICATES
from .identity import source_uri

DEFAULT_POLICY = Path("config/policy.toml")
CONFLICT_RULES = ("manual", "prefer-authoritative")

_TOP_KEYS = {"version", "effective_from", "properties"}
# No key can waive review: AGENTS.md "No autonomous promotion" (ADR-0010).
_ROW_KEYS = {
    "property",
    "authoritative",
    "secondary",
    "freshness_days",
    "required",
    "reviewer_roles",
    "conflict_rule",
}
# A person already set Rejected and Superseded facts aside; they never count.
_COUNTED = {"Candidate", "NeedsEvidence", "Accepted"}


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class PropertyPolicy:
    property: str  # configuration field name, e.g. "department"
    predicate: URIRef
    authoritative: tuple[str, ...]
    secondary: tuple[str, ...]
    conflict_rule: str
    freshness_days: int | None = None
    required: bool = False
    reviewer_roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class Policy:
    version: str
    effective_from: date
    properties: dict[URIRef, PropertyPolicy]


def load_policy(path: Path, source_ids: set[str]) -> Policy | None:
    """Load the policy at ``path``; ``None`` when there is no file. ``source_ids`` are
    the configured sources every id in the policy must name."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise PolicyError(f"{path}: invalid TOML: {exc}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise PolicyError(f"{path}: cannot be read: {exc}") from exc
    if unknown := set(data) - _TOP_KEYS:
        raise PolicyError(f"{path}: unknown top-level keys: {sorted(unknown)}")
    version = data.get("version")
    if not isinstance(version, str) or not version.strip():
        raise PolicyError(f"{path}: 'version' must be a non-blank string")
    effective = data.get("effective_from")
    # tomllib reads a date-time as datetime, a subclass of date: refuse it.
    if not isinstance(effective, date) or isinstance(effective, datetime):
        raise PolicyError(f"{path}: 'effective_from' must be a date such as 2026-01-01")
    rows = data.get("properties", [])
    if not isinstance(rows, list):
        raise PolicyError(f"{path}: 'properties' must be an array of tables")
    properties: dict[URIRef, PropertyPolicy] = {}
    for n, row in enumerate(rows, start=1):
        entry = _row(row, f"{path}: property #{n}", source_ids)
        if entry.predicate in properties:
            raise PolicyError(f"{path}: duplicate property '{entry.property}'")
        properties[entry.predicate] = entry
    return Policy(version.strip(), effective, properties)


def in_force(policy: Policy | None, today: date) -> bool:
    return policy is not None and policy.effective_from <= today


def version_in_force(policy: Policy | None, today: date) -> str:
    """What a review event records as ``ek:policyVersion``."""
    return policy.version if in_force(policy, today) else "none"


def evaluate(policy: Policy | None, discrepancy: dict, today: date) -> dict:
    """Recommend for one discrepancy from ``ek.reconcile.build_report``. Never decides.
    Rationales name sources, never values."""
    if not in_force(policy, today):
        return _result("no-policy", "no authority policy is in force")
    row = policy.properties.get(URIRef(discrepancy["property"]))
    if row is None:
        return _result("no-policy", "the policy has no row for this property")
    roles = list(row.reviewer_roles)
    if row.conflict_rule == "manual":
        return _result(
            "manual", "the policy leaves the choice to a reviewer", roles=roles
        )
    authoritative = {str(source_uri(s)) for s in row.authoritative}
    counted = [
        f
        for f in discrepancy["facts"]
        if f["source"] in authoritative and f["status"] in _COUNTED
    ]
    values = {f["value"] for f in counted}
    if not values:
        return _result(
            "unresolved", "no authoritative source asserts a value", roles=roles
        )
    if len(values) > 1:
        return _result(
            "unresolved",
            f"authoritative sources assert {len(values)} different values",
            roles=roles,
        )
    seen = {f["source"] for f in counted}
    sources = sorted(s for s in row.authoritative if str(source_uri(s)) in seen)
    rationale = (
        f"{', '.join(sources)} is authoritative; a reviewer must still accept it"
    )
    if any(not f["observed_in_latest_run"] for f in counted):
        rationale += "; the value is not in the latest run of its source"
    return _result(
        "recommend",
        rationale,
        recommended=sorted(f["assertion"] for f in counted),
        roles=roles,
    )


def _result(outcome, rationale, recommended=(), roles=()) -> dict:
    return {
        "outcome": outcome,
        "rationale": rationale,
        "recommended": list(recommended),
        "reviewer_roles": list(roles),
    }


def _row(row: object, where: str, source_ids: set[str]) -> PropertyPolicy:
    if not isinstance(row, dict):
        raise PolicyError(f"{where}: must be a table")
    name = row.get("property")
    if not isinstance(name, str) or name not in FIELD_PREDICATES:
        raise PolicyError(f"{where}: unknown property {name!r}")
    where = f"{where} ('{name}')"
    if unknown := set(row) - _ROW_KEYS:
        raise PolicyError(f"{where}: unknown keys {sorted(unknown)}")
    if "authoritative" not in row:
        raise PolicyError(f"{where}: 'authoritative' is required (it may be empty)")
    authoritative = _ids(row, "authoritative", where, source_ids)
    secondary = _ids(row, "secondary", where, source_ids)
    if both := sorted(set(authoritative) & set(secondary)):
        raise PolicyError(f"{where}: sources both authoritative and secondary: {both}")
    rule = row.get("conflict_rule")
    if rule not in CONFLICT_RULES:
        raise PolicyError(f"{where}: 'conflict_rule' must be one of {CONFLICT_RULES}")
    if rule == "prefer-authoritative" and not authoritative:
        raise PolicyError(
            f"{where}: prefer-authoritative needs an authoritative source"
        )
    freshness = row.get("freshness_days")
    if freshness is not None and (
        isinstance(freshness, bool) or not isinstance(freshness, int) or freshness < 1
    ):
        raise PolicyError(f"{where}: 'freshness_days' must be a positive integer")
    required = row.get("required", False)
    if not isinstance(required, bool):
        raise PolicyError(f"{where}: 'required' must be true or false")
    return PropertyPolicy(
        property=name,
        predicate=FIELD_PREDICATES[name],
        authoritative=authoritative,
        secondary=secondary,
        conflict_rule=rule,
        freshness_days=freshness,
        required=required,
        reviewer_roles=_strings(row, "reviewer_roles", where),
    )


def _strings(row: dict, key: str, where: str) -> tuple[str, ...]:
    value = row.get(key, [])
    if not isinstance(value, list) or not all(
        isinstance(v, str) and v.strip() for v in value
    ):
        raise PolicyError(f"{where}: '{key}' must be a list of non-blank strings")
    return tuple(v.strip() for v in value)


def _ids(row: dict, key: str, where: str, source_ids: set[str]) -> tuple[str, ...]:
    ids = _strings(row, key, where)
    if unknown := sorted(set(ids) - source_ids):
        raise PolicyError(f"{where}: '{key}' names unknown sources {unknown}")
    return ids

"""Data-quality findings (architecture §3.4, §4.6).

Computed each time a report is built and never stored. A finding carries no trust
state and nothing here writes to the graph: quality is not trust (ADR-0002).
"""

from collections import defaultdict
from datetime import date, datetime, timedelta

from .constants import EK
from .graph.store import KnowledgeStore
from .policy import Policy, in_force

# One fixed rationale per category. No severity scale: ranking is the data owner's.
INVALID = "the value failed structural validation in at least one run"
UNRESOLVED = "the row could not be tied to an employee: {reason}"
BROKEN_MANAGER = (
    "the manager ID is not the employee ID of any employee from the same issuer"
)
MISSING = (
    "the policy requires this property, and no source's latest run observed it "
    "for this employee"
)
STALE = "the newest observation time is older than the {days}-day freshness window"
UNKNOWN = (
    "the policy sets a freshness window, but the source gave no observation time; "
    "ingestion time is not used"
)
UNKNOWN_TZ = (
    "the policy sets a freshness window, but an observation time has no timezone "
    "or cannot be read; UTC is not assumed"
)


def findings(
    store: KnowledgeStore,
    policy: Policy | None,
    now: datetime,
    today: date | None = None,
) -> list[dict]:
    """Every finding, sorted. Without a policy in force on ``today`` (default
    ``now.date()``), only invalid-value, unresolved-identity and
    broken-manager-reference are checked. ``now`` must carry a timezone."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    observations = store.observations()
    latest = store.latest_runs()
    latest_runs = {str(run) for run, _ in latest.values()}
    known = store.employee_ids()
    rows = policy.properties if in_force(policy, today or now.date()) else {}
    out: list[dict] = []
    employees: dict = {}  # employee URI -> identity fields
    present = set()  # (employee, predicate) observed in some source's latest run
    latest_evidence = defaultdict(list)

    for _, assertion, graph in store.assertions():
        employee = graph.value(assertion, EK.aboutEmployee)
        predicate = graph.value(assertion, EK.predicate)
        source = str(graph.value(assertion, EK.fromSource))
        who = {
            "employee": str(employee),
            "employee_id": str(graph.value(employee, EK.employeeId)),
            "issuer": str(graph.value(employee, EK.issuer)),
        }
        obs = observations.get(assertion, [])
        hits = []  # (category, rationale, observations given as evidence)

        if violating := [o for o in obs if o["validation"] == "Violation"]:
            hits.append(("invalid-value", INVALID, violating))
        manager = (who["issuer"], str(graph.value(assertion, EK.value)))
        if predicate == EK.managerEmployeeId and manager not in known:
            hits.append(("broken-manager-reference", BROKEN_MANAGER, obs))
        if in_latest := [o for o in obs if o["run"] in latest_runs]:
            employees[employee] = who
            present.add((employee, predicate))
            latest_evidence[employee] += _evidence(assertion, source, in_latest)
        row = rows.get(predicate)
        if row is not None and row.freshness_days is not None:
            times = [o for o in obs if o["observed_at"]]
            # One unusable time hides which is newest: never stale on the others.
            unusable = [o for o in times if _zoned(o["observed_at"]) is None]
            if not times:
                hits.append(("freshness-unknown", UNKNOWN, obs))
            elif unusable:
                hits.append(("freshness-unknown", UNKNOWN_TZ, unusable))
            else:
                newest, o = max(
                    ((_zoned(o["observed_at"]), o) for o in times), key=lambda z: z[0]
                )
                if newest < now - timedelta(days=row.freshness_days):
                    hits.append(("stale", STALE.format(days=row.freshness_days), [o]))
        for category, rationale, evidence_obs in hits:
            out.append(
                {
                    "category": category,
                    "rationale": rationale,
                    **who,
                    "property": str(predicate),
                    "evidence": _evidence(assertion, source, evidence_obs),
                }
            )

    for employee, who in employees.items():
        for predicate, row in rows.items():
            if row.required and (employee, predicate) not in present:
                out.append(
                    {
                        "category": "missing-required",
                        "rationale": MISSING,
                        **who,
                        "property": str(predicate),
                        "evidence": _unique(latest_evidence[employee]),
                    }
                )

    for source, (_, graph) in latest.items():
        for q in store.quarantined(graph):
            out.append(
                {
                    "category": "unresolved-identity",
                    "rationale": UNRESOLVED.format(reason=q["reason"]),
                    "evidence": [
                        {
                            "source": str(source),
                            "source_reference": q["source_reference"],
                        }
                    ],
                }
            )

    return sorted(
        out,
        key=lambda f: (
            f["category"],
            f.get("issuer", ""),
            f.get("employee_id", ""),
            f.get("property", ""),
            f["evidence"][0]["source_reference"],
        ),
    )


def _evidence(assertion, source: str, obs: list[dict]) -> list[dict]:
    return _unique(
        {
            "assertion": str(assertion),
            "source": source,
            "source_reference": o["source_reference"],
            **({"observed_at": o["observed_at"]} if o["observed_at"] else {}),
        }
        for o in obs
    )


def _unique(entries) -> list[dict]:
    """Drop repeats (the same row seen in several runs), in a stable order."""
    unique = {tuple(sorted(e.items())): e for e in entries}
    return [unique[k] for k in sorted(unique)]


def _zoned(text: str) -> datetime | None:
    """The time, only when it states its timezone (owner decision, 2026-11-24)."""
    try:
        t = datetime.fromisoformat(text)
    except ValueError:
        return None
    return t if t.tzinfo is not None else None

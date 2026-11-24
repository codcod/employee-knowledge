"""Discrepancy report (architecture §4.6). Shows evidence; never picks a winner."""

from collections import defaultdict
from datetime import UTC, date, datetime

from . import quality
from .constants import EK
from .graph.store import KnowledgeStore
from .policy import Policy, evaluate, in_force
from .review import label


def build_report(
    store: KnowledgeStore,
    policy: Policy | None = None,
    today: date | None = None,
    now: datetime | None = None,
) -> dict:
    """``policy`` adds a recommendation to each discrepancy and turns on the required
    and freshness findings; it changes nothing."""
    now = now or datetime.now(UTC)
    today = today or now.date()
    observations = store.observations()
    latest = store.latest_runs()
    latest_seen = {src: store.observed(graph) for src, (_, graph) in latest.items()}

    facts, grouped = [], defaultdict(list)
    for graph_id, assertion, graph in store.assertions():
        employee = graph.value(assertion, EK.aboutEmployee)
        source = graph.value(assertion, EK.fromSource)
        fact = {
            "assertion": str(assertion),
            "employee": str(employee),
            "employee_id": str(graph.value(employee, EK.employeeId)),
            "issuer": str(graph.value(employee, EK.issuer)),
            "property": str(graph.value(assertion, EK.predicate)),
            "value": str(graph.value(assertion, EK.value)),
            "source": str(source),
            "graph": str(graph_id),
            "status": label(store.state(assertion)),
            # Absence is computed here, never stored, and never changes state.
            "observed_in_latest_run": assertion in latest_seen.get(source, set()),
            "observations": observations.get(assertion, []),
        }
        facts.append(fact)
        grouped[(fact["employee"], fact["property"])].append(fact)

    discrepancies = []
    for (employee, prop), group in sorted(grouped.items()):
        values = sorted({f["value"] for f in group})
        accepted = {f["value"] for f in group if f["status"] == "Accepted"}
        if len(values) > 1:
            item = {
                "employee": employee,
                "employee_id": group[0]["employee_id"],
                "property": prop,
                "values": values,
                "accepted_conflict": len(accepted) > 1,
                "facts": sorted(group, key=lambda f: (f["source"], f["value"])),
            }
            item["policy"] = evaluate(policy, item, today)
            discrepancies.append(item)

    def key(f):
        return (f["employee_id"], f["property"], f["source"], f["value"])

    return {
        "policy": None
        if policy is None
        else {"version": policy.version, "in_force": in_force(policy, today)},
        "discrepancies": discrepancies,
        "not_observed": sorted(
            (f for f in facts if not f["observed_in_latest_run"]), key=key
        ),
        "validation_violations": sorted(
            (
                f
                for f in facts
                if any(o["validation"] == "Violation" for o in f["observations"])
            ),
            key=key,
        ),
        "quarantined": [
            {"source": str(src), "run": str(run), **q}
            for src, (run, graph) in sorted(latest.items())
            for q in store.quarantined(graph)
        ],
        "findings": quality.findings(store, policy, now, today),
    }

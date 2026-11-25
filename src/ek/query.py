"""Read-only fact lookup with an explicit trust scope (architecture §4.8).

Trusted scope answers from accepted assertions only and counts, but never shows, the
values still awaiting or refused acceptance. All scope shows every assertion with its
review state. Neither picks a value. Nothing here writes to the store.
"""

from collections import defaultdict
from enum import StrEnum

from rdflib import URIRef

from .constants import FIELD_PREDICATES, TRUSTED_GRAPH
from .graph.store import KnowledgeStore
from .reconcile import assertion_facts


class Scope(StrEnum):
    TRUSTED = "trusted"
    ALL = "all"


class QueryError(ValueError):
    pass


def query_facts(
    store: KnowledgeStore,
    *,
    scope: Scope,
    employee_id: str | None = None,
    issuer: str | None = None,
    property: str | None = None,
) -> list[dict]:
    """Facts grouped by (employee, property). ``scope`` is required: there is no
    default trust level. ``property`` is a field name from ``FIELD_PREDICATES``.
    Groups are never merged across issuers (ADR-0004)."""
    try:
        scope = Scope(scope)
    except ValueError as exc:
        raise QueryError(f"Unknown scope '{scope}'; use trusted or all") from exc
    predicate = None
    if property is not None:
        if property not in FIELD_PREDICATES:
            raise QueryError(
                f"Unknown property '{property}'; use one of "
                + ", ".join(sorted(FIELD_PREDICATES))
            )
        predicate = str(FIELD_PREDICATES[property])
    # A projection that disagrees with the audit graph could put an unaccepted value
    # in the trusted graph: refuse to answer rather than leak it (ADR-0002).
    if scope is Scope.TRUSTED and store.check_projection():
        raise QueryError("projection out of date; run rebuild-projection")

    # ponytail: every assertion's state and latest review rescans the audit graph, and
    # filters apply after that; index events by assertion once per query when slow.
    grouped = defaultdict(list)
    for f in assertion_facts(store):
        if (
            (employee_id is None or f["employee_id"] == employee_id)
            and (issuer is None or f["issuer"] == issuer)
            and (predicate is None or f["property"] == predicate)
        ):
            grouped[(f["employee"], f["property"])].append(f)

    results = []
    for (employee, prop), group in grouped.items():
        if scope is Scope.TRUSTED:
            shown = [f for f in group if f["graph"] == str(TRUSTED_GRAPH)]
        else:
            shown = group
        values = sorted({f["value"] for f in shown})
        item = {
            "employee": employee,
            "employee_id": group[0]["employee_id"],
            "issuer": group[0]["issuer"],
            "property": prop,
            "values": values,
            "conflict": len(values) > 1,
            "facts": [
                {**f, "latest_review": store.latest_review(URIRef(f["assertion"]))}
                for f in sorted(shown, key=lambda f: (f["source"], f["value"]))
            ],
        }
        if scope is Scope.TRUSTED:
            item["untrusted_candidates"] = len(
                {f["value"] for f in group if f["status"] != "Accepted"} - set(values)
            )
        results.append(item)
    return sorted(results, key=lambda i: (i["employee_id"], i["issuer"], i["property"]))

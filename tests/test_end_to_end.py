"""Architecture §11: the first milestone, end to end, on the synthetic examples.

Each step is marked with its number from development/architecture.md §11. Step 12
(nothing real committed) is tests/test_repository.py.
"""

import json
from pathlib import Path

from rdflib import URIRef
from typer.testing import CliRunner

from ek.constants import AUDIT_GRAPH, EK, TRUSTED_GRAPH, UNTRUSTED_GRAPH
from ek.graph.store import KnowledgeStore
from ek.identity import source_uri

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
CONFIG = str(EXAMPLES / "sources.toml")


def test_first_milestone(tmp_path, monkeypatch):
    from ek.cli import app

    store_path = tmp_path / "store.trig"
    monkeypatch.setenv("EMPLOYEE_KNOWLEDGE_STORE", str(store_path))
    runner = CliRunner()

    def cli(*args):
        result = runner.invoke(app, [str(a) for a in args])
        assert result.exit_code == 0, result.output
        return result.output

    def ingest(workbook, source_id):
        return cli(
            "ingest-excel",
            EXAMPLES / workbook,
            "--source-id",
            source_id,
            "--config",
            CONFIG,
        )

    def report():
        out = tmp_path / "report.json"
        cli("report-json", "--output", out)
        return json.loads(out.read_text())

    # 1-2. Configured sheet and mapping; a stable employee ID is required.
    ingest("employees.xlsx", "hr-export")
    out = ingest("employees-directory.xlsx", "people-directory")  # 6. second source
    assert (
        "Quarantined employees-directory.xlsx#Directory!5: missing employee ID" in out
    )

    store = KnowledgeStore(store_path)
    untrusted = store.dataset.graph(UNTRUSTED_GRAPH)
    all_assertions = set(untrusted.subjects(None, EK.FactAssertion))
    # 4. Everything starts untrusted; nothing is trusted or audited yet.
    assert len(all_assertions) == 20 + 15  # HR: 3 rows x 7 - 1 blank; dir: 3 x 5
    assert len(store.dataset.graph(TRUSTED_GRAPH)) == 0
    assert len(store.dataset.graph(AUDIT_GRAPH)) == 0

    # 3. Each value has source/sheet/row provenance. 5. Each was validated.
    observations = store.observations()
    assert set(observations) == all_assertions
    for obs_list in observations.values():
        for obs in obs_list:
            assert obs["source_reference"].split("#")[1].split("!")[0] in (
                "Employees",
                "Directory",
            )
            assert obs["validation"] == "Conforms"

    # 7. The report shows both values with their source references, and only the
    # real conflict: E-1001's " Engineering " equals "Engineering" after trimming.
    data = report()
    [conflict] = data["discrepancies"]
    assert (conflict["employee_id"], conflict["property"]) == (
        "E-1002",
        str(EK.department),
    )
    assert conflict["values"] == ["People", "Product"]
    facts = {f["source"]: f for f in conflict["facts"]}
    hr = facts[str(source_uri("hr-export"))]
    directory = facts[str(source_uri("people-directory"))]
    assert hr["observations"][0]["source_reference"] == "employees.xlsx#Employees!3"
    assert directory["observations"][0]["source_reference"] == (
        "employees-directory.xlsx#Directory!3"
    )
    assert [q["source_reference"] for q in data["quarantined"]] == [
        "employees-directory.xlsx#Directory!5"
    ]

    # 8. Accept the HR value through an explicit CLI action.
    cli(
        "review",
        "accept",
        hr["assertion"],
        "--reviewer",
        "reviewer-1",
        "--reason",
        "Matches the synthetic HR system of record",
    )

    # 9. It is in the trusted graph, with an audit event.
    store = KnowledgeStore(store_path)
    accepted = URIRef(hr["assertion"])
    assert store.graph_of(accepted) == TRUSTED_GRAPH
    [event] = store.events(accepted)
    audit = store.dataset.graph(AUDIT_GRAPH)
    assert str(audit.value(event, EK.reviewer)) == "reviewer-1"
    assert audit.value(event, EK.toState) == EK.Accepted

    # 10. The competing value is still there and still a candidate; history is kept.
    competitor = URIRef(directory["assertion"])
    assert store.graph_of(competitor) == UNTRUSTED_GRAPH
    assert store.state(competitor) == EK.Candidate
    assert len(report()["discrepancies"]) == 1

    # 11. Re-ingestion is idempotent: new runs and observations, no new assertions,
    # no state change, projection consistent.
    assert "(0 new" in ingest("employees.xlsx", "hr-export")
    assert "(0 new" in ingest("employees-directory.xlsx", "people-directory")
    store = KnowledgeStore(store_path)
    assert {a for _, a, _ in store.assertions()} == all_assertions
    assert store.state(accepted) == EK.Accepted
    assert store.check_projection() == []
    assert len(store.completed_runs(source_uri("hr-export"))) == 2
    after = report()
    assert after["not_observed"] == []
    assert len(after["discrepancies"][0]["facts"][0]["observations"]) == 2

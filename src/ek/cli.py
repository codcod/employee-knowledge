import json
import os
import typing as tp
from datetime import UTC, datetime
from pathlib import Path

import typer
from rdflib import URIRef
from rich import print
from rich.markup import escape
from rich.table import Table
from rich.text import Text

from .adapters.base import SourceError
from .adapters.excel import ExcelAdapter
from .config import DEFAULT_CONFIG, ConfigError, get_source, load_sources
from .constants import TRUSTED_GRAPH, UNTRUSTED_GRAPH
from .graph.store import KnowledgeStore
from .ingest import IngestError, ingest
from .policy import (
    DEFAULT_POLICY,
    Policy,
    PolicyError,
    in_force,
    load_policy,
    version_in_force,
)
from .query import QueryError, Scope, query_facts
from .reconcile import build_report
from .review import ReviewError, label, review

app = typer.Typer(help="Employee Knowledge Graph")


def store_path():
    return Path(os.getenv("EMPLOYEE_KNOWLEDGE_STORE", "./data/employee-knowledge.trig"))


def _today():
    return datetime.now(UTC).date()


PolicyPath = tp.Annotated[
    Path | None,
    typer.Option(
        "--policy",
        help=f"Authority policy (default {DEFAULT_POLICY}; no policy if that is absent)",
        show_default=False,
    ),
]
ConfigPath = tp.Annotated[
    Path, typer.Option("--config", help="Sources, to check the policy's source ids")
]


def _policy(path: Path | None, config: Path) -> Policy | None:
    """The authority policy, or None when the default file is absent. Exits 1 when
    it is invalid, or named with --policy and missing: never fall back to no policy
    (ADR-0010). Policy text is escaped: it is not Rich markup."""
    try:
        if path is not None and not path.exists():
            raise PolicyError(f"{path}: policy file not found")
        path = path or DEFAULT_POLICY
        policy = load_policy(path, set(load_sources(config))) if path.exists() else None
    except (PolicyError, ConfigError) as exc:
        print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(1) from exc
    if policy is None:
        print("No authority policy loaded; conflicts stay unresolved.")
    elif not in_force(policy, _today()):
        print(
            f"[yellow]Policy {escape(policy.version)} is not in force until "
            f"{policy.effective_from}; it is treated as no policy.[/yellow]"
        )
    return policy


def _policy_line(data: dict, item: dict) -> str:
    where = f"{item['employee_id']} {_short(item['property'])}"
    if not (data["policy"] and data["policy"]["in_force"]):
        return f"{where}: no authority policy: unresolved"
    p = item["policy"]
    line = f"{where}: policy {data['policy']['version']}: {p['outcome']}: "
    line += p["rationale"]
    if p["reviewer_roles"]:
        line += f" (reviewer roles: {', '.join(p['reviewer_roles'])})"
    return line


@app.command("ingest-excel")
def ingest_excel(
    workbook: tp.Annotated[Path, typer.Argument(exists=True, readable=True)],
    source_id: tp.Annotated[str, typer.Option("--source-id")],
    config: tp.Annotated[Path, typer.Option("--config")] = DEFAULT_CONFIG,
):
    started = datetime.now(UTC)
    try:
        source = get_source(load_sources(config), source_id)
        if source.kind != "excel":
            raise ConfigError(f"Source '{source_id}' is not an Excel source")
        result = ExcelAdapter(workbook, source).read()
        store = KnowledgeStore(store_path())
        summary = ingest(store, source, result, started)
    except (ConfigError, SourceError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    except IngestError as exc:
        # A bug, not bad source data. Shapes and paths only: messages may hold values.
        print(f"[red]{exc}. Nothing was saved.[/red]")
        for f in exc.findings:
            print(f"[red]  {f.shape} {f.path or ''}[/red]")
        raise typer.Exit(2) from exc
    store.save()
    print(
        f"[green]Run {summary.run} completed:[/green] {summary.observations} "
        f"observations of {summary.assertions} assertions "
        f"({summary.new_assertions} new, added to the untrusted graph)."
    )
    print(f"Workbook sha256 {result.sha256}")
    if summary.value_violations:
        print(
            f"[yellow]{summary.value_violations} observations failed value "
            "validation; they are stored and flagged.[/yellow]"
        )
    # References and reasons only: no cell values, so no employee data on screen.
    for q in result.quarantined:
        print(f"[yellow]Quarantined {q.source_reference}: {q.reason}[/yellow]")


def _short(iri: str) -> str:
    return iri.rsplit("#", 1)[-1].rsplit(":", 1)[-1]


def _flags(fact: dict) -> str:
    flags = [] if fact["observed_in_latest_run"] else ["not in latest run"]
    if any(o["validation"] == "Violation" for o in fact["observations"]):
        flags.append("invalid")
    return ", ".join(flags)


@app.command("report")
def report(policy: PolicyPath = None, config: ConfigPath = DEFAULT_CONFIG):
    """Print discrepancies with the policy's recommendation, values no longer
    observed and data-quality findings. Never picks a winner."""
    data = build_report(KnowledgeStore(store_path()), _policy(policy, config))
    columns = ("Employee", "Property", "Value", "Source", "State", "Flags")

    def table(title, rows):
        t = Table(title=title)
        for heading in columns:
            t.add_column(heading)
        for row in rows:
            t.add_row(*row)
        return t

    def row(f):
        return (
            f["employee_id"],
            _short(f["property"]),
            f["value"],
            _short(f["source"]),
            f["status"],
            _flags(f),
        )

    if data["discrepancies"]:
        t = table("Discrepancies", [])
        for item in data["discrepancies"]:
            for f in item["facts"]:
                t.add_row(*row(f))
            if item["accepted_conflict"]:
                t.add_row("", "", "[red]conflicting values are both accepted[/red]")
            t.add_section()
        print(t)
        # Outside the table, so a long rationale does not wrap into the cells.
        for item in data["discrepancies"]:
            print(escape(_policy_line(data, item)))
    else:
        print("[green]No conflicting values detected.[/green]")
    if data["not_observed"]:
        print(table("Not observed in the latest run", map(row, data["not_observed"])))
    if data["findings"]:
        # References and rationales only, no values. Source text is not Rich markup.
        t = Table(title="Data-quality findings")
        for heading in ("Category", "Employee", "Property", "Evidence", "Rationale"):
            t.add_column(heading)
        for f in data["findings"]:
            refs = sorted(
                {
                    f"{_short(e['source'])}: {e['source_reference']}"
                    for e in f["evidence"]
                }
            )
            t.add_row(
                f["category"],
                escape(f.get("employee_id", "")),
                _short(f.get("property", "")),
                escape(", ".join(refs)),
                escape(f["rationale"]),
            )
        print(t)
    if not (data["policy"] and data["policy"]["in_force"]):
        print("Required and freshness checks are off: no authority policy is in force.")


@app.command("report-json")
def report_json(
    output: tp.Annotated[Path, typer.Option("--output")] = Path(
        "reports/discrepancies.json"
    ),
    policy: PolicyPath = None,
    config: ConfigPath = DEFAULT_CONFIG,
):
    """Write the full report, with every observation, as JSON."""
    data = build_report(KnowledgeStore(store_path()), _policy(policy, config))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote {output}")


@app.command("query")
def query(
    scope: tp.Annotated[
        Scope,
        typer.Option(
            "--scope", help="trusted: accepted only. all: every assertion, with state"
        ),
    ],
    employee_id: tp.Annotated[str | None, typer.Option("--employee-id")] = None,
    issuer: tp.Annotated[str | None, typer.Option("--issuer")] = None,
    property: tp.Annotated[
        str | None, typer.Option("--property", help="Field name, e.g. department")
    ] = None,
    as_json: tp.Annotated[bool, typer.Option("--json", help="Print JSON")] = False,
):
    """Look up facts by employee and/or property. Read-only; never picks a value."""
    try:
        results = query_facts(
            KnowledgeStore(store_path()),
            scope=scope,
            employee_id=employee_id,
            issuer=issuer,
            property=property,
        )
    except QueryError as exc:
        print(Text(str(exc), style="red"))
        raise typer.Exit(1) from exc
    if as_json:
        typer.echo(json.dumps(results, indent=2))
        return
    if scope is Scope.TRUSTED:
        title = (
            f"Scope trusted: facts from {TRUSTED_GRAPH}; unaccepted values counted, "
            "not shown"
        )
    else:
        title = f"Scope all: facts from {TRUSTED_GRAPH} and {UNTRUSTED_GRAPH}"
    t = Table(title=title)
    for heading in ("Employee", "Issuer", "Property", "Value", "Source", "State"):
        t.add_column(heading)
    t.add_column("References")
    # Text cells: source values are not Rich markup.
    for item in results:
        for f in item["facts"]:
            refs = sorted({o["source_reference"] for o in f["observations"]})
            t.add_row(
                *map(
                    Text,
                    (
                        f["employee_id"],
                        f["issuer"],
                        _short(f["property"]),
                        f["value"],
                        _short(f["source"]),
                        f["status"],
                        ", ".join(refs),
                    ),
                )
            )
        if item["conflict"]:
            t.add_row("", "", "", Text("conflicting values; none is picked", "red"))
        if item["facts"]:
            t.add_section()
    print(t)
    for item in results:
        where = f"{item['employee_id']} ({item['issuer']}) {_short(item['property'])}"
        n = item.get("untrusted_candidates", 0)
        if not item["facts"]:
            print(Text(f"{where}: no trusted value.", "yellow"))
        if n:
            print(
                Text(
                    f"{where}: {n} unaccepted value(s) not shown; use --scope all",
                    "yellow",
                )
            )


review_app = typer.Typer(
    help="Record a review decision. The reviewer is a local label, not authentication."
)
app.add_typer(review_app, name="review")

Assertion = tp.Annotated[str, typer.Argument(help="Assertion URI from report-json")]
Reviewer = tp.Annotated[str, typer.Option("--reviewer", help="Local label only")]
Reason = tp.Annotated[str, typer.Option("--reason")]


def _review(assertion, action, reviewer, reason, policy, config, superseded_by=None):
    # Load the policy first: an invalid one must leave no event behind.
    version = version_in_force(_policy(policy, config), _today())
    store = KnowledgeStore(store_path())
    try:
        outcome = review(
            store,
            URIRef(assertion),
            action,
            reviewer=reviewer,
            reason=reason,
            superseded_by=URIRef(superseded_by) if superseded_by else None,
            policy_version=version,
        )
    except ReviewError as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    store.save()
    print(
        f"[green]{label(outcome.from_state)} -> {label(outcome.to_state)}[/green]; "
        f"event {outcome.event} recorded in the audit graph (policy {escape(version)})."
    )
    for other in outcome.accepted_conflicts:
        print(f"[yellow]Also accepted with a different value: {other}[/yellow]")


@review_app.command("accept")
def review_accept(
    assertion: Assertion,
    reviewer: Reviewer,
    reason: Reason,
    policy: PolicyPath = None,
    config: ConfigPath = DEFAULT_CONFIG,
):
    _review(assertion, "accept", reviewer, reason, policy, config)


@review_app.command("reject")
def review_reject(
    assertion: Assertion,
    reviewer: Reviewer,
    reason: Reason,
    policy: PolicyPath = None,
    config: ConfigPath = DEFAULT_CONFIG,
):
    _review(assertion, "reject", reviewer, reason, policy, config)


@review_app.command("request-evidence")
def review_request_evidence(
    assertion: Assertion,
    reviewer: Reviewer,
    reason: Reason,
    policy: PolicyPath = None,
    config: ConfigPath = DEFAULT_CONFIG,
):
    _review(assertion, "request-evidence", reviewer, reason, policy, config)


@review_app.command("supersede")
def review_supersede(
    assertion: Assertion,
    reviewer: Reviewer,
    reason: Reason,
    by: tp.Annotated[
        str | None, typer.Option("--by", help="URI of the replacing assertion")
    ] = None,
    policy: PolicyPath = None,
    config: ConfigPath = DEFAULT_CONFIG,
):
    _review(assertion, "supersede", reviewer, reason, policy, config, by)


@review_app.command("reopen")
def review_reopen(
    assertion: Assertion,
    reviewer: Reviewer,
    reason: Reason,
    policy: PolicyPath = None,
    config: ConfigPath = DEFAULT_CONFIG,
):
    _review(assertion, "reopen", reviewer, reason, policy, config)


@app.command("rebuild-projection")
def rebuild_projection(
    check: tp.Annotated[
        bool, typer.Option("--check", help="Report mismatches; change nothing")
    ] = False,
):
    """Recompute the trusted and untrusted graphs from the audit graph."""
    store = KnowledgeStore(store_path())
    mismatches = store.check_projection()
    for assertion, graph, state in mismatches:
        print(f"[yellow]{assertion} is in {graph} but is {label(state)}[/yellow]")
    if check:
        if mismatches:
            raise typer.Exit(1)
        print("[green]Projection matches the audit graph.[/green]")
        return
    store.rebuild_projection()
    store.save()
    print(f"[green]Projection rebuilt; {len(mismatches)} assertions moved.[/green]")


if __name__ == "__main__":
    app()

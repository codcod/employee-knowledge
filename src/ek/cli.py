import json
import os
import typing as tp
from datetime import UTC, datetime
from pathlib import Path

import typer
from rdflib import URIRef
from rich import print
from rich.table import Table

from .adapters.base import SourceError
from .adapters.excel import ExcelAdapter
from .config import DEFAULT_CONFIG, ConfigError, get_source, load_sources
from .graph.store import KnowledgeStore
from .ingest import IngestError, ingest
from .reconcile import build_report
from .review import ReviewError, label, review

app = typer.Typer(help="Employee Knowledge Graph")


def store_path():
    return Path(os.getenv("EMPLOYEE_KNOWLEDGE_STORE", "./data/employee-knowledge.trig"))


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
def report():
    """Print discrepancies, values no longer observed, invalid values and
    quarantined rows. Never picks a winner."""
    data = build_report(KnowledgeStore(store_path()))
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
    else:
        print("[green]No conflicting values detected.[/green]")
    if data["not_observed"]:
        print(table("Not observed in the latest run", map(row, data["not_observed"])))
    if data["validation_violations"]:
        print(table("Invalid values", map(row, data["validation_violations"])))
    if data["quarantined"]:
        t = Table(title="Quarantined rows (latest run of each source)")
        for heading in ("Source", "Reference", "Reason"):
            t.add_column(heading)
        for q in data["quarantined"]:
            t.add_row(_short(q["source"]), q["source_reference"], q["reason"])
        print(t)


@app.command("report-json")
def report_json(
    output: tp.Annotated[Path, typer.Option("--output")] = Path(
        "reports/discrepancies.json"
    ),
):
    """Write the full report, with every observation, as JSON."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build_report(KnowledgeStore(store_path())), indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {output}")


review_app = typer.Typer(
    help="Record a review decision. The reviewer is a local label, not authentication."
)
app.add_typer(review_app, name="review")

Assertion = tp.Annotated[str, typer.Argument(help="Assertion URI from report-json")]
Reviewer = tp.Annotated[str, typer.Option("--reviewer", help="Local label only")]
Reason = tp.Annotated[str, typer.Option("--reason")]


def _review(assertion, action, reviewer, reason, superseded_by=None):
    store = KnowledgeStore(store_path())
    try:
        outcome = review(
            store,
            URIRef(assertion),
            action,
            reviewer=reviewer,
            reason=reason,
            superseded_by=URIRef(superseded_by) if superseded_by else None,
        )
    except ReviewError as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    store.save()
    print(
        f"[green]{label(outcome.from_state)} -> {label(outcome.to_state)}[/green]; "
        f"event {outcome.event} recorded in the audit graph."
    )
    for other in outcome.accepted_conflicts:
        print(f"[yellow]Also accepted with a different value: {other}[/yellow]")


@review_app.command("accept")
def review_accept(assertion: Assertion, reviewer: Reviewer, reason: Reason):
    _review(assertion, "accept", reviewer, reason)


@review_app.command("reject")
def review_reject(assertion: Assertion, reviewer: Reviewer, reason: Reason):
    _review(assertion, "reject", reviewer, reason)


@review_app.command("request-evidence")
def review_request_evidence(assertion: Assertion, reviewer: Reviewer, reason: Reason):
    _review(assertion, "request-evidence", reviewer, reason)


@review_app.command("supersede")
def review_supersede(
    assertion: Assertion,
    reviewer: Reviewer,
    reason: Reason,
    by: tp.Annotated[
        str | None, typer.Option("--by", help="URI of the replacing assertion")
    ] = None,
):
    _review(assertion, "supersede", reviewer, reason, by)


@review_app.command("reopen")
def review_reopen(assertion: Assertion, reviewer: Reviewer, reason: Reason):
    _review(assertion, "reopen", reviewer, reason)


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

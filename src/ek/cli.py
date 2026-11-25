import hashlib
import json
import os
import re
import typing as tp
from datetime import UTC, datetime
from pathlib import Path

import typer
from rdflib import URIRef
from rich import print
from rich.table import Table
from rich.text import Text

from .adapters.base import ReadResult, SourceError
from .adapters.registry import load_adapter
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


_CONTROL = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]")  # Cc except tab


def _clean(value: object) -> str:
    """External text as written, but with control characters other than tab shown
    as visible escapes (\\x1b, \\n), so they never reach the terminal raw."""
    return _CONTROL.sub(lambda m: m[0].encode("unicode_escape").decode(), str(value))


def _say(*parts: str | tuple[str, str]) -> None:
    """Print as Text: not parsed for Rich markup or emoji. A part is text, or
    (text, style)."""
    print(
        Text.assemble(
            *(
                (_clean(p[0]), p[1]) if isinstance(p, tuple) else _clean(p)
                for p in parts
            )
        )
    )


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
    (ADR-0010). Policy text is printed as written: it is not Rich markup."""
    try:
        if path is not None and not path.exists():
            raise PolicyError(f"{path}: policy file not found")
        path = path or DEFAULT_POLICY
        policy = load_policy(path, set(load_sources(config))) if path.exists() else None
    except (PolicyError, ConfigError) as exc:
        _say((str(exc), "red"))
        raise typer.Exit(1) from exc
    if policy is None:
        print("No authority policy loaded; conflicts stay unresolved.")
    elif not in_force(policy, _today()):
        when = policy.effective_from
        msg = f"Policy {policy.version} is not in force until {when}; it is treated as"
        _say((f"{msg} no policy.", "yellow"))
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


SourceFile = tp.Annotated[Path, typer.Argument(exists=True, readable=True)]
SourceId = tp.Annotated[str, typer.Option("--source-id")]
SourcesPath = tp.Annotated[Path, typer.Option("--config")]


@app.command("ingest")
def ingest_file(
    path: SourceFile, source_id: SourceId, config: SourcesPath = DEFAULT_CONFIG
):
    """Ingest a file with the adapter of its source's kind."""
    _ingest(path, source_id, config)


@app.command("ingest-excel")
def ingest_excel(
    workbook: SourceFile, source_id: SourceId, config: SourcesPath = DEFAULT_CONFIG
):
    _ingest(workbook, source_id, config, excel_only=True)


def _check_file(path: Path, result: ReadResult) -> None:
    """File provenance is checked by ek, not taken from the adapter (ADR-0011)."""
    if result.file_name != path.name:
        raise SourceError(f"{path.name}: the adapter reported another file name")
    if result.sha256 != hashlib.sha256(path.read_bytes()).hexdigest():
        raise SourceError(
            f"{path.name}: the adapter's sha256 does not match the file "
            "(or the file changed while it was read)"
        )


def _ingest(path: Path, source_id: str, config: Path, excel_only: bool = False):
    started = datetime.now(UTC)
    try:
        source = get_source(load_sources(config), source_id)
        if excel_only and source.kind != "excel":
            raise ConfigError(f"Source '{source_id}' is not an Excel source")
        # Enabled sources always have a plugin: placeholders must be disabled.
        result = load_adapter(source.kind).read(path, source)
        _check_file(path, result)
        store = KnowledgeStore(store_path())
        summary = ingest(store, source, result, started)
    except (ConfigError, SourceError) as exc:
        _say((str(exc), "red"))
        raise typer.Exit(1) from exc
    except IngestError as exc:
        # A bug, not bad source data. Shapes and paths only: messages may hold values.
        _say((f"{exc}. Nothing was saved.", "red"))
        for f in exc.findings:
            _say((f"  {f.shape} {f.path or ''}", "red"))
        raise typer.Exit(2) from exc
    store.save()
    _say(
        (f"Run {summary.run} completed:", "green"),
        f" {summary.observations} observations of {summary.assertions} assertions "
        f"({summary.new_assertions} new, added to the untrusted graph).",
    )
    _say(f"File sha256 {result.sha256}")
    if summary.value_violations:
        msg = f"{summary.value_violations} observations failed value validation;"
        _say((f"{msg} they are stored and flagged.", "yellow"))
    # References and reasons only: no cell values, so no employee data on screen.
    for q in result.quarantined:
        _say((f"Quarantined {q.source_reference}: {q.reason}", "yellow"))


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
        cells = (
            f["employee_id"],
            _short(f["property"]),
            f["value"],
            _short(f["source"]),
            f["status"],
            _flags(f),
        )
        return [Text(_clean(c)) for c in cells]

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
            _say(_policy_line(data, item))
    else:
        print("[green]No conflicting values detected.[/green]")
    if data["not_observed"]:
        print(table("Not observed in the latest run", map(row, data["not_observed"])))
    if data["findings"]:
        # References and rationales only, no values.
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
            cells = (
                f["category"],
                f.get("employee_id", ""),
                _short(f.get("property", "")),
                ", ".join(refs),
                f["rationale"],
            )
            t.add_row(*(Text(_clean(c)) for c in cells))
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
    _say(f"Wrote {output}")


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
        _say((str(exc), "red"))
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
    for item in results:
        for f in item["facts"]:
            refs = sorted({o["source_reference"] for o in f["observations"]})
            cells = (
                f["employee_id"],
                f["issuer"],
                _short(f["property"]),
                f["value"],
                _short(f["source"]),
                f["status"],
                ", ".join(refs),
            )
            t.add_row(*(Text(_clean(c)) for c in cells))
        if item["conflict"]:
            t.add_row("", "", "", Text("conflicting values; none is picked", "red"))
        if item["facts"]:
            t.add_section()
    print(t)
    for item in results:
        where = f"{item['employee_id']} ({item['issuer']}) {_short(item['property'])}"
        n = item.get("untrusted_candidates", 0)
        if not item["facts"]:
            _say((f"{where}: no trusted value.", "yellow"))
        if n:
            _say(
                (
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
        _say((str(exc), "red"))
        raise typer.Exit(1) from exc
    store.save()
    _say(
        (f"{label(outcome.from_state)} -> {label(outcome.to_state)}", "green"),
        f"; event {outcome.event} recorded in the audit graph (policy {version}).",
    )
    for other in outcome.accepted_conflicts:
        _say((f"Also accepted with a different value: {other}", "yellow"))


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
        _say((f"{assertion} is in {graph} but is {label(state)}", "yellow"))
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

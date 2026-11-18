# Employee Knowledge

A provenance-first employee knowledge graph. The MVP ingests Excel workbooks, maps
records to an employee ontology, keeps accepted and unreviewed assertions separate, and
reports conflicting values with source evidence.

## Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
mkdir -p config && cp examples/sources.toml config/sources.toml
uv run employee-knowledge ingest-excel examples/employees.xlsx --source-id hr-export
uv run employee-knowledge ingest-excel examples/employees-directory.xlsx --source-id people-directory
uv run employee-knowledge report
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

The full walkthrough, including review, is in
[docs/operating.md](docs/operating.md#example-run). The local TriG store defaults to
`./data/employee-knowledge.trig`. Override it with `EMPLOYEE_KNOWLEDGE_STORE`.

## Trust model

Every ingested value is a separate assertion that starts untrusted and becomes trusted
only through an explicit, audited review. See [docs/trust-model.md](docs/trust-model.md).

## Scope

Included: configured Excel ingestion with per-run provenance, an RDF ontology with SHACL
validation, immutable assertions, audited review actions, a discrepancy report, two
synthetic sample workbooks and tests.

Confluence, Jira and Power BI have connector placeholders only. Before enabling them,
define read-only access scopes, credentials, source ownership and field mappings.

## Privacy

Synthetic people only. Never commit real employee data, graph stores, exports, reports or
credentials.

## Pickle / Brine

Pickle/Brine is the development workflow layer, not part of the platform. The board is
[tickets/BOARD.md](tickets/BOARD.md); tickets are `EK-NNN`. Jira as a data source is
separate from Brine's own board.

## Documentation

- [docs/](docs/): the product and how to operate it ([trust model](docs/trust-model.md),
  [operating guide](docs/operating.md), [source onboarding](docs/source-onboarding.md)).
- [development/](development/): [architecture](development/architecture.md),
  [roadmap](development/roadmap.md), [decisions](development/decisions/).
- [AGENTS.md](AGENTS.md): rules for coding agents.

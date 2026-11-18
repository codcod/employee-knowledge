# ADR-0005: Graph storage for the prototype

- **Status:** Accepted (2026-11-17)
- **Supersedes:** ADR-004 (one-line entry)
- **Related:** ADR-0002, ADR-0003

## Context

The prototype needs local, portable, inspectable storage with named graphs (architecture
§4.5, §9). The old store had three problems:

- It used `ConjunctiveGraph`, which is deprecated in RDFLib 7.
- It loaded and rewrote the whole TriG file on every command, in place: a crash
  mid-write corrupts the store.
- Nothing stopped two commands writing at the same time.

The review also asked whether RDF is worth its cost, compared with a relational
assertion log.

## Decision

- Keep RDF as the canonical representation. Use RDFLib's `Dataset` and persist it as one
  TriG file.
- **Atomic save:** write to a temporary file in the same directory, flush it, then
  `os.replace` it over the store. A failed command leaves the previous store intact.
- **One writer at a time.** No lock in the prototype. The operating guide says so.
- All graph access goes through `KnowledgeStore`. Adapters, ingestion, review and
  reconciliation never touch RDFLib storage directly, so the engine can change without
  rewriting them.

### RDF vs relational

| | RDF (chosen) | Relational assertion log |
|---|---|---|
| Fit for the assertion and provenance model | Needs reification (ADR-0001) | Natural: assertion, observation and event tables |
| Ontology and SHACL | Native | Would need a separate schema layer |
| NL→SPARQL, graph queries | Native | Needs translation or text-to-SQL |
| Tooling maturity | Moderate | High |
| Operational cost | Higher in production | Low |

RDF stays because the ontology, SHACL validation and later SPARQL querying are core to
the architecture. The reification cost is accepted.

### When to reconsider

Reconsider when any of these happens:

- more than one concurrent writer is needed;
- load and save time becomes noticeable;
- production deployment (M4).

A managed graph store (or a relational store behind the same interface) is chosen at that
point by a new ADR.

## Alternatives considered

- **SQLite/Postgres assertion tables.** Simpler storage and transactions, but loses
  native ontology, SHACL and SPARQL. Rejected for now; see the table.
- **A file lock now.** A small cost, but no concurrent use exists yet. Add it when it does.
- **One file per named graph.** Cheaper incremental writes, but makes a run's writes
  harder to keep atomic. Not needed at prototype scale.

## Consequences

- Concurrent commands can lose writes. That is documented, not prevented.
- Store size and command time grow with every run (ADR-0003). Acceptable for synthetic
  data.

## Migration

None. TriG files from `ConjunctiveGraph` parse into a `Dataset`, but the content changes
anyway under ADR-0001 to ADR-0004.

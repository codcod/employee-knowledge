---
id: EK-012
title: Add an extension point for third-party source adapters
project: employee-knowledge
depends-on: []
spawned-by: []
impact: high
complexity: medium
cost: M
---

# EK-012 — Add an extension point for third-party source adapters

## Outcome

After this ships, a separate package can add a source kind (its adapter and configuration) and ingest through the standard CLI and pipeline without editing `src/ek/`.

## Description

Today the seam exists only at library level: an adapter returns `ReadResult` and `ek.ingest.ingest` does the rest, so a downstream package can call it from its own CLI. Three things are closed:

- `ek/config.py` accepts only the built-in kinds (`_KIND_KEYS`) and parses only Excel options; `SourceConfig` has no place for adapter-specific options.
- `ek/cli.py` hard-wires `ExcelAdapter` in `ingest-excel`; there is no generic `ingest --source-id` that dispatches by kind.
- There is no discovery: downstream adapters cannot register themselves (Python entry points, group such as `employee_knowledge.adapters`, are the obvious standard mechanism).

Also open, and shared with EK-007 to EK-009: `ReadResult` and the SHACL shapes require `ek:fileName` and `ek:sha256`, which only fits file sources. API sources need a source-version reference without fabricating provenance; that needs an ADR. Out of scope: extending the ontology from outside (new attributes still go through the ontology-first rule).

Soft couplings: EK-011 (packaging), EK-007, EK-008, EK-009 (built-in adapters should use the same mechanism), EK-010 (onboarding docs).

Acceptance: a test package registers a synthetic adapter kind; `sources.toml` accepts it; one generic CLI command ingests it with full provenance and validation; unknown kinds are still refused; built-in Excel ingestion is unchanged.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: found while checking adapter wiring for a downstream package

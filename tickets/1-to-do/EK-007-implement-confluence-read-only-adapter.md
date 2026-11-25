---
id: EK-007
title: Implement Confluence read-only adapter
project: employee-knowledge
depends-on: []
spawned-by: []
impact: medium
complexity: medium-high
cost: L
---

# EK-007 — Implement Confluence read-only adapter

## Outcome

After this ships, allow-listed Confluence spaces and pages can be ingested read-only, with page ID and version as provenance.

## Description

Roadmap task: Task-015 in `development/roadmap.md`.

Define allow-listed spaces/pages, page versions and evidence references. Needs the source-onboarding items in `docs/source-onboarding.md` and EK-014's recorded answer to §13 question 9. Shares operational controls with EK-010. Milestone M2.

Since EK-012 (ADR-0011): register the `confluence` kind through the `employee_knowledge.adapters` entry-point group; a plugin for a placeholder kind takes precedence over the placeholder. The plugin contract is file-only today: `ReadResult` needs `file_name` and `sha256`, and the CLI re-hashes the file. This ticket owns the source-version provenance that API sources need, with its ADR and ontology change, and the `ingest` command's shape for a source that has no file. EK-008 and EK-009 then follow it.

Acceptance: connector is read-only, scoped and produces source-version-aware assertions.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-015 when Brine was set up
- 2026-11-19 — description patched (EK-001 review, step 8): the §13 answers are recorded by EK-014, split from EK-001
- 2026-11-25 — impact sweep (EK-012 review): Description patched. Register through the entry-point group; this ticket designs non-file (source-version) provenance and the contract change

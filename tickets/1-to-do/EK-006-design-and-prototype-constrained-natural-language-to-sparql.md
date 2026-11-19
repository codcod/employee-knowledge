---
id: EK-006
title: Design and prototype constrained natural-language-to-SPARQL
project: employee-knowledge
depends-on: []
spawned-by: []
impact: medium
complexity: high
cost: L
---

# EK-006 — Design and prototype constrained natural-language-to-SPARQL

## Outcome

After this ships, there is a design and a prototype that turns a natural-language question into a validated, read-only SPARQL query over approved graphs, and discloses conflicting or untrusted evidence in its answer.

## Description

Roadmap task: Task-014 in `development/roadmap.md`.

Only after the ontology and the query interface (EK-005) stabilise. Use schema grounding, read-only validation, timeouts, result limits and provenance-aware answers (architecture §4.8). Sending any employee data to a model provider needs EK-014's recorded answer to §13 question 6. Milestone M4.

Acceptance: generated queries cannot update data or access unapproved graphs; ambiguous/conflicting answers are disclosed.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-014 when Brine was set up
- 2026-11-19 — description patched (EK-001 review, step 8): the §13 answers are recorded by EK-014, split from EK-001

---
id: EK-011
title: Package the ontology so ek installs as a regular dependency
project: employee-knowledge
depends-on: []
spawned-by: []
impact: high
complexity: low
cost: S
---

# EK-011 — Package the ontology so ek installs as a regular dependency

## Outcome

After this ships, `employee-knowledge` works when installed from a wheel or a git tag, not only as an editable checkout, so another package can depend on it.

## Description

`ek/validation.py` resolves `ontology/` from the source tree (`Path(__file__).parents[2]`, already marked with a `ponytail:` comment). A non-editable install has no `ontology/` there, so validation fails. Ship `employees.ttl` and `shapes.ttl` as package data and load them with `importlib.resources`; keep `ontology/` as the single edited copy (move it into the package or copy it at build time, decided in refinement).

Found while wiring the closed corporate example, which depends on ek as a package and has to use an editable path dependency until this lands. Soft coupling: EK-012 (the same consumers need it).

Acceptance: a test installs the built wheel into a clean environment and runs one ingestion with validation; the editable install keeps working.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: found while checking adapter wiring for a downstream package

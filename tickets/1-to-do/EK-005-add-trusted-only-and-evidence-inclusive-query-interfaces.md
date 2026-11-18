---
id: EK-005
title: Add trusted-only and evidence-inclusive query interfaces
project: employee-knowledge
depends-on: []
spawned-by: []
impact: high
complexity: medium
cost: M
---

# EK-005 — Add trusted-only and evidence-inclusive query interfaces

## Outcome

After this ships, a caller can ask for trusted-only answers or for a diagnostic view that includes untrusted assertions, must choose one explicitly, and gets provenance with every result.

## Description

Roadmap task: Task-013 in `development/roadmap.md`.

Provide safe, read-only query methods for trusted answers and diagnostic views that include untrusted assertions (architecture §4.8). Include provenance in results. The business questions it must answer come from EK-001 (§13 question 10). Milestone M1.

Acceptance: callers must explicitly choose trust scope; tests prove untrusted values do not leak into trusted-only results.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-013 when Brine was set up

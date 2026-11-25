---
id: EK-010
title: Add source onboarding and operational controls
project: employee-knowledge
depends-on: []
spawned-by: []
impact: medium
complexity: medium
cost: M
---

# EK-010 — Add source onboarding and operational controls

## Outcome

After this ships, a new source can be onboarded through documented configuration and review, with credentials, scopes, scheduling, retries, rate limits, retention, offboarding and audit covered.

## Description

Roadmap task: Task-018 in `development/roadmap.md`.

Document connector credentials, scopes, scheduling, retries, rate limits, retention, source offboarding and audit. Retention depends on EK-014 (§13 question 8). Serves EK-007, EK-008 and EK-009. Milestone M2.

Acceptance: a new source can be onboarded through documented configuration and review without code changes where possible.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-018 when Brine was set up
- 2026-11-19 — description patched (EK-001 review, step 8): the §13 answers are recorded by EK-014, split from EK-001
- 2026-11-25 — impact sweep (EK-012 review): `docs/source-onboarding.md` gained "Adding a source kind from another package" (plugin rules, dependency instructions); fold operational controls for plugin kinds in there

---
id: EK-001
title: Confirm architecture decisions and domain vocabulary with the data owner
project: employee-knowledge
depends-on: []
spawned-by: []
impact: high
complexity: medium
cost: M
---

# EK-001 — Confirm architecture decisions and domain vocabulary with the data owner

## Outcome

After this ships, the open architecture questions (architecture §13: attribute scope, reviewer roles, AI-provider limits, production store, retention, connector scope, first business questions, ontology domain) have recorded answers from the data owner, and the ontology terms have definitions they have confirmed.

## Description

Roadmap task: Task-001 in `development/roadmap.md`.

Review the architecture with the employee-data owner. Confirm the employee identifier strategy (HR issues IDs; stability across rehire is still open), the initial employee properties, source naming, timestamp semantics and initial authority assumptions. Record unresolved decisions; do not invent source authority.

The project owner answered §13 questions 1, 3, 4 and 11–16 on 2026-11-18. Questions 2 and 5–10 remain. Question 14 (ontology namespace) is reopened and settled by EK-013.

Acceptance: decisions are recorded, ontology terms have definitions, and open questions are explicit.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-001 when Brine was set up
- 2026-11-18 — EK-013 refinement: Q14 no longer waits on a company domain; namespace moves to w3id.org in EK-013

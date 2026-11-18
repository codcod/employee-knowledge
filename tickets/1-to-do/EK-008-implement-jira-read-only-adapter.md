---
id: EK-008
title: Implement Jira read-only adapter
project: employee-knowledge
depends-on: []
spawned-by: []
impact: medium
complexity: medium-high
cost: L
---

# EK-008 — Implement Jira read-only adapter

## Outcome

After this ships, allow-listed Jira projects and fields can be ingested read-only, with stable user and issue references and update times as provenance.

## Description

Roadmap task: Task-016 in `development/roadmap.md`.

Define allowed projects, object types/fields and stable user/issue references. Jira as a data source is unrelated to this Brine board. Needs EK-001's answer to §13 question 9; shares operational controls with EK-010. Milestone M2.

Acceptance: connector is read-only, scoped and preserves update/version metadata.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-016 when Brine was set up

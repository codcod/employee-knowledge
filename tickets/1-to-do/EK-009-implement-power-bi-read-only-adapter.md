---
id: EK-009
title: Implement Power BI read-only adapter
project: employee-knowledge
depends-on: []
spawned-by: []
impact: medium
complexity: medium-high
cost: L
---

# EK-009 — Implement Power BI read-only adapter

## Outcome

After this ships, approved Power BI workspaces and datasets can be ingested read-only, with refresh metadata and row/field provenance.

## Description

Roadmap task: Task-017 in `development/roadmap.md`.

Define approved workspaces/datasets, refresh metadata and row/field provenance. A Power BI report may be a derived view, not an authority (architecture §6). Needs EK-001's answer to §13 question 9; shares operational controls with EK-010. Milestone M2.

Acceptance: connector is read-only and does not treat a report as authoritative without an explicit policy.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-017 when Brine was set up

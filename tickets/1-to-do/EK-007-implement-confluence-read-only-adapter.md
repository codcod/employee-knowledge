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

Define allow-listed spaces/pages, page versions and evidence references. Needs the source-onboarding items in `docs/source-onboarding.md` and EK-001's answer to §13 question 9. Shares operational controls with EK-010. Milestone M2.

Acceptance: connector is read-only, scoped and produces source-version-aware assertions.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-015 when Brine was set up

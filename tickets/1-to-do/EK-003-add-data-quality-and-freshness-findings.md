---
id: EK-003
title: Add data-quality and freshness findings
project: employee-knowledge
depends-on: []
spawned-by: []
impact: high
complexity: medium-high
cost: M-L
---

# EK-003 — Add data-quality and freshness findings

## Outcome

After this ships, the report lists missing required fields, invalid values, unresolved identities, broken manager references and stale data as findings, each with a category, severity or rationale, and an evidence reference.

## Description

Roadmap task: Task-010 in `development/roadmap.md`.

Add missing-required-field, invalid-value, unresolved-identity, broken-manager-reference and stale-data findings. Keep quality dimensions separate from trust status (architecture §3.4). Per ADR-0004, `ek:managerEmployeeId` stays a string; this ticket resolves it to an employee of the same issuer and reports references that do not resolve. Which attributes are required and the freshness windows depend on EK-001 (§13 questions 2 and 5).

Acceptance: each finding has a category, severity/rationale and evidence reference.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-010 when Brine was set up

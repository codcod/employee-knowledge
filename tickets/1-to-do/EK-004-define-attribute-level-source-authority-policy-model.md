---
id: EK-004
title: Define attribute-level source-authority policy model
project: employee-knowledge
depends-on: []
spawned-by: []
impact: high
complexity: high
cost: L
---

# EK-004 — Define attribute-level source-authority policy model

## Outcome

After this ships, a versioned policy can name, per property, the authoritative sources, freshness window, reviewer role and conflict rule, and review events record that policy version instead of `none`.

## Description

Roadmap task: Task-012 in `development/roadmap.md`.

Create versioned policy configuration per property, including authoritative sources, freshness, reviewer role and conflict rules (architecture §6). Do not populate unapproved assumptions as facts. The project owner decided on 2026-11-18 that no source is authoritative until this policy exists and is approved. A policy may recommend; it never changes trust state without a review event (ADR-0002). Couples to EK-003 (freshness) and EK-001 (reviewer roles).

Acceptance: policy evaluation is testable and a conflict without a policy remains unresolved/untrusted.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-012 when Brine was set up

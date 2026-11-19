---
id: EK-014
title: Record the data owner's answers to the architecture review
project: employee-knowledge
depends-on: [EK-001]
spawned-by: [EK-001]
impact: high
complexity: medium
cost: M
---

# EK-014 — Record the data owner's answers to the architecture review

## Outcome

After this ships, each question in architecture §13 that was still open has either the data owner's answer or an explicit deferral naming who decides and which ticket needs the answer. The ten business ontology terms carry definitions the data owner has confirmed.

## Description

Spawned from EK-001 when it was refined (2026-11-19). EK-001 prepares `development/data-owner-review.md`; this ticket records what the data owner answers in it. It cannot be refined until the session has happened and the filled-in pack is back. Until then it waits in TO DO, so it does not take the WIP slot.

Scope, to be pinned at refinement:
- **Answers.** Each answer goes inline in architecture §13, in the form used on 2026-11-18. A deferral names who decides and the ticket that needs the answer. An ADR is written only where an answer changes the architecture; reviewer roles (Q5) and AI-provider limits (Q6) are the likely ones.
- **Business terms.** A confirmed or corrected definition updates the `rdfs:comment` in `src/ek/ontology/employees.ttl`.
- **Attribute scope (Q2).** An attribute added or excluded under Q2 follows the ontology-first rule (AGENTS.md §3; architecture §4.4): `employees.ttl`, `shapes.ttl`, tests and docs.
- **Dependent tickets.** Tickets that were waiting on an answer get it in their Description: EK-003 (Q1), EK-004 (Q5), EK-005 (Q10), EK-006 (Q6), EK-007 to EK-009 (Q9), EK-010 (Q8 and Q9).
- **Trimming in definitions** (EK-001 review F3, folded): ADR-0008 trims every value, but only `ek:employeeId` and `ek:workEmail` say so, and `ek:workEmail` says both "as the source records it" and "lowercased" (`ek:rawValue` keeps the source text). Settle the wording with the confirmed definitions.
- **Retire the pack** once everything is recorded. Git history keeps it.

Privacy: the filled-in pack must hold policy answers only, never employee records (architecture §8). Check this before the pack enters an agent session.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-19 — created (TO DO). source: pickle ticket new
- 2026-11-19 — folded EK-001 review F3 (trimming wording in the business-term definitions)

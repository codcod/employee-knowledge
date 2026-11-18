---
id: EK-013
title: Choose a licence and a project-owned ontology namespace
project: employee-knowledge
depends-on: []
spawned-by: []
impact: high
complexity: low
cost: S
---

# EK-013 — Choose a licence and a project-owned ontology namespace

## Outcome

After this ships, the repository has a licence that allows closed internal modification, and the ontology namespace is one the project owns, so IRIs never need to change after publishing.

## Description

Required before the first public push. The licence should be permissive (Apache-2.0 or MIT) so organisations can run modified internal copies. The namespace is `https://example.org/employee-knowledge/ontology#` (`ek/constants.py`, `ontology/*.ttl`). The earlier decision to use a company domain (architecture §13) conflicts with keeping the project generic, so it is reopened: use a domain or persistent ID the project controls, such as a `w3id.org` ID. Changing it later means deleting stores and re-ingesting (ADR-0001).

Soft couplings: EK-001 (domain vocabulary), EK-002 (CI runs after the first push).

Acceptance: a LICENSE file and `license` in `pyproject.toml`; an ADR recording the namespace; the namespace updated in code, ontology, shapes, docs and tests; all checks pass.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: owner plans open-source release with a closed downstream copy

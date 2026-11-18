---
id: EK-002
title: Run tests and lint in GitHub Actions
project: employee-knowledge
depends-on: []
spawned-by: []
impact: medium
complexity: low
cost: S
---

# EK-002 — Run tests and lint in GitHub Actions

## Outcome

After this ships, every push and pull request runs lint, format check and tests on GitHub Actions, and a failing check is visible before merge.

## Description

Roadmap task: Task-002 in `development/roadmap.md`.

The local baseline is done (uv, pytest, Ruff, `.gitignore`, `tests/test_repository.py`). `.github/workflows/ci.yml` exists and its steps pass locally, but the repository has no remote yet. Remaining: push to GitHub, confirm the first run is green, and add branch protection if wanted.

Before the first public push, the owner registers the `employee-knowledge/` redirect on w3id.org (a pull request to perma-id/w3id.org) so the ontology IRIs are reserved before they are published (ADR-0009, Consequences). This is an owner action. The agent does not open that pull request. If the name has been taken in the meantime, stop and reopen the namespace decision before pushing.

Acceptance: clean install, tests and lint run in CI; no sensitive fixtures are tracked.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-002 when Brine was set up
- 2026-11-18 — folded from EK-013: w3id.org registration deferred to before the first public push (owner request)

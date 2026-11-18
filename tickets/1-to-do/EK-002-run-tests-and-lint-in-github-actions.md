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

**w3id.org registration** (ADR-0009, Consequences). Register the ontology namespace through a pull request to perma-id/w3id.org from the owner's GitHub account (`codcod`). This needs the owner's approval of the exact files first. Ordering matters:

1. Before the first push, re-check that `ids/employee-knowledge/` (and its case variants) is still free in perma-id/w3id.org. If it has been taken, stop and reopen the namespace decision before pushing.
2. Push the repository. w3id requires the redirect target to be live over HTTPS before the pull request is opened, and reviewers check this.
3. Open the pull request with this one file. Keep the flat path, not `codcod/` (decided 2026-11-18): w3id's naming practice is one top-level directory per project, and `codcod` is a personal account, which w3id would send to `people/`.

   `ids/employee-knowledge/.htaccess`:
   ```apache
   # # /employee-knowledge/
   #
   # https://w3id.org/employee-knowledge/ontology redirects to the
   # Employee Knowledge ontology (Turtle). Everything else under
   # https://w3id.org/employee-knowledge/ redirects to the project page.
   #
   # ## Contact
   # This space is administered by:
   #
   # Nikos
   # GitHub username: codcod

   RewriteEngine on
   RewriteRule ^ontology$ https://raw.githubusercontent.com/codcod/employee-knowledge/main/src/ek/ontology/employees.ttl [R=302,L]
   RewriteRule ^ https://github.com/codcod/employee-knowledge [R=302,L]
   ```

   Commit (squashed): `employee-knowledge: add redirect for ontology namespace`. Before opening, follow w3id's AGENTS.md checklist:
   - run `node tools/check/bin/w3id-check.js`;
   - confirm the diff touches only `ids/employee-knowledge/`;
   - `curl -sIL` the raw TTL target;
   - resolve the rules against a local Apache via `tools/server/` (or hand-trace them if no container runtime is available).
4. After the merge, `curl -sIL https://w3id.org/employee-knowledge/ontology` must end at the TTL.

Open questions for refinement:
- Contact details beyond the name and GitHub username (full name, email). Do not publish personal details without the owner's say-so.
- Whether the redirect should point at `main` or at a release tag.
- The target path assumes the GitHub repository is `codcod/employee-knowledge` with default branch `main`.

Acceptance: clean install, tests and lint run in CI; no sensitive fixtures are tracked.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-002 when Brine was set up
- 2026-11-18 — folded from EK-013: w3id.org registration deferred to before the first public push (owner request)
- 2026-11-18 — w3id registration: owner chose the flat `employee-knowledge/` path (not `codcod/`). The PR to perma-id/w3id.org is part of this ticket, opened after the repository is live; the draft .htaccess is recorded in the Description

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

After this ships, `codcod/employee-knowledge` is public on GitHub with history authored as `codcod <nikos@linux.com>`. Every push to `main` and every pull request runs lint, the format check and the tests on Python 3.11, and a failing check is visible on the pull request before merge. `main` cannot be force-pushed or deleted. A pull request to perma-id/w3id.org asks for `https://w3id.org/employee-knowledge/ontology` to redirect to the ontology.

## Description

Roadmap task: Task-002 in `development/roadmap.md`.

The local baseline is done (uv, pytest, Ruff, `.gitignore`, `tests/test_repository.py`). `.github/workflows/ci.yml` exists and its steps pass locally. The GitHub repository `codcod/employee-knowledge` exists (public, default branch `main`, empty), and the local remote `origin` points at it. Nothing has been pushed.

Checked at refinement (2026-11-18):
- No secret matches (the `tests/test_repository.py` patterns) and no forbidden paths anywhere in the history. The only binaries are the two synthetic example workbooks. The only real email address is the commit author's.
- All commits (24 at refinement, 25 at pickup) are authored and committed as `Nikos <nikos@linux.com>`. The owner's other public repository (`~/Projects/codcod/pickle`) uses `codcod <nikos@linux.com>`, and this one must match. Nothing is pushed yet, so this is the cheap moment to rewrite.
- `ci.yml` pins `actions/checkout@v4` and `astral-sh/setup-uv@v6`. The latest releases are v7.0.1 and v10.3.3. Since v8, setup-uv publishes only immutable full tags: `@v10` and `@v10.3` do not resolve, only `@v10.3.3` does (checked 2026-11-19).
- Local development runs Python 3.14, and nothing tests the declared floor (`requires-python = ">=3.11"`).
- `on: push` plus `pull_request` runs CI twice for a pull-request branch in the same repository.
- Commits are unsigned. `feat/EK-011-package-ontology` is already merged into `main`.

**w3id.org registration** (ADR-0009, Consequences). Register the namespace through a pull request to perma-id/w3id.org from the owner's account (`codcod`), with the flat path `ids/employee-knowledge/` (decided 2026-11-18). w3id's practice is one top-level directory per project, and `codcod` is a personal account, which w3id would send to `people/`. w3id requires the redirect target to be live over HTTPS before the pull request is opened. The file, as approved in content at refinement:

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

Acceptance: clean install, tests and lint run in CI; no sensitive fixtures are tracked.

## Implementation Plan

### 0. Feature branch (mandatory)

Task 1 rewrites history on `main` and must come first. Cut the branch only after it:

```
cd /Users/nka/Projects/codcod/employee-knowledge
git checkout main
git checkout -b feat/EK-002-ci
```

Commit locally on the branch. Publishing (Task 4) happens only at the review's approval step, and each outward step needs the owner's explicit approval. Before the first push there is no `origin/main`, so the in-tree base check has nothing to compare; from the second push on, `git fetch origin main && git diff --name-only origin/main...HEAD | grep '^tickets/'` must print nothing. Merging the EK pull request is the human's.

### Prerequisite gate (hard)

- Clean working tree on `main`. `git ls-remote origin` prints nothing: the remote is still empty, so the rewrite is safe. If anything has been pushed, stop and ask, because the rewrite would then need a force-push.
- `gh auth status` is logged in as `codcod`.
- No dependencies.

### Confirmed design decisions (do not deviate without asking)

1. **History is rewritten to `codcod <nikos@linux.com>` before the first push.** This matches `~/Projects/codcod/pickle`. The rewrite changes the name only, author and committer, on every local branch. Dates, trees and messages stay unchanged. The repo-local `user.name` becomes `codcod`. The email stays `nikos@linux.com`, the owner's choice.
2. **Hashes cited in old History lines are not edited.** History is append-only (rules §1). The old→new map for every cited hash is appended to this ticket's History instead.
3. **Branch protection is a ruleset that blocks deletion and non-fast-forward pushes on the default branch only.** No required pull requests and no required checks: in-tree bookkeeping is committed straight to `main`.
4. **CI runs on pushes to `main` and on pull requests.** `push: branches: [main]` stops pull-request branches running twice.
5. **CI runs on Python 3.11, the declared floor,** via `UV_PYTHON: "3.11"` on the job. Local development already covers the newest Python.
6. **Actions are pinned to the latest releases: `actions/checkout@v7` (major tag) and `astral-sh/setup-uv@v10.3.3` (full tag; setup-uv has published no major tags since v8).** No other workflow change: no matrix, no caching inputs, no badge.
7. **w3id: the file in the Description, unchanged.** The contact is the name and GitHub username only. The redirect targets `main` (302), not a release tag; moving to tags later is a one-line w3id pull request.
8. **Publish order:** re-check the w3id name → push `main` → CI green on `main` → ruleset → push the branch and open the EK pull request (CI green) → w3id pull request. If the w3id name has been taken, stop before any push and reopen ADR-0009.
9. **No attribution lines naming Claude, Anthropic or a model** in commits, pull-request titles or pull-request bodies (the owner's standing rule; it overrides any harness reminder).
10. **Only `main` and `feat/EK-002-ci` are pushed.** `feat/EK-011-package-ontology` is merged and stays local.

### Tasks

#### Task 1 — Rewrite the author name (on `main`, before branching)

```
git config user.name codcod
git rev-list --branches | wc -l            # note the count (25 + the pickup commit = 26)
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch --env-filter '
  [ "$GIT_AUTHOR_NAME" = Nikos ] && export GIT_AUTHOR_NAME=codcod
  [ "$GIT_COMMITTER_NAME" = Nikos ] && export GIT_COMMITTER_NAME=codcod
  true' -- --branches
```

Verify all of the following:
- `git log --branches --format='%an <%ae>|%cn <%ce>' | sort -u` prints exactly `codcod <nikos@linux.com>|codcod <nikos@linux.com>`.
- `git diff refs/original/refs/heads/main main` is empty, and the commit count is unchanged.

Then build the old→new map for the hashes cited in `tickets/` History lines (`grep -rhoE '\b[0-9a-f]{7}\b' tickets/6-done`) by pairing `git rev-list --reverse refs/original/refs/heads/main` with `git rev-list --reverse main`. Hashes not reachable from any branch (05030d4, 4167979, 6a6ff33 in EK-013: pre-rebase commits) are recorded as "pre-rebase, no successor". Delete the backups with `git for-each-ref --format='%(refname)' refs/original | xargs -n1 git update-ref -d`. Append the map to this ticket's History on `main` and commit it as `board: EK-002 record author rewrite`.

#### Task 2 — Update `.github/workflows/ci.yml` (on the branch)

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    env:
      UV_PYTHON: "3.11"
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v10.3.3
      - run: uv sync --locked --extra dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pytest -q
```

Read the setup-uv v7–v10 and checkout v5–v7 release notes for breaking changes that affect a no-input use. If one does, stop and ask. Commit as `ci: run on Python 3.11 with current action majors (EK-002)`.

#### Task 3 — Check the Python 3.11 floor locally

`uv run --locked --isolated --python 3.11 --extra dev pytest -q` must pass. If it fails because 3.12+ code has crept in, fix the code on the branch (a separate `fix:` commit) rather than raising the floor. Raising the floor needs the owner's decision.

#### Task 4 — Publish (at the review's approval step only; each step approved explicitly)

1. Re-check the w3id name: `gh api repos/perma-id/w3id.org/git/trees/master --jq '.tree[]|select((.path|ascii_downcase)=="ids")|.sha'` gives the `ids` sha. Then list `gh api repos/perma-id/w3id.org/git/trees/<sha> --jq '.truncated, ([.tree[].path|ascii_downcase]|index("employee-knowledge")|tostring)'`. Expect `false` and `null`. Do not use the contents API, which truncates at 1,000 entries. If the name is taken, stop.
2. `git push -u origin main`, then `gh run watch "$(gh run list -b main -L1 --json databaseId -q '.[0].databaseId')" --exit-status`.
3. Create the ruleset:
   ```
   gh api -X POST repos/codcod/employee-knowledge/rulesets --input - <<'JSON'
   {"name":"protect main","target":"branch","enforcement":"active",
    "conditions":{"ref_name":{"include":["~DEFAULT_BRANCH"],"exclude":[]}},
    "rules":[{"type":"deletion"},{"type":"non_fast_forward"}]}
   JSON
   ```
4. Run the in-tree base check, then `git push -u origin feat/EK-002-ci` and `gh pr create --base main` with the approved title and body. Wait for its CI run to be green. The owner merges.
5. Prepare the w3id pull request in the scratchpad, not in the project:
   - `gh repo fork perma-id/w3id.org --clone=false`
   - shallow-clone the fork and branch `employee-knowledge`
   - add the Description's file and commit `employee-knowledge: add redirect for ontology namespace` as `codcod <nikos@linux.com>`
   - run w3id's AGENTS.md checklist: `node tools/check/bin/w3id-check.js`, confirm the diff touches only `ids/employee-knowledge/`, `curl -sIL` the raw TTL URL (must end `200`), and resolve the rules against a local Apache via `tools/server/` (Docker is installed) or hand-trace them.

   Show the owner the exact diff and pull-request body. Only after approval, push the fork branch and `gh pr create -R perma-id/w3id.org`.
6. Record the results in this ticket's History on `main`: the run URLs, the EK pull request, the ruleset id and the w3id pull request. Add a `tickets/NOTES.md` entry: "after perma-id/w3id.org merges the EK-002 pull request, `curl -sIL https://w3id.org/employee-knowledge/ontology` must end at the TTL with 200."

### Acceptance test

Local, before review (all must pass):

```
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
uv run --locked --isolated --python 3.11 --extra dev pytest -q
git log --branches --format='%an <%ae>|%cn <%ce>' | sort -u   # one line: codcod <nikos@linux.com>|codcod <nikos@linux.com>
grep -cE 'actions/checkout@v7|astral-sh/setup-uv@v10\.3\.3|UV_PYTHON: "3.11"|branches: \[main\]' .github/workflows/ci.yml   # 4
git log --branches -p | uv run python -c "import sys; sys.path.insert(0, 'tests'); from test_repository import SECRETS; h = [l for l in sys.stdin if l.startswith('+') and SECRETS.search(l)]; print(len(h)); sys.exit(bool(h))"   # 0
git log --branches --name-only --format= | sort -u | uv run python -c "import sys; sys.path.insert(0, 'tests'); from test_repository import ALLOWED, FORBIDDEN_PATHS as F; b = [p for p in sys.stdin.read().split() if p not in ALLOWED and any(r.search(p) for r in F)]; print(b); sys.exit(bool(b))"   # []
```

Remote, at publish (recorded in History):
- the `main` CI run and the EK pull-request CI run both conclude `success`;
- `gh api repos/codcod/employee-knowledge/rulesets --jq '.[].name'` lists `protect main`;
- the rules on `main`: `gh api repos/codcod/employee-knowledge/rules/branches/main --jq '.[].type'`, which lists `deletion` and `non_fast_forward`;
- the w3id pull request is open, and its diff touches only `ids/employee-knowledge/.htaccess`.

### Docs update (mandatory when user-facing)

- `development/roadmap.md`: in the M0 row, change "Task-001 (EK-001) and Task-002 (EK-002) carry on after M0" to "Task-001 (EK-001) carries on after M0". Replace Task-002's Progress with "Done: CI runs on GitHub Actions on Python 3.11 (EK-002)."
- `development/architecture.md` §10: the `ci.yml` comment becomes `# lint and tests on Python 3.11 (GitHub Actions)`.
- `tickets/NOTES.md`: the w3id post-merge check (Task 4.6, on `main`).
- No `docs/` change: CI is not part of the product.

### Finish (mandatory)

1. Local acceptance green; `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` clean.
2. Docs updated as above.
3. Summary: files touched, the rewrite map, anything deferred (the w3id merge and its curl check sit with w3id's maintainers).
4. Suggested commits (root-path child, keep tidied history):
   ```
   ci: run on Python 3.11 with current action majors (EK-002)
   docs: mark Task-002 done (EK-002)
   ```
5. Tidy the branch into these atomic commits.
6. Commit locally; do not push. `pickle ticket move EK-002 in-review --reason "acceptance green"`. Publishing is Task 4, at the review's approval step.

## Review

Review 2026-11-19, branch `feat/EK-002-ci` (33c9824, bd445e4).

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F1 | non-blocking | design | noted | `ci.yml` has no `permissions:` block, so the GITHUB_TOKEN scope follows the repository default and checkout persists it while `uv sync`/`pytest` run | `.github/workflows/ci.yml` has no `permissions` key; decision 6 forbids other workflow changes | raised with the owner at the approval step: add `permissions: { contents: read }`, or confirm the repository default is read-only at publish |
| F2 | non-blocking | stale-xref | noted | plan prose (Task 2, Finish 4) says "current action majors"; the commit says "current action releases", which is accurate after decision 6 was amended to the full `v10.3.3` tag | `git log -2 feat/EK-002-ci` vs this ticket's Task 2 | keep the branch wording |
| F3 | non-blocking | design | noted | roadmap Task-002 line reads "Progress: Done: …", a doubled label; Task-003 onward use "Status: done in M0." | `development/roadmap.md:44` vs `:47` | matches the plan's mandated wording; leave |

Disposition summary: 3 noted (F1, F2, F3); 0 fixed inline, 0 folded, 0 new tickets.
cost: estimated S, actual S

- [x] Reviewer independence settled (step 0): delegated. A fresh sub-agent with no hand in the branch ran steps 1–4a. All 3 of its findings were re-verified by hand, and none was discarded.
- [x] In-tree stale-branch check (step 0a): `pickle doctor` flagged the branch's copy of the ticket as stale. I rebased onto `main` and the re-run was clean.
- [x] Implementation audit (steps 1, 2): the local acceptance test was re-run verbatim and is green (125 passed on 3.14 and on 3.11.18, one identity, grep 4, secrets 0, forbidden paths []). Tasks 1–3 and the docs step were met. Task 4 and the remote acceptance wait for publish.
- [x] Correctness hunt (step 3): an angle hunt, one pass over all 8 angles (low complexity), run by the delegated reviewer. No host tool or sub-agents were used, and angle 7 was part of the pass. There are no correctness rows.
- [x] Consistency audit (step 4): no stale `checkout@v4`/`setup-uv@v6` or CI references remain. The only drift is F2 and F3.
- [x] Documentation audit (step 4a): nothing user-facing, so no `docs/` change. No docs build is configured.
- [x] Docs-readability pass (step 4b): consciously skipped. The `.md` changes are two one-line edits, both copied verbatim from the plan.
- [x] Findings recorded (step 5)
- [x] Ticket moved to `6-done/` (step 6)
- [x] Governing documents reconciled (step 7): the branch updates roadmap and architecture §10. No other document cites EK-002's workflow.
- [x] Impact sweep (step 8): no ticket depends on EK-002 or cites its CI assumptions.
- [ ] Approval and publish (step 9, Task 4): pending the owner.

Note: Task 4.2 pushes `main` before the pull request merges, so the first green run on `main` exercises the old workflow (`checkout@v4`, `setup-uv@v6`, unpinned Python). The new workflow is first proven on the pull-request run.

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-002 when Brine was set up
- 2026-11-18 — folded from EK-013: w3id.org registration deferred to before the first public push (owner request)
- 2026-11-18 — w3id registration: owner chose the flat `employee-knowledge/` path (not `codcod/`). The PR to perma-id/w3id.org is part of this ticket, opened after the repository is live; the draft .htaccess is recorded in the Description
- 2026-11-18 — refined: owner decisions — rewrite history to `codcod <nikos@linux.com>` to match the pickle repo; ruleset blocks force-push/delete only; w3id contact name + GitHub username; redirect to `main`. Plan written
- 2026-11-18 — TO DO → READY: plan complete
- 2026-11-19 — plan amended inline (applicability gate, owner-approved routing): pin `astral-sh/setup-uv@v10.3.3` (no `@v10` major tag exists since v8; blocking as written) in decision 6, Task 2 and the acceptance grep; record the 3 unreachable EK-013 hashes as pre-rebase; commit count 25+1; Task 4.1 jq prints the `ids` sha and `null` via `tostring`; roadmap edit grammar ("carries on")
- 2026-11-19 — READY → IN DEVELOPMENT: picked up
- 2026-11-19 — author rewrite done (Task 1): 27 commits on `main` and `feat/EK-011-package-ontology`, author and committer `Nikos` → `codcod`, email unchanged, trees identical. Map of hashes cited in History: 6f307c1 → 6a7c242, 4f023ea → 764e0d9 (EK-011); 753a9ca → cc26497, 7de854c → 6836985 (EK-013); 05030d4, 4167979, 6a6ff33 (EK-013) pre-rebase, no successor
- 2026-11-19 — IN DEVELOPMENT → IN REVIEW: acceptance green
- 2026-11-19 — IN REVIEW → DONE: review: no blocking findings; 3 noted (F1, F2, F3); publish (Task 4) pending owner approval

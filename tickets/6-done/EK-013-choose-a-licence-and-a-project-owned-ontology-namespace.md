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

After this ships, the repository is MIT-licensed, which allows closed, modified internal copies. The ontology namespace is `https://w3id.org/employee-knowledge/ontology#`, a persistent ID the project can register and keep, so ontology IRIs never need to change after the first publication. ADR-0009 records the choice and why the internal `urn:employee-knowledge:*` instance IRIs stay as they are.

## Description

Required before the first public push.

- **Licence.** There is no LICENSE file and no `license` in `pyproject.toml`. Use MIT, a permissive licence, so organisations can run modified internal copies. The copyright holder is "The Employee Knowledge contributors" (decided 2026-11-18).
- **Ontology namespace.** It is currently `https://example.org/employee-knowledge/ontology#`, used in `src/ek/constants.py:3`, `src/ek/ontology/employees.ttl` (prefix, ontology IRI, and the "provisional" comment on line 8), `src/ek/ontology/shapes.ttl` (prefix and two full IRIs in the SPARQL constraint, lines 122–123), `tests/test_validation.py:11` and `development/architecture.md` §13 question 14. The 2026-11-18 decision for Q14 (a company-owned domain) conflicts with keeping the project generic, so it is reopened. The new namespace is `https://w3id.org/employee-knowledge/ontology#` (decided 2026-11-18). Changing it later would mean deleting stores and re-ingesting (ADR-0001), which is why it is fixed now.
- **Instance IRIs stay out of scope.** `urn:employee-knowledge:{assertion,employee,file,graph,observation,quarantine,review,run,source}:…` (about 65 uses) use an unregistered URN namespace. They are internal identifiers that are never published for dereferencing. They are kept, and ADR-0009 records why (decided 2026-11-18).
- `docs/` does not mention the namespace or a licence.

Soft couplings: EK-001 (domain vocabulary; its Q14 mention is updated by this refinement), EK-002 (CI runs after the first push).

Acceptance: an MIT LICENSE file, plus `license`/`license-files` in `pyproject.toml` and the licence in the built wheel; ADR-0009 records the namespace; no `example.org` IRI is left in code, ontology, shapes, tests or docs; all checks pass.

## Implementation Plan

### 0. Feature branch (mandatory)

```
cd /Users/nka/Projects/codcod/employee-knowledge   # child employee-knowledge, path "."
git checkout main
git checkout -b feat/EK-013-licence-and-namespace
```

Work and commit locally on this branch. In-tree layout: ticket and board bookkeeping is committed on `main`, never on this branch. No push and no merge request without explicit user approval; merging is the human's. Before pushing (after approval), `git fetch origin main && git diff --name-only origin/main...HEAD | grep '^tickets/'` must print nothing (skip if there is still no remote).

### Prerequisite gate (hard)

- Clean tree on `main`; `depends-on: []`.
- The owner has confirmed that `employee-knowledge` is not already taken on w3id.org (there is no `employee-knowledge/` directory in the perma-id/w3id.org repository). If the name is taken, stop and ask for another path. Registering the redirect is the owner's external step and is not part of this ticket (decision 5).

### Confirmed design decisions (do not deviate without asking)

1. **The licence is MIT, with copyright holder "The Employee Knowledge contributors".** The standard SPDX MIT text goes in `LICENSE`, with the line `Copyright (c) 2026 The Employee Knowledge contributors`. (Chosen 2026-11-18 over Apache-2.0.)
2. **PEP 639 licence metadata.** In `pyproject.toml`, set `license = "MIT"` and `license-files = ["LICENSE"]`, and raise the build requirement to `setuptools>=77`, the first version that accepts an SPDX string. Do not use the legacy `{text = ...}` / `{file = ...}` table, and do not add a licence classifier (PEP 639 deprecates it).
3. **The namespace is `https://w3id.org/employee-knowledge/ontology#`, in hash style.** The ontology IRI is `https://w3id.org/employee-knowledge/ontology` (no `#`). Only the base changes; local names stay the same. (Chosen 2026-11-18.)
4. **`urn:employee-knowledge:*` instance IRIs are unchanged.** ADR-0009 records the reason: they are internal identifiers, never published for dereferencing, and moving them is a separate delete-and-re-ingest if it is ever needed. (Chosen 2026-11-18.)
5. **w3id registration is a recorded follow-up, not a task.** ADR-0009 names it as an owner action under Consequences. The agent does not open the w3id pull request.
6. **The ontology version goes from `0.2.0` to `0.3.0`.** Every term IRI changes, which is a breaking change for any consumer.
7. **No migration code.** Existing stores (synthetic only) are deleted and re-ingested, per ADR-0001. ADR-0009 says so under migration implications.
8. **The architecture keeps a single namespace source.** In architecture §13 Q14, the "Decided" text is replaced with the new decision and points to ADR-0009. The old company-domain answer is mentioned as superseded in one clause; it is not kept as a second answer.

### Tasks

#### Task 1 — Licence
- New `LICENSE`: the standard MIT text with the copyright line from decision 1.
- `pyproject.toml`: `requires = ["setuptools>=77", "wheel"]`; under `[project]`, add `license = "MIT"` and `license-files = ["LICENSE"]`.
- `tests/test_packaging.py`: the `wheel` fixture copies `("pyproject.toml", "README.md", "LICENSE")` (EK-011 F3). Without `LICENSE`, the clean-copy build fails. Add `test_wheel_carries_licence`, which asserts that one wheel member ends with `.dist-info/licenses/LICENSE` and that the wheel's `METADATA` contains `License-Expression: MIT`.

#### Task 2 — Namespace
Replace `https://example.org/employee-knowledge/ontology` with `https://w3id.org/employee-knowledge/ontology` in:
- `src/ek/constants.py:3`
- `src/ek/ontology/employees.ttl`: the prefix, the `owl:Ontology` IRI, and `owl:versionInfo "0.3.0"`. In the comment on line 8, replace "The namespace is provisional (architecture §13, question 14)." with "Namespace: ADR-0009."
- `src/ek/ontology/shapes.ttl`: the prefix and the full IRIs on lines 122–123.
- `tests/test_validation.py:11`

Then `git grep -n "example.org/employee-knowledge"` must print nothing outside `tickets/`.

#### Task 3 — Namespace regression test
In `tests/test_validation.py` (or the nearest existing ontology test), add one test. It parses `importlib.resources.files("ek") / "ontology" / "employees.ttl"` directly, not through the private `ek.validation._load`, and asserts two things: the single `owl:Ontology` subject equals `str(EK).rstrip("#")`, and `str(EK)` starts with `https://w3id.org/employee-knowledge/`. The test catches the code constant and the TTL drifting apart.

#### Task 4 — ADR-0009 and architecture
- New `development/decisions/0009-ontology-namespace.md`, Status Accepted (2026-11-18), Related ADR-0001. It has the sections Context, Decision, Alternatives considered, Consequences and Migration implications. Context: the example.org placeholder, and why the company-domain answer conflicts with keeping the project generic. Decision: decisions 3, 4 and 6. Alternatives: company domain (ties the generic project to one organisation), own domain (renewal risk), slash IRIs (a needless change of style), moving the URNs too (cost, and no external consumer). Consequences: the owner registers the w3id redirect before IRIs are published. Migration: delete stores and re-ingest, as decision 7 says.
- `development/decisions/README.md`: add an index row for 0009.
- `development/architecture.md` §10: add `├── LICENSE` to the repository tree, next to `README.md`.
- `development/architecture.md` §13 Q14: rewrite it per decision 8, for example: "*Decided (2026-11-18):* `https://w3id.org/employee-knowledge/ontology#` (ADR-0009), replacing the earlier company-domain answer, which would tie the generic project to one organisation."

### Acceptance test

```
uv run pytest tests/test_packaging.py tests/test_validation.py -v   # new tests pass
uv run pytest                                                        # whole suite green
uv run ruff check . && uv run ruff format --check .
test -z "$(git grep -n 'example.org/employee-knowledge' -- . ':!tickets')"
head -1 LICENSE | grep -q 'MIT License'
grep -q 'license = "MIT"' pyproject.toml
ls development/decisions/0009-ontology-namespace.md
```

### Docs update (mandatory when user-facing)

- `README.md`: add a short `## Licence` section ("MIT, see [LICENSE](LICENSE).") before `## Documentation`.
- Development docs: ADR-0009, the ADR index and architecture §13 Q14 (Task 4).
- `docs/` stays as it is. It mentions neither the namespace nor a licence, and it must not link to `development/`.

### Finish (mandatory)

1. Acceptance test green; `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` clean.
2. Docs updated (README Licence section, ADR-0009 and its index row, architecture Q14).
3. Write a summary: files touched, the decisions above, and what is deferred (w3id registration by the owner; the URN instance IRIs are kept).
4. Suggested commit messages (root-path child, atomic history):

   ```
   chore: license under MIT (EK-013)

   Add LICENSE and PEP 639 metadata; ship the licence in the wheel.
   ```

   ```
   feat(ontology)!: move the namespace to w3id.org (EK-013)

   Replace the example.org placeholder with
   https://w3id.org/employee-knowledge/ontology# (ADR-0009). Ontology 0.3.0.
   Existing stores must be deleted and re-ingested.
   ```

5. Root-path child: tidy WIP commits into the two atomic commits above (plus a `docs:` commit if that reads better) before presenting them.
6. Commit locally on `feat/EK-013-licence-and-namespace`; do not push. `pickle ticket move EK-013 in-review --reason "acceptance green"`.

## Review

Reviewed 2026-11-18 on `feat/EK-013-licence-and-namespace` (tip 6a6ff33 after the inline fix).

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F1 | non-blocking | spec-unclear | fixed inline | ADR-0009's Context quoted the full placeholder IRI, so acceptance line 4 (`git grep 'example.org/employee-knowledge' -- . ':!tickets'`) failed as written at the tip. It had passed during implementation only because the ADR was still untracked, and `git grep` skips untracked files. Task 4 asked the ADR to describe the placeholder, while the grep only excludes `tickets/`, so the plan contradicted itself. Intent held: no code, ontology, shapes, tests or `docs/` file kept the IRI. | Reproduced: the grep printed `development/decisions/0009-ontology-namespace.md:9:` followed by the old IRI. | Reworded the Context to "used an `example.org` placeholder namespace" and amended the docs commit. The grep now prints nothing, and the whole acceptance block passes on a clean tree. |

Dispositions: 1 fixed inline (F1); 0 blocking, 0 folded, 0 new tickets, 0 noted.
cost: estimated S, actual S

- [x] Reviewer independence settled (step 0): delegated. The orchestrator authored the branch in this session, so a fresh general-purpose sub-agent ran steps 1–4a with the verbatim spawn prompt (`hunt: angle 7 only`). The orchestrator re-verified F1 by hand. No delegated findings were discarded.
- [x] In-tree stale-branch check (step 0a): `pickle doctor` warned that the branch still had EK-013 in 3-in-development. I rebased the branch onto main, and the re-run gave 0 errors and 0 warnings.
- [x] Implementation audit (steps 1 and 2): acceptance test re-run verbatim. Tasks 1–4 and the docs step are met, and decisions 1–8 are honoured. Line 4 failed at first (F1), and after the fix all lines pass. `uv run pytest` gives 125 passed. Ruff check and format are clean.
- [x] Correctness hunt (step 3): host tool path, `/code-review low` on `main...feat/EK-013-licence-and-namespace`, run by the orchestrator. It found nothing, so nothing was discarded. Angle 7 ran separately in the delegated reviewer and found nothing: no input handling, the SPARQL is static, there are no secrets, and nothing dereferences the namespace. No correctness rows. The rest of the quality audit ran in full, including mutation runs: drifting `shapes.ttl` fails 5 or 22 tests, and drifting the `EK` constant fails the new test.
- [x] Consistency audit (step 4): repository-wide search for `example.org`, the namespace, `provisional`, Q14, `company-owned`, `licen[cs]e` and the version strings. F1 was the only hit. The leftover `example.com` strings are synthetic emails (gate F3).
- [x] Documentation audit (step 4a): the README Licence section covers the user-facing change. `docs/` is untouched and has no links to development/. No docs build is configured.
- [x] Docs-readability pass (step 4b): conscious skip. The prose change is small (one ADR, one README section, one architecture answer) and was already read in full by the delegated reviewer.
- [x] Findings recorded with severity, class and disposition; disposition summary and cost line present (step 5).
- [x] Ticket moved to 6-done; History appended (step 6).
- [x] Governing documents reconciled (step 7): the branch updates architecture §10 and §13 Q14 and the ADR index. The ticket references in EK-001 were updated during refinement. The board is regenerated by the move.
- [x] Impact sweep (step 8): EK-001 already points Q14 to EK-013. EK-011 is done. EK-002 (CI) is unaffected, because uv fetches setuptools>=77 at build time. No open ticket mentions the namespace or the licence.
- [x] Summary, commit messages and MR attributes presented for approval (step 9): approved 2026-11-18; history kept; no MR because there is no remote; merged locally at the owner's request; bookkeeping committed; next-ticket suggestion given.

## History

- 2026-11-18 — created (TO DO). source: chat: owner plans open-source release with a closed downstream copy
- 2026-11-18 — EK-011 review: path corrected to src/ek/ontology/ (EK-011 F2); when adding the licence, extend the file list copied by the `wheel` fixture in tests/test_packaging.py, or the wheel build breaks if pyproject names a licence file (EK-011 F3)
- 2026-11-18 — refined: owner chose MIT (holder "The Employee Knowledge contributors"), namespace https://w3id.org/employee-knowledge/ontology#, URN instance IRIs kept; plan written
- 2026-11-18 — TO DO → READY: plan complete
- 2026-11-18 — applicability gate (fresh sub-agent): no blocking findings. F1 (Task 3 would use a private loader) → inline; F2 (§10 tree lacks LICENSE) → inline; F3 (acceptance grep narrower than its wording; the leftover example.com strings are synthetic emails) → note-and-close. Routing approved by the owner
- 2026-11-18 — plan amended inline: Task 3 reads employees.ttl via importlib.resources rather than the private _load (gate F1); Task 4 adds LICENSE to the architecture §10 tree (gate F2)
- 2026-11-18 — READY → IN DEVELOPMENT: picked up
- 2026-11-18 — IN DEVELOPMENT → IN REVIEW: acceptance green
- 2026-11-18 — IN REVIEW → DONE: review clean; 1 non-blocking (fixed inline: F1)
- 2026-11-18 — publish approved by the owner (commits 05030d4, 4167979, 6a6ff33 and MR attributes as presented; keep history). Not pushed: the repository has no git remote yet. Push and open the MR once one is added
- 2026-11-18 — merged to main (local fast-forward, no MR, no remote; 753a9ca..7de854c)

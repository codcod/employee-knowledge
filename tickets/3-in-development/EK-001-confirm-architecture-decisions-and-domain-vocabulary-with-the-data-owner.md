---
id: EK-001
title: Confirm architecture decisions and domain vocabulary with the data owner
project: employee-knowledge
depends-on: []
spawned-by: []
impact: high
complexity: low
cost: S
---

# EK-001 — Confirm architecture decisions and domain vocabulary with the data owner

## Outcome

After this ships, the project owner has a review pack to take to the employee-data owner. It lists the open architecture questions with today's provisional defaults, the decisions already made that need the data owner's confirmation, and the ten business ontology terms with the definitions to confirm. Every ontology term now has a definition, and a test keeps it that way. EK-014 records what the data owner answers.

## Description

Roadmap task: Task-001 in `development/roadmap.md`.

Split at refinement (2026-11-19, owner decision). The employee-data owner is someone other than the project owner, so the confirmation session happens outside this repository and outside agent sessions. This ticket prepares for that session. EK-014 (`depends-on: [EK-001]`) records the answers afterwards. It stays in TO DO until the filled-in pack is back, so it does not take the WIP slot.

Re-verified on 2026-11-19:
- Architecture §13 records answers to Q3, Q4 and Q11 to Q16, and Q1 in part (the HR system issues the ID; stability across rehire is still open). Q2 and Q5 to Q10 are open. Q14 (namespace) and Q16 (CI) are not data-owner matters.
- `src/ek/ontology/employees.ttl` (version `0.3.0`) defines 59 terms, and 30 of them have no `rdfs:comment`. Two comments are stale since Q11 and Q15 were decided. `ek:workEmail` says "Format rules are not yet defined (question 11)", but ADR-0008 trims the address and lowercases it. `ek:managerEmployeeId` says "Provisional: may become a relationship (question 15)", but Q15 decided on a manager-ID string as the source states it, which EK-003 resolves.
- No test checks that terms are defined.

Acceptance (roadmap): decisions are recorded, ontology terms have definitions, and open questions are explicit. This ticket covers the definitions and makes the open questions explicit in the pack. EK-014 records the decisions.

## Implementation Plan

### 0. Feature branch (mandatory)

```
cd /Users/nka/Projects/codcod/employee-knowledge
git checkout main && git pull --ff-only
git checkout -b feat/EK-001-review-pack
```

Commit locally on the branch. Bookkeeping (ticket moves) goes on `main`, never on the branch. Do not push or open a pull request without the owner's approval. Before pushing, `git fetch origin main && git diff --name-only origin/main...HEAD | grep '^tickets/'` must print nothing. Merging is the owner's.

### Prerequisite gate (hard)

- No dependencies. WIP for `employee-knowledge` is 0/1 in development.
- Clean tree on `main`, up to date with `origin/main`.

### Confirmed design decisions (do not deviate without asking)

1. **Split (owner, 2026-11-19).** This ticket prepares the pack and the definitions. EK-014 records the data owner's answers. No §13 question is answered here, and no business rule is invented.
2. **Done bar (owner).** A question is closed when it is answered, or when it is explicitly deferred with who decides and which ticket needs the answer. The pack offers both options for every question.
3. **Definitions (owner).** Every ek: term gets an `rdfs:comment`, following the existing convention; no `skos:definition`. Only the ten business terms go to the data owner for confirmation: `ek:Employee`, `ek:employeeId`, `ek:issuer`, and the seven assertable properties.
4. **Where definitions come from.** Write each definition from ADR-0001 to ADR-0004, ADR-0006 to ADR-0008, architecture §4.7 and §5, or what `src/ek/` does. Never add meaning that none of these states. The review states and actions follow ADR-0002's transition table.
5. **Where answers go (owner, used by EK-014).** Answers go inline in §13. An ADR is written only where an answer changes the architecture.
6. **The pack is Markdown in `development/` (owner).** The file is `development/data-owner-review.md`, version-controlled. The owner exports or prints it for the session, and EK-014 retires it.
7. **Ontology version `0.3.0` → `0.3.1`.** Comments change and no IRI does, so this is a patch bump.
8. **The pack holds no employee data.** Examples are synthetic. The pack tells the data owner to answer with policy only, never real records, because the filled-in pack will be read in an agent session (AGENTS.md §3, the "No employee data in agent sessions" item).

### Tasks

#### Task 1 — Define every ontology term (`src/ek/ontology/employees.ttl`)

- Add an `rdfs:comment` to the 30 terms that lack one:
  - Classes and properties: `aboutEmployee fromSource forSource mappingVersion ofAssertion validationResult validationMessage quarantineReason reviewAction fromState toState reviewReason supersededBy RunStatus ValidationOutcome ReviewAction ReviewState`.
  - Individuals: `Completed Conforms Violation Accept Reject RequestEvidence Supersede Reopen Candidate Accepted Rejected NeedsEvidence Superseded`.
  - Each review action says what it means and which transitions it performs. Each review state says what it means and which transitions lead to it (ADR-0002 §States and transitions).
  - Keep each comment to one or two sentences, in the style of the file. Individuals may move off their current one-line form.
- Replace the stale comments:
  - `ek:workEmail`: "Work email address as the source records it, trimmed and lowercased before comparison (ADR-0008)."
  - `ek:managerEmployeeId`: "Employee ID of the person's manager as the source states it, from the same issuer as the record. To be resolved to an employee, with broken references reported, by data-quality checks (Task-010; architecture §13, question 15)."
- Set `owl:versionInfo "0.3.1"`.
- Add `tests/test_ontology.py` with one test. It parses `employees.ttl` with rdflib and asserts that every subject IRI in the `ek:` namespace has exactly one `rdfs:label` and at least one non-empty `rdfs:comment`. The assertion message lists the terms that fail. Use `import typing as tp` if typing is needed.
- Commit: `feat(ontology): define every ontology term (EK-001)`.

#### Task 2 — Write the review pack (`development/data-owner-review.md`)

Plain Markdown with no links into `docs/` and no employee data. The sections are fixed in this order:

1. **Purpose and how to answer.** Three to five sentences.
   - Who it is for: the employee-data owner.
   - For each question, answer it, or defer it by naming who decides and by when.
   - Answer with policy only, never real employee records or examples. The filled-in pack is read in an AI-assisted session.
   - Return the filled-in pack to the project owner.
2. **Open questions.** One `### Qn — <short title>` heading for each of Q1, Q2 and Q5 to Q10, in that order. Q1 covers only stability across rehire and legal-entity changes. Under each heading:
   - The question, quoted from §13.
   - **Why it matters**: what it blocks, in one or two sentences.
   - **Today's default**: from §13's closing paragraph and the ADRs. For example, Q5 has a local reviewer label that is not access control (§4.7). Q6 sends nothing to an AI provider. Q7 is ADR-0005's store. Q9 has connector access disabled.
   - **Needed by**: Q1 → ADR-0004 (and EK-003's unresolved-identity findings). Q2 → EK-003 and ontology scope (§4.4). Q5 → EK-004 and EK-003. Q6 → EK-006. Q7 → ADR-0005, no ticket yet. Q8 → EK-010. Q9 → EK-007 to EK-009, and EK-010 for access approval. Q10 → EK-005.
   - The empty fields `Answer:` and `Or defer — who decides, by when:`.
3. **Decisions to confirm.** One row each for Q1 (the HR system issues the ID), Q3, Q4 (including the meaning of `ek:observedAt`: a time supplied by the source, never the ingestion time), Q11, Q12, Q13 and Q15.
   - Table columns: `| question | decided (2026-11-18) | confirm / correct |`.
   - The decided text is quoted from §13, and the last column is empty.
4. **Business terms to confirm.** One row per term.
   - Table columns: `| term | source field | definition | confirm / correct |`.
   - The ten terms of decision 3, each in the form `` `ek:fullName` ``.
   - The source field is the Excel mapping name from `docs/source-onboarding.md` (for example `full_name`), or `—` for `ek:Employee` and `ek:issuer`.
   - The definition is the term's `rdfs:comment` after Task 1.

Then add one sentence at the top of architecture §13, after its intro: "The open questions go to the data owner in `development/data-owner-review.md` (EK-001); EK-014 records the answers here." Commit: `docs: add the data-owner review pack (EK-001)`.

### Acceptance test

```
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
uv run pytest -q tests/test_ontology.py                                    # passes
uv run python -c "from rdflib import Graph, RDFS, URIRef; g = Graph().parse('src/ek/ontology/employees.ttl'); ns = 'https://w3id.org/employee-knowledge/ontology#'; m = sorted(str(s) for s in set(g.subjects()) if isinstance(s, URIRef) and str(s).startswith(ns) and not str(g.value(s, RDFS.comment) or '').strip()); print(m); raise SystemExit(bool(m))"   # []
grep -c 'owl:versionInfo "0.3.1"' src/ek/ontology/employees.ttl            # 1
grep -cE 'may become a relationship|Format rules are not yet defined' src/ek/ontology/employees.ttl   # 0
grep -cE '^### Q(1|2|5|6|7|8|9|10) ' development/data-owner-review.md        # 8
grep -cE '^\| `ek:(Employee|employeeId|issuer|fullName|workEmail|department|jobTitle|managerEmployeeId|location|employmentStatus)`' development/data-owner-review.md   # 10
grep -c 'data-owner-review.md' development/architecture.md                 # 1
grep -rn 'development/' docs/ ; test $? -eq 1                              # no docs → development links
```

Regression check: temporarily delete one `rdfs:comment` and confirm that `tests/test_ontology.py` fails and names the term. Then restore it.

### Docs update (mandatory when user-facing)

- `development/roadmap.md` Task-001:
  - "- Ticket: EK-001." becomes "- Ticket: EK-001 (review pack), EK-014 (record answers)."
  - Add "- Progress: review pack ready (EK-001); answers wait for the data-owner session (EK-014)."
- Architecture §13: the one sentence from Task 2.
- No `docs/` change. Ontology comments and the pack are not operator-facing, and `docs/` must not link to `development/`.

### Finish (mandatory)

1. Acceptance green, and `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` are clean.
2. Check that the pack and the test fixtures hold no real employee data.
3. Summary: the files touched, the 30 definitions added, and the open items handed to EK-014.
4. Commits (root-path child, keep the tidied history):
   ```
   feat(ontology): define every ontology term (EK-001)
   docs: add the data-owner review pack (EK-001)
   ```
5. Commit locally; do not push. On `main`, run `pickle ticket move EK-001 in-review --reason "acceptance green"`, then review. Publishing (push, pull request) happens only at the review's approval step.

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-001 when Brine was set up
- 2026-11-18 — EK-013 refinement: Q14 no longer waits on a company domain; namespace moves to w3id.org in EK-013
- 2026-11-19 — refined. Owner decisions: the data owner is a separate person; split, so EK-014 (new, depends-on EK-001) records the answers; a question is done when it is answered or deferred with who decides; every term gets an rdfs:comment, and the data owner confirms the 10 business terms; answers go inline in §13, with an ADR if material; the pack is Markdown in development/. Re-graded complexity medium → low, cost M → S. Plan written
- 2026-11-19 — TO DO → READY: plan complete
- 2026-11-19 — plan amended inline (applicability gate, owner-approved routing): managerEmployeeId comment in the future tense (nothing resolves it yet; Task-010); ADR-0006/0007 added as definition sources; Needed-by gains Q2 → EK-003 and Q5 → EK-003 (EK-003 cites both); actions say which transitions they perform, states which lead to them. Noted: Q7 and Q10 are arguably project-owner questions; they stay in the pack as scoped
- 2026-11-19 — READY → IN DEVELOPMENT: picked up

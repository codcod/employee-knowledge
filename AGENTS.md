# AGENTS.md: instructions for coding agents

## 1. Project overview

Employee Knowledge is a provenance-first employee knowledge platform. It ingests
employee-related information from multiple sources (Excel first; Confluence, Jira, Power
BI and others later through source adapters), maps it to a manually maintained ontology,
preserves its provenance, surfaces discrepancies and provides a trusted, queryable view.
It uses RDF and named graphs to keep facts, provenance and trust status.

**Before doing any work, read `development/architecture.md` in full.** It is the
normative source for the architecture, data model, ontology, provenance, trust and
review, ingestion lifecycle, security and privacy, and technology choices. Milestones
and the task backlog are in `development/roadmap.md`; decisions are in
`development/decisions/`.

If a requirement seems to conflict with the architecture, do not pick an interpretation
silently. Name the conflict and propose an architecture decision.

## 2. Development workflow: Pickle/Brine

This repository uses Pickle/Brine to organise and govern development work: the board is
`tickets/BOARD.md` and the rules are in the "Brine (start here)" section at the end of
this file. Ticket IDs are `EK-NNN`. The roadmap's `Task-NNN` items are planning
descriptions, not tickets; each open task has one EK ticket that names it. Do not copy
generated board or ticket files from another repository.

## 3. Invariants checklist

These rules are mandatory unless changed through an approved architecture decision. The
linked sections of `development/architecture.md` define them; this list is a reminder,
not a replacement.

- [ ] **Assertions, not overwrites.** Each observed value is an independent assertion.
  Never overwrite one source's value with another's. (§3.1, §5.2)
- [ ] **Provenance is mandatory.** Every assertion carries the fields listed in §5.2,
  plus the source reference from the §4.1 table (for Excel: workbook, sheet, row). Never
  fabricate provenance, including timestamps the source did not supply. (§3.2, §5.2)
- [ ] **Trust is per assertion.** New facts enter
  `urn:employee-knowledge:graph:untrusted`. The trusted and audit graphs are
  `…:graph:trusted` and `…:graph:audit`; each ingestion run has its own
  `…:graph:run:{uuid}`. Trust state comes only from audit events; graph membership is a
  projection of them (ADR-0002). Never trust a whole source, workbook or connector.
  (§3.3, §4.5)
- [ ] **No autonomous promotion.** AI and automation may suggest, extract, compare and
  explain. Only an explicit, authorised review action with a recorded reason changes
  trust. (§3.3, §3.5, §4.7)
- [ ] **Keep conflicts visible.** Never pick the newest value, prefer a source without an
  approved policy, delete a conflicting assertion or replace source values with AI
  interpretations. (§3.5, §4.6, §6)
- [ ] **Conservative identity.** Use the organisation-issued employee ID as the key
  (ADR-0004). Never use a name as an identifier or merge on name, department
  or title similarity. Leave ambiguous matches unresolved. (§4.3)
- [ ] **Ontology first.** Before adding an employee attribute: check for an equivalent
  property, review its meaning and datatype, decide whether it belongs in the ontology,
  update `ontology/employees.ttl` and `ontology/shapes.ttl`, add tests and docs. Map
  source-specific field names onto the common ontology; never add a property for one
  source's naming. Structural validity is not correctness. (§4.4)
- [ ] **Read-only adapters.** Adapters retrieve, keep source identifiers and versions,
  normalise and give provenance. They never modify sources, decide trust, pick between
  conflicting values, discard source information or embed credentials. Keep
  source-specific logic out of the graph, ontology and reconciliation layers. Mappings are
  configuration, reviewable and version-controlled. (§4.1, §4.2)
- [ ] **Document new connectors** with the items in `docs/source-onboarding.md`.
- [ ] **Privacy.** Synthetic data only in tests and examples. Never commit real employee
  data, production workbooks, graph stores, reports or credentials. Least-privilege
  read-only connector access. Collect only attributes with a defined purpose. Do not send
  employee data to an external AI provider without explicit approval and controls. (§8)
- [ ] **No employee data in agent sessions.** This agent session is itself an external
  AI provider. Never open, read, print or summarise a real workbook, export, graph store
  or report. Work only with synthetic fixtures. (§8)
- [ ] **Reviewer labels are not authentication.** Never present the local reviewer
  argument as access control. (§2, §4.7)
- [ ] **Safe querying.** AI-generated SPARQL is untrusted input: grounded in the published
  ontology, read-only, validated,
  limited to approved graphs, with timeouts and result limits, and answers that include
  provenance and disclose conflicting, stale, missing or untrusted evidence. (§4.8)

## 4. Engineering practices

Use Python 3.11+ and uv (`uv sync --extra dev`). Follow the existing package structure
(`src/ek/`) and conventions; line length is 88.

- Keep modules focused and responsibilities clear.
- Use type hints for public interfaces; prefer explicit data contracts.
- Keep business logic independent of CLI presentation.
- Keep graph-store operations behind a clear interface.
- Handle malformed source records explicitly.
- Make ingestion repeatable and idempotent.
- Avoid unnecessary dependencies; explain any new framework or infrastructure
  dependency.
- Avoid premature microservice decomposition.
- Log meaningfully without exposing employee data.
- Document important design decisions.

## 5. Testing requirements

Every meaningful change includes tests. Cover, as relevant: expected behaviour, invalid
inputs, missing values, conflicting source assertions, provenance preservation,
trust-state transitions, identity-resolution edge cases, re-ingestion and idempotency,
persistence and graph reload, and security-sensitive behaviour.

Use synthetic fixtures only. A change affecting trust, provenance, identity or graph
persistence needs regression tests. Never weaken or remove a test to make an
implementation pass.

## 6. Documentation and architecture decisions

- `docs/` describes the product and how to operate it. It must not link to
  `development/`.
- `development/` holds architecture, designs, ADRs and the roadmap.

Update the documentation when changing ontology definitions, assertion structure,
provenance requirements, trust and promotion rules, source adapter contracts, graph
storage, identity resolution, security boundaries or query behaviour.

Record material architectural changes as ADRs in `development/decisions/`, one file per
decision, with context, decision, alternatives considered, consequences and migration
implications. Do not let implementation details silently redefine the architecture.

## 7. Definition of done

A ticket is not complete because the code works on one happy-path example. Before
declaring work complete:

1. Confirm the acceptance criteria are met.
2. Add or update tests.
3. Run the test suite (`uv run pytest`).
4. Run lint and format checks (`uv run ruff check .`, `uv run ruff format --check .`).
5. Check that no real employee data or credentials were introduced.
6. Check that the provenance and trust invariants still hold.
7. Update the relevant documentation.
8. Record remaining limitations.
9. Update the Pickle/Brine ticket through its supported workflow.
10. Make the work available for review.

Do not claim tests or checks passed unless they were actually run.

## 8. Working style

Prefer small, independently reviewable changes.

When starting a task: read this file and `development/architecture.md`, inspect the
repository structure, read the relevant ticket, and identify dependencies and acceptance
criteria.

When something is ambiguous: do not invent business rules, assume source authority,
assume employee identity or infer permission to access production data. Record the
question and ask for a decision.

When finishing: summarise what changed, list the tests and checks actually run, name
incomplete work, and name architectural decisions that need human approval.

**The primary objective is a trustworthy and explainable employee knowledge platform,
not merely merging data from multiple sources.**

<!-- pickle:begin -->
## Brine (start here)

**Start at [`tickets/BOARD.md`](tickets/BOARD.md)** — the generated index of every ticket by
status. No feature is built directly from a chat message or a raw idea — work enters only as a
ticket whose Implementation Plan has met the READY gate. A *review finding* is different: it
earns a **disposition** (rules §5), and most are resolved without a new ticket.

- The flow engine is the **brine skill** at `.agents/skills/brine/`. It holds
  the rules (`resources/tickets-README.md`), the ticket template
  (`resources/TEMPLATE.md`), and the review protocol
  (`resources/review-protocol.md`). Agents that read `.agents/skills/` find it there
  directly; `pickle install --agent claude` adds a `.claude/skills/brine` view for
  Claude Code. The directory is pickle-owned — `pickle install` and `pickle upgrade`
  both replace it wholesale, so keep hand-written notes outside it.
- Triggers: "make it a ticket", "refine ticket EK-NNN", "implement ticket EK-NNN", "rework ticket
  EK-NNN", "validate ticket EK-NNN" (or "review ticket EK-NNN"), "audit the board".

### Project configuration

- **Build target.** Every ticket targets one registered child-project via `project:`
  frontmatter (`pickle project list`). Registered child-projects: `employee-knowledge`.
- **Commands** (each child's, from `pickle.toml`):
  - `employee-knowledge`: test `uv run pytest` · lint `uv run ruff check . && uv run ruff format --check .`
- **Branch & commit.** Conventional Commits with the **ticket id in brackets at the end of
  the subject** (e.g. `feat(cli): add board audit (EK-2)`) for child-project code. Ticket/board
  bookkeeping uses its own `board: EK-NNN <verb phrase>` form instead — grammar and scope in
  the rules §0. Branch per child:
  - `employee-knowledge`: `feat/EK-NNN-<slug>`
- **WIP limits** (per child):
  - `employee-knowledge`: `3-in-development/` ≤ 1 · `4-in-review/` ≤ 1
- **Commit policy.** Child-projects are **publish-gated**: local WIP commits are encouraged;
  **no push / no merge request without explicit user approval**; after approval, finalize
  (squash or keep history) + push + open the MR — **merging is always the human's**.
  Overarching bookkeeping (tickets, board, docs) may be committed automatically,
  always with **explicit pathspecs** (`git add <paths>`, never `git add -A`/`.`).
- **Where commits land.** Code goes on the child's feature branch; **ticket and board
  bookkeeping is committed on the base branch**, never on a feature branch — a squash-merge
  folds or drops it and the board then disagrees with the tickets it indexes. This covers a
  review's own moves too, and it is why a reviewer on a feature branch reads the ticket from
  the base branch. This project uses the `in-tree` layout, where the board and the code share
  one repository, which is what makes the rule load-bearing here.
  `pickle hooks install` enforces it locally, once per clone: a `pre-commit`
  hook refuses the commit, and a `pre-push` hook refuses the push if it still slipped through
  (bypass either with `--no-verify`).

### Board rule

`tickets/BOARD.md` is **generated** — regenerated wholesale from the ticket files by
`pickle ticket new`, `pickle ticket move` and `pickle board sync`. **Never edit it by
hand**; hand-written planning notes go in `tickets/NOTES.md`. Every ticket move = move
the file + one dated `## History` line, and the board regenerates. Prefer
`pickle ticket move` — it does all of it atomically.
<!-- pickle:end -->

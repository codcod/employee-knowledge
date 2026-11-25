---
id: EK-015
title: Escape source and config text in CLI output
project: employee-knowledge
depends-on: []
spawned-by: [EK-004]
impact: medium
complexity: low
cost: S
---

# EK-015 — Escape source and config text in CLI output

## Outcome

After this ships, the CLI prints every value, reference and message that comes from a
source, a configuration or policy file, an adapter plugin or a command argument exactly as
written. A bracketed value such as `[/x]` or `[bold]x`, or a shortcode such as
`:warning:`, can no longer crash a command or change how its output looks. Terminal
control characters other than tab are shown as visible escapes (`\x1b`, `\x9b`, `\n`)
and never reach the terminal raw. JSON output is unchanged.

## Description

Found in the EK-004 review (finding F9, 2026-11-24). `ek.cli` prints through `rich.print`,
which reads `[...]` as Rich markup. Text from outside the program is interpolated without
escaping:

- workbook values, employee IDs and source references in the `report` tables;
- `ConfigError` and `SourceError` messages, which carry file names, sheet names and
  headers;
- quarantine references and reasons in `ingest-excel` output;
- `IngestError` shapes and paths.

Reproduced on `main` (76745dc) with synthetic data: a department value of `[/x]` makes
`report` exit with a `MarkupError` traceback. A value of `[bold]x` would be shown wrongly
instead of crashing. That misreports source data on screen, though `report-json` stays
correct.

EK-004's rework escaped its own policy strings (version, roles, rationale, policy errors)
for `[...]` markup only. `rich.print` also turns emoji shortcodes such as `:warning:` into
symbols, so a policy version of `v:warning:1` is still shown as `v⚠1` (EK-004 re-review
R1, folded here). The fix for this ticket must cover markup and emoji in every external
string, the policy text included, for example by printing it as `rich.text.Text`.

Folded from the EK-003 review (2026-11-24): `escape()` does not remove terminal control
characters, so a workbook or sheet name holding ESC/OSC sequences reaches the terminal
(F12); strip or replace C0/C1 control characters other than tab in external text. The
new `report` "Data-quality findings" table escapes markup but not emoji (F13), and the
other report tables escape nothing (F11); include all of them in the regression test.

Re-verified on `main` (7a80234, 2026-11-25) with synthetic values:
- `report` exits 1 with a `MarkupError` on a department of `[/x]`. It shows `[bold]x`
  styled and turns `:warning:x` into an emoji.
- `report` and `query` both pass ESC through to the terminal.
- `query` already prints its cells as `Text`, so markup and emoji are safe there.
- The new `ingest` command (EK-012) prints adapter-supplied messages, quarantine
  references and reasons unescaped.

Refined 2026-11-25 (owner decisions):
- **Control characters** (Unicode category Cc, which is C0, DEL and C1, except tab) are
  shown as Python-style visible escapes. They are not replaced or dropped.
- **Format characters** (Cf, such as U+202E or ZWJ) are left alone: real names use some of
  them. Bidi spoofing is recorded as a known limitation.

## Implementation Plan

### 0. Feature branch (mandatory)

```
cd /Users/nka/Projects/codcod/employee-knowledge   # child path "." (in-tree layout)
git checkout main && git pull --ff-only
git checkout -b feat/EK-015-escape-cli-output
```

Work on this branch with local WIP commits. Publishing is gated: no push and no merge
request without the owner's explicit approval (AGENTS.md, rules §0). This is a root-path
child, so tidy the WIP commits into atomic ones before presenting them, and keep that
history by default. Before pushing, run
`git fetch origin main && git diff --name-only origin/main...HEAD | grep '^tickets/'`; it
must print nothing. Merging is the human's.

### Prerequisite gate (hard)

None: `depends-on: []`. Start from a clean tree on an up-to-date `main`, and check that
`uv run pytest` is green first.

### Confirmed design decisions (do not deviate without asking)

1. **One boundary, in `src/ek/cli.py`.** Every string that did not come from a literal in
   `cli.py` is external. That covers source values, employee IDs, issuers, source
   references, quarantine reasons, file and sheet names, exception messages, policy text,
   assertion and event URIs, and command arguments such as `--output`. External text is
   printed only as `rich.text.Text`, through one helper, and never inside an f-string
   passed to `print` as markup. Rich does not parse a `Text` for markup or emoji. The
   `rich.markup.escape` calls and their import are removed: `Text` replaces them.
2. **The helper:** `_clean(value: object) -> str` replaces each character of category Cc
   except tab (`[\x00-\x08\x0a-\x1f\x7f-\x9f]`) with its `unicode_escape` form (`\x1b`,
   `\n`, `\x9b`). Everything else is left exactly as written, Cf characters included.
   Literal markup such as `[red]` stays only in constant strings.
3. **Mixed lines** (a styled constant with external text) are built with
   `Text.assemble`, or as `Text(f"...{_clean(x)}...", style=...)`. Table cells are
   `Text(_clean(...))`, including the cells in `report`'s three tables and in `query`.
4. **JSON is unchanged.** `report-json` and `query --json` already serialise safely, and
   their bytes do not change. The JSON tests stay as they are.
5. **No other module changes.** Messages keep their wording. Business logic in
   `ek.report`, `ek.query`, `ek.ingest` and the adapters is not touched (AGENTS.md §4,
   which keeps presentation in the CLI).
6. **Known limitations, recorded and not fixed:**
   - a literal backslash sequence in a source value (the six characters `\x1b`) looks
     the same as an escaped control character;
   - Cf bidi overrides can still reorder text on screen;
   - typer's own usage errors are out of scope.

### Tasks

#### Task 1 — Helper and output sites

In `src/ek/cli.py`, add `_clean` and a small `_say(*parts)`, which prints a `Text` built
with `Text.assemble`. Then route these sites through them (line numbers are on 7a80234):
- `_policy` errors and the not-in-force line (67, 73);
- `_ingest` errors, model findings, summary, sha256, value-violation and quarantine lines
  (134–156);
- `report` table cells, the accepted-conflict row and the policy lines, with
  `_policy_line` output cleaned (178–232);
- `report-json` "Wrote" (247);
- `query`: the error (275), the cells (295–310) and the trusted-scope lines (318–325),
  adding `_clean` to the existing `Text`;
- `_review`: errors, the outcome line and "Also accepted" (353–361);
- `rebuild-projection` mismatch lines (432).

Remove the `escape` import.

#### Task 2 — Regression tests

Add `tests/test_cli_output.py` with synthetic data only. Build a store with
`ek.ingest.ingest` from two sources, so that there is a discrepancy. Parametrize over the
hostile values `[/x]`, `[bold]x`, `:warning:x`, `Eng\x1b[31mRED`, `a\x9b2Jb` and
`two\nlines`. Put each value in the department value, the employee ID and the source
reference. For each value, assert:
- `report`: exit 0. The output contains the value as written, with controls escaped
  (the value `Eng` + ESC + `[31mRED` appears as the literal text `Eng\x1b[31mRED`). It contains no ESC, no C1
  character and no `⚠`.
- `query --scope all --employee-id <id>` and `--scope trusted` (the "no trusted value"
  line): the same checks.
- `ingest` with an unknown `--source-id` set to the hostile value, so that the
  `ConfigError` echoes it: exit 1, and the value is shown as written.
- `ingest-excel` on a synthetic workbook named `[bold]hr.xlsx` (openpyxl rejects `[`,
  `]` and `:` in sheet titles) whose sheet is titled `a\x9b2J` and whose row is
  quarantined: the quarantine line shows `[bold]hr.xlsx#a\x9b2J!…` as written, with the
  C1 character escaped.
- A policy whose `version = "v:warning:1"` naming a source id `[/x]` (from
  `sources.toml`) as authoritative, so `[/x]` reaches the rationale built by
  `evaluate()` (a policy has no rationale field): the `report` policy line shows both as
  written. A second policy with a future `effective_from`: the `_policy` not-in-force
  line shows the version as written.
- `review accept` with a hostile assertion argument: exit 1, and the "Unknown assertion"
  message is shown as written.
- `_clean` unit test: tab is kept; `\x00`, `\x1b`, `\x7f`, `\x9b` and `\n` are escaped;
  U+202E and ZWJ are unchanged.
- JSON (decision 4): the existing `report-json` and `query --json` tests stay green with
  no edits. Add one case showing that `json.loads` of the `query --json` output gives
  back `Eng` + ESC + `[31mRED` (the original text, not the escaped form), and that the
  raw output has no ESC byte.

Existing tests that assert on CLI output must stay green without being weakened.

### Acceptance test

```
uv run pytest tests/test_cli_output.py -v   # all pass
uv run pytest                               # all pass
uv run ruff check . && uv run ruff format --check .
grep -n "escape(" src/ek/cli.py             # prints nothing
```

Manual, synthetic only: ingest `examples/employees.xlsx` and
`examples/employees-directory.xlsx` (operating.md example), then run `report` and
`query --scope all --employee-id <an example id>`. The output should be the same as
before, apart from the fix.

### Docs update (mandatory when user-facing)

- `docs/operating.md`, after the commands section or under "Report discrepancies": one
  short paragraph saying that text from sources, configuration and policy files is
  printed as written; that control characters other than tab are shown as escapes such
  as `\x1b`; and that JSON output carries the original text. State the backslash
  ambiguity in one line.
- `development/architecture.md` §8 (security): one bullet saying that the CLI prints
  external text without interpreting it, and that control characters are escaped. No ADR,
  because this changes no architectural decision.
- No changelog. `docs/` must not link to `development/`.

### Finish (mandatory)

1. The acceptance test is green, `uv run pytest` passes and both ruff checks are clean.
2. The docs are updated.
3. Write the summary: the files touched, the decisions honoured, and the limitations
   (decision 6).
4. Suggested commit message:

   ```
   fix(cli): print source and config text as written (EK-015)

   External strings are printed as rich Text, so markup and emoji
   shortcodes in values, references, messages and policy text are shown
   literally. Control characters other than tab are shown as visible
   escapes. JSON output is unchanged.
   ```

5. Tidy the WIP commits into atomic ones (root-path child).
6. Commit locally on the branch, and do not push. Then run
   `pickle ticket move EK-015 in-review --reason "acceptance green"`.

## Review

Review of `feat/EK-015-escape-cli-output` (9621470, plus the review's test commit 17b65de),
2026-11-25. Audits by a delegated independent reviewer (fresh sub-agent); classification,
dispositions and the move by the orchestrator, who also wrote the branch.

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F1 | non-blocking | correctness | new ticket (EK-016) | An undecodable argv or file-name byte becomes a lone surrogate (Cs), which `_clean` does not escape (decision 2 is Cc only), so printing it raises `UnicodeEncodeError`. Pre-existing | Reproduced on branch and on `main`: `ingest x.xlsx --config <synthetic> --source-id $'\xff'` exits 1 with a `UnicodeEncodeError` traceback instead of the `Unknown source id` message | Escape `\ud800-\udfff` in `_CONTROL`; needs owner sign-off, as it amends decision 2 |
| F2 | non-blocking | correctness | new ticket (EK-016) | typer's pretty tracebacks show local variables by default, so any uncaught error can print employee data to the terminal (AGENTS.md §4, architecture §8). Pre-existing | `typer.Typer(help=...)` at `src/ek/cli.py:33` with no `pretty_exceptions_show_locals`; the F1 traceback printed its frames' locals | `pretty_exceptions_show_locals=False` |
| F3 | non-blocking | test-gap | fixed inline | No test for `report-json --output` with a hostile path, a site decision 1 names | `tests/test_cli_output.py` had no case; added `test_report_json_output_path_is_shown_as_written` (17b65de), which fails on the old `cli.py` (6 failed) and passes on the branch | — |
| F4 | non-blocking | design | noted | Text printed through `_say` is no longer coloured by Rich's ReprHighlighter, so numbers and URIs in the run summary, sha256 and review lines lose highlighting on a colour terminal | `Console(force_terminal=True).print(str)` colours `42`; `print(Text(...))` does not. Invisible in CliRunner and JSON output | None: not highlighting external text is the intent of decision 1 |
| F5 | non-blocking | design | noted | Two messages are split into a `msg` prefix plus a tuple (`_policy` not-in-force, `_ingest` value violations) only to fit 88 columns | `src/ek/cli.py`, `_policy` and `_ingest` | None: an implicit concatenation inside the tuple trips ruff ISC004, which is why it was split; wording is unchanged |

Dispositions: 1 fixed inline (F3), 2 new ticket (F1, F2, batched as EK-016), 2 noted (F4, F5), 0 folded.
cost: estimated S, actual S

- [x] Reviewer independence settled (step 0): delegated to a fresh independent sub-agent; no delegated findings discarded. Its F1 was split into F1 and F2 above (separable dispositions)
- [x] In-tree stale-branch check (step 0a): `pickle doctor` warned of the branch's stale ticket copy; rebased onto `main`, then 0 warnings
- [x] Implementation audit (steps 1, 2): acceptance test re-run verbatim and green (`test_cli_output.py` 22 then 28 passed, suite 267 then 273 passed, ruff clean, `grep escape(` empty); the manual run on the examples gave output identical to `main`; Tasks 1–2 and decisions 1–6 met
- [x] Correctness hunt (step 3): angle hunt, one pass over all eight angles by the delegated reviewer, no sub-agents (`complexity: low`), angle 7 inside the pass; no host tool run. F1 reproduced by hand on branch and `main`
- [x] Consistency audit (step 4): project-wide grep; no contract drift
- [x] Documentation audit (step 4a): `docs/operating.md` paragraph and architecture §8 bullet present; whole-tree sweep clean; no docs build configured
- [x] Docs-readability pass (step 4b): conscious skip, since no dedicated reviewer is configured and the changed prose is two short paragraphs
- [x] Findings recorded with severity, class and disposition; summary and cost lines present (step 5)
- [x] Ticket moved to `tickets/6-done/`; History appended (step 6)
- [x] Other references (step 7): `development/architecture.md` §8 already updated on the branch; no other ticket or doc references EK-015 behaviour
- [x] Impact sweep (step 8): no ticket in `1-to-do/` or `2-ready/` references EK-015 apart from EK-016, which it spawned
- [x] Summary, commit message and PR attributes approved by the owner (fold into one commit, push, open PR) (step 9)

## History

- 2026-11-24 — created (TO DO). source: review: EK-004 review finding F9 (pre-existing unescaped Rich markup in CLI output; owner chose a new ticket)
- 2026-11-24 — folded EK-004 re-review R1 (emoji shortcodes in policy text are still rendered)
- 2026-11-24 — folded EK-003 review F11–F13 (unescaped report tables, terminal control characters, emoji in the findings table)
- 2026-11-25 — note (EK-005 applicability gate): the new `query` command builds its table cells as `rich.text.Text`, so markup and emoji shortcodes in source text are not interpreted there. Terminal control characters are not stripped yet; include `query` in that fix
- 2026-11-25 — folded EK-005 review F1: `query` passes ESC and C1 (U+009B) control sequences in source text to the terminal, in table cells and in the trusted-scope "no trusted value" / "N unaccepted" lines; `--json` is safe. Reproduced with a synthetic `department="Eng\x1b[31mRED"`. Cover `query` alongside `report`
- 2026-11-25 — impact note from EK-012 gate (G2): the new generic `ingest` command reuses `ingest-excel`'s unescaped error, finding and quarantine output, and that text can now come from third-party adapter code
- 2026-11-25 — refined. Re-verified on main 7a80234 (report MarkupError on `[/x]`, `[bold]` styled, emoji rendered, ESC passes in report and query). Owner decisions: Cc except tab shown as visible escapes; Cf left alone (bidi a known limitation). Grades unchanged (medium / low / S). Plan written
- 2026-11-25 — TO DO → READY: plan complete
- 2026-11-25 — plan amended inline: applicability gate G1–G3 (non-blocking, owner-approved). G1: openpyxl rejects `[`/`:` in sheet titles, so the markup goes in the workbook file name and the sheet title carries a C1 character. G2: a policy has no rationale field, so `[/x]` enters the rationale through an authoritative source id, and a second future-dated policy covers the not-in-force line. G3: the JSON check is on `json.loads` output plus no raw ESC byte
- 2026-11-25 — READY → IN DEVELOPMENT: picked up; gate G1–G3 non-blocking, plan amended inline
- 2026-11-25 — IN DEVELOPMENT → IN REVIEW: acceptance green
- 2026-11-25 — IN REVIEW → DONE: review: no blocking findings; 1 fixed inline (F3), 2 new ticket (F1, F2 -> EK-016), 2 noted (F4, F5)

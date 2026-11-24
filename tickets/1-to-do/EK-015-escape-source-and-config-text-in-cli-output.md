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
source or a configuration file exactly as written. A bracketed value such as `[/x]` or
`[bold]` can no longer crash a command or change how its output looks.

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

Likely approach, to be confirmed at refinement: wrap every interpolated external string in
`rich.markup.escape()`, or print it with `markup=False`, and add a regression test with
bracketed synthetic values in every printing command.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-24 — created (TO DO). source: review: EK-004 review finding F9 (pre-existing unescaped Rich markup in CLI output; owner chose a new ticket)
- 2026-11-24 — folded EK-004 re-review R1 (emoji shortcodes in policy text are still rendered)

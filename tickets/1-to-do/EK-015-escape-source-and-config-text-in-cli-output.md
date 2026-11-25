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

Folded from the EK-003 review (2026-11-24): `escape()` does not remove terminal control
characters, so a workbook or sheet name holding ESC/OSC sequences reaches the terminal
(F12); strip or replace C0/C1 control characters other than tab in external text. The
new `report` "Data-quality findings" table escapes markup but not emoji (F13), and the
other report tables escape nothing (F11); include all of them in the regression test.

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
- 2026-11-24 — folded EK-003 review F11–F13 (unescaped report tables, terminal control characters, emoji in the findings table)
- 2026-11-25 — note (EK-005 applicability gate): the new `query` command builds its table cells as `rich.text.Text`, so markup and emoji shortcodes in source text are not interpreted there. Terminal control characters are not stripped yet; include `query` in that fix
- 2026-11-25 — folded EK-005 review F1: `query` passes ESC and C1 (U+009B) control sequences in source text to the terminal, in table cells and in the trusted-scope "no trusted value" / "N unaccepted" lines; `--json` is safe. Reproduced with a synthetic `department="Eng\x1b[31mRED"`. Cover `query` alongside `report`
- 2026-11-25 — impact note from EK-012 gate (G2): the new generic `ingest` command reuses `ingest-excel`'s unescaped error, finding and quarantine output, and that text can now come from third-party adapter code

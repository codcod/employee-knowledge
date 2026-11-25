---
id: EK-016
title: Harden CLI error output: surrogates and traceback locals
project: employee-knowledge
depends-on: []
spawned-by: [EK-015]
impact: medium
complexity: low
cost: S
---

# EK-016 — Harden CLI error output: surrogates and traceback locals

## Outcome

After this ships, a command argument or file name holding an undecodable byte is shown as
a visible escape instead of crashing the CLI, and an unexpected error's traceback no longer
prints local variables, which can hold employee data.

## Description

Found in the EK-015 review (finding F1, 2026-11-25); both parts are pre-existing on
`main`.

- **Surrogates.** On POSIX, an undecodable byte in argv or a file name becomes a lone
  surrogate (category Cs). `ek.cli._clean` escapes only category Cc (EK-015 decision 2), so
  printing such text raises `UnicodeEncodeError`. Reproduced with synthetic config:
  `employee-knowledge ingest x.xlsx --config sources.toml --source-id $'\xff'` exits 1
  with a traceback instead of `Unknown source id '\udcff'`. Likely fix: add
  `\ud800-\udfff` to `_CONTROL` (`unicode_escape` already renders them as `\udcff`).
  This amends EK-015 decision 2, so the owner signs off.
- **Traceback locals.** `typer.Typer` defaults to `pretty_exceptions_show_locals=True`,
  so any uncaught exception prints the frame's local variables (records, values, paths)
  to the terminal. That conflicts with AGENTS.md §4 ("log meaningfully without exposing
  employee data") and architecture §8. Likely fix: `pretty_exceptions_show_locals=False`
  on `app` (and `review_app`), with a regression test that an induced error prints no
  locals.

Soft coupling: EK-015 (the `_clean` boundary in `src/ek/cli.py`).

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-25 — created (TO DO). source: pickle ticket new

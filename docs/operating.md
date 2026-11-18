# Operating guide

Employee Knowledge is a local command-line tool. It reads source files, stores assertions
in a local graph file and reports discrepancies. See [trust-model.md](trust-model.md) for
what the graphs mean.

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Graph store

All commands read and write one TriG file, `./data/employee-knowledge.trig` by default.
Override the location with the `EMPLOYEE_KNOWLEDGE_STORE` environment variable (see
`.env.example`).

The store can contain personal data. Keep it outside version control (`data/` is
git-ignored) and do not share it.

Only one command should use the store at a time. Each command loads the whole file and
writes it back. Nothing prevents two commands running together, and if they do, one
command's changes are lost. A command that fails leaves the previous store intact: the
new file is written beside it and replaces it only when complete.

Stores created before ingestion runs were introduced use an older layout. Delete them
and ingest again.

## Commands

### Ingest an Excel workbook

```bash
uv run employee-knowledge ingest-excel <workbook.xlsx> --source-id <id> [--config <path>]
```

- Reads the source configuration from `config/sources.toml`, or the file named by
  `--config`. Start by copying `examples/sources.toml`. The `--source-id` must name an
  enabled Excel source in that file.
- Reads the sheet set by the source's `sheet` key, or the active sheet if none is set.
- The first row holds the headers. Every column named in the source's `mapping` must be
  present; unmapped columns are ignored. The command stops without ingesting anything if
  the file is not a readable `.xlsx`, the sheet is missing or empty, a header appears
  twice, or a mapped column is missing.
- Rows are identified by employee ID, not by row number, so re-sorting the sheet does
  not create new assertions.
- A row without an employee ID, or with an ID that is a decimal number, date or
  true/false value, is quarantined. So is every row whose ID appears on more than one
  row of the sheet. The command lists each one by workbook, sheet and
  row with the reason. Fully blank rows are skipped.
- Each non-blank mapped value becomes one assertion in the untrusted graph. Leading and
  trailing spaces are trimmed, and work email addresses are lowercased.
- Each ingestion is a run with its own named graph. The command prints the run, how many
  values it observed, how many were new assertions, and the SHA-256 of the workbook.
  Values already stored, trusted or not, are recorded as observed again but keep their
  trust state.
- Values that fail structural validation are stored, flagged and counted. If the system
  itself produces an invalid record, the command exits with status 2 and saves nothing.

Format the employee ID column as text in Excel. A numeric ID cell has already lost any
leading zeros, and this cannot be detected.

Use the same `--source-id` every time you ingest the same source. A different ID is
treated as a different source.

### Report discrepancies

```bash
uv run employee-knowledge report
uv run employee-knowledge report-json [--output reports/discrepancies.json]
```

`report` prints up to four tables:

- **Discrepancies:** every employee and property with more than one distinct value, each
  value with its source and review state. A row marks groups where conflicting values
  are both accepted.
- **Not observed in the latest run:** values that the most recent ingestion of their
  source no longer contained. Their review state is unchanged.
- **Invalid values:** values that failed structural validation in any run.
- **Quarantined rows:** rows from the latest run of each source that could not be used,
  with the reason.

`report-json` writes the same report to a file, adding assertion and employee URIs and,
for every value, each observation: run, source reference, exact source text, observation
time (if supplied) and validation result. `reports/` is git-ignored.

The report shows employee data. Treat it like the store.

### Review an assertion

```bash
uv run employee-knowledge review accept <assertion-uri> --reviewer <label> --reason "<why>"
uv run employee-knowledge review reject <assertion-uri> --reviewer <label> --reason "<why>"
uv run employee-knowledge review request-evidence <assertion-uri> --reviewer <label> --reason "<why>"
uv run employee-knowledge review supersede <assertion-uri> [--by <assertion-uri>] --reviewer <label> --reason "<why>"
uv run employee-knowledge review reopen <assertion-uri> --reviewer <label> --reason "<why>"
```

Take assertion URIs from `report-json`. Each command records one review event in the
audit graph, with the reviewer label, reason, time and the state change, and moves the
assertion to the trusted graph (accepted) or the untrusted graph (any other state). See
[trust-model.md](trust-model.md) for which actions are allowed from which state. A
refused action records nothing and exits with status 1.

`supersede --by` names the assertion that replaces this one. It must be about the same
employee and property.

When you accept an assertion and another accepted assertion for the same employee and
property has a different value, the command lists it. Both stay accepted; resolve the
conflict with another review action.

The reviewer label is free text. It identifies nobody and grants nothing.

### Rebuild the trusted and untrusted graphs

```bash
uv run employee-knowledge rebuild-projection --check
uv run employee-knowledge rebuild-projection
```

Which of the two graphs an assertion is in follows from its review events. `--check`
lists any assertion in the wrong graph and exits with status 1 if there is one, changing
nothing. Without `--check`, the command moves those assertions.

## Example run

This walks the whole flow on the synthetic examples, using a throwaway store.

```bash
mkdir -p config && cp examples/sources.toml config/sources.toml
export EMPLOYEE_KNOWLEDGE_STORE=./data/demo.trig

# Ingest two sources. The directory has one row without an employee ID; it is
# quarantined and listed.
uv run employee-knowledge ingest-excel examples/employees.xlsx --source-id hr-export
uv run employee-knowledge ingest-excel examples/employees-directory.xlsx --source-id people-directory

# One discrepancy: E-1002's department is "People" in HR and "Product" in the
# directory. E-1001's " Engineering " is not one: it matches after trimming.
uv run employee-knowledge report
uv run employee-knowledge report-json --output reports/demo.json

# Accept the HR value, using its "assertion" URI from reports/demo.json.
uv run employee-knowledge review accept <assertion-uri> --reviewer demo --reason "Matches HR"

# The accepted value is now in the trusted graph. The directory value is still a
# candidate, and the discrepancy is still reported.
uv run employee-knowledge report

# Ingesting again adds runs and observations but no assertions, and changes no state.
uv run employee-knowledge ingest-excel examples/employees.xlsx --source-id hr-export
uv run employee-knowledge rebuild-projection --check
```

Both workbooks contain synthetic people only. Delete `data/demo.trig` and
`reports/demo.json` afterwards.

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

### Ingest a file

```bash
uv run employee-knowledge ingest <file> --source-id <id> [--config <path>]
uv run employee-knowledge ingest-excel <workbook.xlsx> --source-id <id> [--config <path>]
```

- Reads the source configuration from `config/sources.toml`, or the file named by
  `--config`. Start by copying `examples/sources.toml`. The `--source-id` must name an
  enabled source in that file.
- `ingest` reads the file with the source's kind: `excel`, or a kind an installed
  package adds (see [source-onboarding.md](source-onboarding.md)). `ingest-excel` does
  the same, but only for Excel sources. Both print the same summary and use the same
  exit statuses: 1 when the configuration or the file cannot be used, 2 when the system
  produced an invalid record. In both cases nothing is saved.

For Excel sources:

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
  values it observed, how many were new assertions, and the SHA-256 of the file.
  Values already stored, trusted or not, are recorded as observed again but keep their
  trust state.
- Values that fail structural validation are stored, flagged and counted. If the system
  itself produces an invalid record, the command exits with status 2 and saves nothing.

Format the employee ID column as text in Excel. A numeric ID cell has already lost any
leading zeros, and this cannot be detected.

Use the same `--source-id` every time you ingest the same source. A different ID is
treated as a different source.

### Set up an authority policy

The authority policy says which sources to believe for each property (see
[trust-model.md](trust-model.md)). It is optional: without it, every conflict is
reported as unresolved.

`report`, `report-json` and the `review` commands read `config/policy.toml`, or the file
named by `--policy`. A missing `config/policy.toml` means no policy; a file named with
`--policy` must exist. The file is local and not committed. Start from
`examples/policy.toml`, whose rows only illustrate the format. Putting a policy file in
place is what approves it, so have the data owner approve its contents first.

```toml
version = "2026-1"             # recorded on every review event; change it on every edit
effective_from = 2026-01-01    # in force from this date (UTC)

[[properties]]
property = "department"        # a field name from the source configuration
authoritative = ["hr-export"]  # source ids; may be empty
secondary = ["people-directory"]
conflict_rule = "prefer-authoritative"   # or "manual"
freshness_days = 365           # optional
required = true                # optional, default false
reviewer_roles = ["hr-reviewer"]         # optional; for people to read, not checked
```

Every source id must name a source in the source configuration. When a policy file
exists, these commands also read `config/sources.toml`, or the file named by
`--config`, to check the ids. Unknown keys, unknown properties, unknown sources and
invalid values are errors. If the policy file is invalid, the command exits with status
1 and changes nothing.

### Report discrepancies

```bash
uv run employee-knowledge report [--policy <path>] [--config <path>]
uv run employee-knowledge report-json [--output reports/discrepancies.json] [--policy <path>] [--config <path>]
```

`report` prints up to three tables:

- **Discrepancies:** every employee and property with more than one distinct value, each
  value with its source and review state. A row marks groups where conflicting values
  are both accepted. After the table, one line per discrepancy gives the authority
  policy's recommendation, or "no authority policy: unresolved".
- **Not observed in the latest run:** values that the most recent ingestion of their
  source no longer contained. Their review state is unchanged.
- **Data-quality findings:** one row per finding, with its category, employee,
  property, evidence (source id and source reference) and rationale. It prints no values. The
  categories are invalid values, unusable rows (latest run of each source), broken
  manager references and, when an authority policy is in force, missing required
  properties and stale or freshness-unknown values. Without a policy in force, a line
  says the required and freshness checks are off. A policy row turns these checks on
  for its property with `required = true` and `freshness_days`. See
  [trust-model.md](trust-model.md) for each category.

`report-json` writes the same report to a file, adding assertion and employee URIs and,
for every value, each observation: run, source reference, exact source text, observation
time (if supplied) and validation result. Its `policy` key gives the policy version and
whether it is in force. Each discrepancy's `policy` gives the outcome, the rationale,
the recommended assertion URIs and the reviewer roles. The `findings` key lists every
data-quality finding with its `category`, `rationale` and `evidence` (assertion URI,
source, source reference and, if supplied, observation time), and its employee and
property where they apply. The `validation_violations` and `quarantined` keys are
unchanged. `reports/` is git-ignored.

The report shows employee data. Treat it like the store.

### Review an assertion

```bash
uv run employee-knowledge review accept <assertion-uri> --reviewer <label> --reason "<why>"
uv run employee-knowledge review reject <assertion-uri> --reviewer <label> --reason "<why>"
uv run employee-knowledge review request-evidence <assertion-uri> --reviewer <label> --reason "<why>"
uv run employee-knowledge review supersede <assertion-uri> [--by <assertion-uri>] --reviewer <label> --reason "<why>"
uv run employee-knowledge review reopen <assertion-uri> --reviewer <label> --reason "<why>"
```

Every review command also takes `--policy <path>` and `--config <path>`, as described
under the authority policy above.

Take assertion URIs from `report-json`. Each command records one review event in the
audit graph, with the reviewer label, reason, time, the state change and the version of
the authority policy in force (`none` without one), and moves the
assertion to the trusted graph (accepted) or the untrusted graph (any other state). See
[trust-model.md](trust-model.md) for which actions are allowed from which state. A
refused action records nothing and exits with status 1.

`supersede --by` names the assertion that replaces this one. It must be about the same
employee and property.

When you accept an assertion and another accepted assertion for the same employee and
property has a different value, the command lists it. Both stay accepted; resolve the
conflict with another review action.

The reviewer label is free text. It identifies nobody and grants nothing.

### Query facts

```bash
uv run employee-knowledge query --scope trusted|all [--employee-id <id>] [--issuer <issuer>] [--property <field>] [--json]
```

`--scope` is required. There is no default trust level:

- **`trusted`:** accepted values only, read from the trusted graph. A line under the
  table says how many other values exist for an employee and property: "N unaccepted
  value(s) not shown; use --scope all". Unaccepted means any review state other than
  Accepted: Candidate, NeedsEvidence, Rejected or Superseded. Those values are counted
  but never shown. When nothing is accepted yet, the line "no trusted value" says so.
- **`all`:** every value with its review state, from the trusted and untrusted graphs.
  Use it to see what a trusted answer leaves out.

The table title names the scope and the graphs read. Each row gives the employee,
issuer, property, value, source, review state and source references. When an employee
and property have more than one value in the scope (in `trusted`, more than one
accepted value), a row says so; no value is picked.

Filters combine. `--property` takes a field name such as `department` or
`employment_status`; an unknown name is an error. `--employee-id` without `--issuer`
matches the ID under every issuer, but each issuer's employee is listed separately and
never merged. With no filter, every employee and property is listed.

`--json` prints the results instead: one entry per employee and property, with
`values`, `conflict` and, in `trusted` scope, `untrusted_candidates` (the count above).
Each fact gives its assertion URI, source, review state, whether the source's latest
run observed it, every observation (run, source reference, exact source text,
observation time and validation result) and `latest_review`: the reviewer label,
action, reason, policy version and time of its latest review event, or `null`.

The command only reads; it never changes the store. If the trusted and untrusted
graphs disagree with the review events, `trusted` scope refuses to answer ("projection
out of date; run rebuild-projection") and exits with status 1, rather than risk showing
an unaccepted value. Run `rebuild-projection` (below), then query again. A missing
`--scope` or an unknown scope exits with status 2.

The output shows employee data. Treat it like the store.

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
cp examples/policy.toml config/policy.toml   # optional: the example authority policy
export EMPLOYEE_KNOWLEDGE_STORE=./data/demo.trig

# Ingest two sources. The directory has one row without an employee ID; it is
# quarantined and listed.
uv run employee-knowledge ingest-excel examples/employees.xlsx --source-id hr-export
uv run employee-knowledge ingest-excel examples/employees-directory.xlsx --source-id people-directory

# One discrepancy: E-1002's department is "People" in HR and "Product" in the
# directory. E-1001's " Engineering " is not one: it matches after trimming. With the
# example policy, the report recommends the HR value; nothing is accepted yet.
# Data-quality findings: E-1002's manager E-1004 is not an employee, the directory row
# without an ID, and, with the example policy, freshness-unknown for each department
# value (the workbooks give no observation time).
uv run employee-knowledge report
uv run employee-knowledge report-json --output reports/demo.json

# No trusted department for E-1002 yet: "2 unaccepted value(s) not shown".
uv run employee-knowledge query --scope trusted --employee-id E-1002 --property department

# Accept the HR value, using its "assertion" URI from reports/demo.json.
uv run employee-knowledge review accept <assertion-uri> --reviewer demo --reason "Matches HR"

# The accepted value is now in the trusted graph. The directory value is still a
# candidate, and the discrepancy is still reported.
uv run employee-knowledge report

# The trusted answer is "People", with "1 unaccepted value(s) not shown". The all
# scope shows both values, Accepted and Candidate, and flags the conflict.
uv run employee-knowledge query --scope trusted --employee-id E-1002 --property department
uv run employee-knowledge query --scope all --employee-id E-1002 --property department

# Ingesting again adds runs and observations but no assertions, and changes no state.
uv run employee-knowledge ingest-excel examples/employees.xlsx --source-id hr-export
uv run employee-knowledge rebuild-projection --check
```

Both workbooks contain synthetic people only. Delete `data/demo.trig`,
`reports/demo.json` and `config/policy.toml` afterwards.

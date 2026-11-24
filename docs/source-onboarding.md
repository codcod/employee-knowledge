# Source onboarding

How to bring a new source of employee information into Employee Knowledge.

## Before connecting anything

Record the following for the source and get approval from its data owner:

| Item | Question to answer |
|---|---|
| Purpose | Which business question does this source help answer? |
| Data owner | Who owns the source and approves access? |
| Data accessed | Which fields are read? Drop any that are not needed. |
| Permissions | Which read-only account or scope is used? Never use write access. |
| Identifiers | Which employee identifier does the source use, and who issues it? |
| Provenance | What identifies a record and its version (sheet/row, page ID and version, issue key, dataset refresh)? |
| Retention | How long are extracted values kept, and how are corrections and deletions handled? |
| Security | Where are credentials kept? They must never be committed or written into configuration files. |

Use synthetic data for any test or example. Never commit a real export.

## Excel sources

Excel is the only supported source type today.

1. Make sure the workbook has a header row and an employee ID column formatted as text.
   Rows without a usable employee ID are quarantined and listed (see
   [operating.md](operating.md)).
2. Add a source entry to the source configuration (below) that maps each field to the
   workbook's column header.
3. Pick a stable source ID and use it for every ingestion of this source.

### Source configuration

The command-line tool reads `config/sources.toml`, which is local and not committed.
Copy `examples/sources.toml` to start. Each `[[sources]]` entry has:

| Key | Meaning |
|---|---|
| `id` | Stable source ID. |
| `kind` | `excel`. Confluence, Jira and Power BI entries must have `enabled = false`. |
| `enabled` | Optional, default `true`. Disabled sources cannot be ingested. |
| `issuer` | Who issues the employee IDs in this source. |
| `sheet` | Optional sheet name; the active sheet if omitted. |
| `mapping_version` | Increase it every time `mapping` changes. |
| `mapping` | Field name = column header. Must include `employee_id`. Fields: `full_name`, `work_email`, `department`, `job_title`, `manager_employee_id`, `location`, `employment_status`. |

Unknown keys are an error. There is no setting for trust: every ingested value starts
untrusted.

A new source is not authoritative for anything. It becomes authoritative for a property
only when an approved authority policy names it for that property (see
[operating.md](operating.md)). Even then, its values still need a review.

## Confluence, Jira and Power BI

Not available yet. These connectors stay disabled until the questions above are answered
for each one.

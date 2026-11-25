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

Excel is the built-in source kind. Other file formats can be added from another package
(see [Adding a source kind from another package](#adding-a-source-kind-from-another-package)).

1. Make sure the workbook has a header row and an employee ID column formatted as text.
   Rows without a usable employee ID are quarantined and listed (see
   [operating.md](operating.md)).
2. Add a source entry to the source configuration (below) that maps each field to the
   workbook's column header.
3. Pick a stable source ID and use it for every ingestion of this source.

### Source configuration

The command-line tool reads `config/sources.toml`, which is local and not committed.
Copy `examples/sources.toml` to start. Every `[[sources]]` entry has these keys:

| Key | Meaning |
|---|---|
| `id` | Stable source ID. |
| `kind` | `excel`, or a kind an installed package adds. Confluence, Jira and Power BI entries must have `enabled = false` until a package adds them. |
| `enabled` | Optional, default `true`. Disabled sources cannot be ingested, but are still checked. |
| `issuer` | Who issues the employee IDs in this source. |
| `mapping_version` | Increase it every time `mapping` changes. |
| `mapping` | Field name = column header (or the source's own field name). Must include `employee_id`. Fields: `full_name`, `work_email`, `department`, `job_title`, `manager_employee_id`, `location`, `employment_status`. |

Any other key is an option of the source's kind. Excel has one:

| Key | Meaning |
|---|---|
| `sheet` | Optional sheet name; the active sheet if omitted. |

Unknown keys are an error. There is no setting for trust: every ingested value starts
untrusted.

A new source is not authoritative for anything. It becomes authoritative for a property
only when an approved authority policy names it for that property (see
[operating.md](operating.md)). Even then, its values still need a review.

## Adding a source kind from another package

A separate Python package can add a file-based source kind without changing Employee
Knowledge. Once it is installed, `employee-knowledge ingest <file> --source-id <id>`
ingests sources of that kind like Excel ones: same provenance, same validation, and every
value starts untrusted.

### Depend on Employee Knowledge

Depend on a built wheel, or on a tagged release from the repository:

```bash
uv add "employee-knowledge @ git+<repo-url>@<tag>"
```

### Register the kind

Declare an entry point in the package's `pyproject.toml`. The name is the `kind` used in
`sources.toml`:

```toml
[project.entry-points."employee_knowledge.adapters"]
csv = "my_package.csv_source:plugin"
```

`plugin` is an object with two methods:

```python
from pathlib import Path

from ek.adapters.base import EmployeeRecord, ReadResult, SourceError
from ek.config import ConfigError, SourceConfig


class CsvSource:
    def parse_options(
        self, options: dict[str, object], where: str
    ) -> dict[str, object]:
        # Every key of the [[sources]] entry except id, kind, enabled, issuer,
        # mapping_version and mapping. Refuse anything unknown or invalid.
        if unknown := set(options) - {"delimiter"}:
            raise ConfigError(f"{where}: unknown keys {sorted(unknown)}")
        return {"delimiter": options.get("delimiter", ",")}

    def read(self, path: Path, source: SourceConfig) -> ReadResult:
        # Read the file once; hash the same bytes you parse.
        ...


plugin = CsvSource()
```

The options `parse_options` returns are in `source.options` when `read` runs. Errors in
loading a kind are reported when the source configuration is read: an unknown kind, a
kind two packages register, or a package that fails to import. Only kinds named in the
configuration are loaded.

### Rules for a source kind

- **Read only.** Never change, move or lock the file.
- **File provenance.** Return the file's own name (not a path) and the SHA-256 of the
  exact bytes read. Employee Knowledge hashes the file again and stops the ingestion if
  either does not match. Give each record a reference that finds it again in the file,
  such as `people.csv!row 2`.
- **Usable records.** Each record's employee ID must be non-blank text with no
  surrounding spaces, and appear on only one record of the file; every value must be
  text. Quarantine records that fall short. When records share an employee ID,
  quarantine every one of them, as the Excel adapter does: keeping one would pick a
  value. A record that breaks these rules stops the ingestion, and nothing is saved.
- **Unreadable sources.** Raise `SourceError` with a message that holds no employee
  data. Put individual unusable records in `quarantined`, with a reason, instead of
  dropping them. Quarantine reasons and record references are printed, so they must
  not hold employee data either.
- **No trust decisions.** Do not filter, rank or pick between values. Every value goes
  in, untrusted.
- **Ontology fields only.** Return only the fields the source's `mapping` names. A field
  outside it stops the ingestion. New fields go through the ontology first.
- **No credentials** in code, in options or in `sources.toml`.

Each new kind still needs the items in [Before connecting anything](#before-connecting-anything)
answered and approved for every source of that kind.

Only file sources are supported. Sources read through an API need a source version in
their provenance, which is not available yet.

## Confluence, Jira and Power BI

Not available yet. These connectors stay disabled until the questions above are answered
for each one.

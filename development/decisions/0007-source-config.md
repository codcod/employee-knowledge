# ADR-0007: Source configuration in TOML

- **Status:** Accepted (2026-11-17)
- **Related:** ADR-0003, ADR-0004
- **Amended by:** [ADR-0011](0011-source-adapter-plugins.md): kinds come from adapter
  plugins, and every key outside the common ones is the plugin's option.

## Context

Mappings must be configuration, reviewable and versioned (architecture §4.2, AGENTS.md).
The old YAML example had three problems:

- No code read it.
- Its column names didn't match the example workbook.
- It had a `trust_on_ingest` key, which implied trust could be configured per source,
  against architecture §3.3.

The CLI also accepted any free-text `--source-id`. Ingesting one workbook under two IDs
would therefore look like two independent sources.

## Decision

- Source configuration is TOML, read with the standard-library `tomllib`. No new
  dependency.
- The CLI reads `config/sources.toml` (git-ignored, local) by default; `--config` sets
  another path. If the file is missing, the CLI says so and points to
  `examples/sources.toml`.
- `--source-id` must match a configured, enabled source.

Schema for each `[[sources]]` entry:

| Key | Required | Meaning |
|---|---|---|
| `id` | yes | Stable source ID, used in source URIs and assertion IDs. |
| `kind` | yes | `excel`; `confluence`, `jira` and `powerbi` are accepted but must be `enabled = false`. |
| `enabled` | no (default `true`) | Disabled sources cannot be ingested. |
| `issuer` | yes for `excel` | Employee-ID issuer (ADR-0004). |
| `sheet` | no | Sheet name; default is the active sheet. |
| `mapping_version` | yes for `excel` | Bump it whenever `mapping` changes. Recorded on every run. |
| `mapping` | yes for `excel` | Table of ontology field → source column header. Must include `employee_id`. Every field must map to a known assertable property. |
| `allowed_spaces`, `allowed_projects`, `workspace_id`, `dataset_id` | per connector | Placeholders for disabled connectors. |

- Unknown keys are an error. That makes trust or authority settings impossible to add by
  accident; source authority will get its own reviewed policy model (Task-012).
- The loader only reads. Nothing writes the configuration.

## Alternatives considered

- **YAML with PyYAML.** Familiar, but adds a dependency for what the standard library
  already does. Rejected.
- **Mappings in code** (today's `DEFAULT_COLUMN_MAP`). Not reviewable as configuration
  and not versioned per source. Rejected.
- **JSON.** Standard library, but no comments, and comments matter for reviewable
  mappings. Rejected.

## Consequences

- Each machine needs a local `config/sources.toml` (copied from the example).
- A mapping change without a `mapping_version` bump goes unnoticed. Review catches it;
  the loader cannot.

## Migration

`docs/source-mapping.example.yaml` became `examples/sources.toml`.
`DEFAULT_COLUMN_MAP` was removed.

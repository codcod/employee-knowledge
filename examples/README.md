Synthetic fictional data only. Never commit a production workbook or export.

- `employees.xlsx`: example HR export (sheet `Employees`, source `hr-export`).
- `employees-directory.xlsx`: example people directory (sheet `Directory`, source
  `people-directory`) with its own column headers. It disagrees with the HR export on
  one value (E-1002's department), differs only by surrounding spaces on another
  (E-1001's department), and has one row without an employee ID.
- `sources.toml`: example source configuration. Copy it to `config/sources.toml`.

# Trust model

This page explains how Employee Knowledge treats the information it ingests: what an
assertion is, where it is stored, and how it becomes trusted.

## Assertions, not records

The system does not keep one editable record per employee. Every value a source supplies
is stored as a separate **assertion**: "source S says property P of employee E has value
V". Each assertion carries its evidence:

- the employee it is about, identified by employee ID and by who issued that ID;
- the property and the value, with surrounding spaces trimmed (and email addresses
  lowercased);
- the source it came from.

Each time a source is ingested, the run is recorded with its source, mapping version,
file name and file SHA-256, and its start and end times. For every value it reads, the
run records an **observation**: the source record (for Excel: workbook, sheet and row),
the exact source text before normalisation, the result of structural validation, and the
observation time if the source supplies one. The ingestion time is never recorded as an
observation time. Rows that cannot be used, for example rows without an employee ID, are
recorded with the reason.

Ingesting the same data again adds a new run and new observations but no new
assertions. Re-sorting a sheet changes nothing, because records are identified by
employee ID. When a value changes, the new value becomes a new assertion and the old one
stays.

Employee IDs issued by different systems are never merged, even when the IDs are
identical.

If two sources disagree, for example HR says *Engineering* and a directory says
*Product*, both assertions are kept. Ingesting a newer file never overwrites or deletes
what an older file said.

## Named graphs

| Graph | Contains |
|---|---|
| `urn:employee-knowledge:graph:untrusted` | Every newly ingested assertion. Nothing skips this step. |
| `urn:employee-knowledge:graph:trusted` | Assertions a reviewer has explicitly accepted. |
| `urn:employee-knowledge:graph:audit` | Review events: who decided, when and why. |
| `urn:employee-knowledge:graph:run:{id}` | One per ingestion run: the run, its observations and its unusable rows. |

Trust applies to one assertion at a time. Marking a source, workbook or connector as
trusted does not exist and is not planned.

## Review states

Every assertion has a review state. A new assertion is a **candidate**. Only an explicit
review action by a named reviewer, with a non-empty reason, changes the state:

| Action | Allowed from | Result |
|---|---|---|
| accept | candidate, needs evidence, superseded | accepted |
| reject | candidate, needs evidence, accepted | rejected |
| request evidence | candidate | needs evidence |
| supersede | accepted | superseded |
| reopen | rejected | candidate |

Every action is recorded in the audit graph as an event: who, why, when, the state
before and after, and the version of the authority policy in force (`none` when there
is none; see below).
Events are never edited or deleted; the current state is the result of the latest one.
The audit graph is the only record of trust. Accepted assertions are placed in the
trusted graph and every other state in the untrusted graph, and both graphs can be
rebuilt from the audit graph at any time.

Re-ingesting a source never changes a state. An accepted value seen again stays
accepted. A value that a source no longer contains also keeps its state.

Reviewing one assertion leaves competing assertions for the same employee and property
untouched, so the disagreement stays visible. Two conflicting values can both be
accepted; the system points this out but never picks one.

Automated tools and AI assistants may suggest mappings, compare values or explain a
discrepancy. They never review an assertion on their own.

Validation is separate from trust. A value can be well-formed and still wrong. Passing
validation does not make an assertion trusted.

## Authority policy

No source is trusted wholesale. Which source to believe is decided per property, in an
authority policy that the data owner approves. Each policy row names, for one property:

- the authoritative sources, and any acceptable secondary sources;
- a freshness window in days;
- whether every employee must have the property;
- the reviewer roles permitted to review it; and
- a conflict rule: `manual` (a reviewer chooses) or `prefer-authoritative`.

For each discrepancy, the report shows what the policy recommends:

| Outcome | Meaning |
|---|---|
| no policy | No policy is in force, or it has no row for the property. The conflict stays unresolved. |
| manual | The policy leaves the choice to a reviewer. |
| recommend | Exactly one value comes from the authoritative sources. The report names its source; `report-json` lists its assertions. |
| unresolved | The authoritative sources assert no value, or more than one. |

Rejected and superseded values are not counted, because someone has already set them
aside. A recommended value that the latest ingestion no longer contained is still
counted, and the report says so.

A recommendation changes nothing. The value stays a candidate until a reviewer accepts
it, with a reason, like any other. No policy setting can turn review off. Each review
event records the version of the policy in force at the time.

A policy is in force from its `effective_from` date. Until then, it is treated as
absent.

## Discrepancies

The report lists every employee and property for which more than one distinct value
has been asserted, whatever their review state. It shows each value with its source, its
review state and every place it was observed. It also flags:

- conflicting values that are both accepted;
- values the latest ingestion of their source no longer contained;
- values that failed structural validation;
- rows that the latest ingestion of each source could not use.

A value missing from the latest run keeps its review state: absence is evidence to
review, not a deletion. The report never chooses a winner.

## Current limitations

- The reviewer name is a free-text local label. It does not authenticate anyone and must
  not be relied on as access control.
- The reviewer roles in the authority policy are not checked. They tell people who
  should review a property; they do not stop anyone else.
- Values are compared exactly as written, after trimming surrounding whitespace, so
  differences in letter case count as discrepancies. Work email addresses are the
  exception: they are lowercased first.
- Unusable rows are reported for the latest run of each source only. Earlier runs keep
  them in their run graphs.

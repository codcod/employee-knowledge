# ADR-0003: Assertion identity, observations and ingestion runs

- **Status:** Accepted (2026-11-17)
- **Related:** ADR-0001, ADR-0002, ADR-0004, ADR-0007

## Context

Re-ingestion must be idempotent, and changed data must not erase evidence (architecture
§5.2, Task-008). The old assertion ID hashed `source + "Sheet:row" + predicate + value`.
Problems with that:

- Sorting a workbook changed every ID.
- Re-ingesting piled up `observedAt` values on the same assertion.
- An employee removed from a source stayed asserted with no sign that it had gone.
- When the source gave no timestamp, ingestion time was stored as observation time,
  which is fabricated provenance.

## Decision

### Assertion identity

```
assertion id = sha256( source_id ␟ record_key ␟ predicate IRI ␟ datatype IRI ␟ normalised value )
```

- `␟` is the U+001F unit separator character.
- `record_key` is the source's stable key for the record. For employee-ID sources
  (everything today) it is the employee ID as it appears in the source, trimmed. Row
  numbers are never part of identity.
- The normalised value follows ADR-0008. Changing the rule changes IDs, so it needs its
  own ADR and a migration.

So: the same value seen again gives the same assertion. A changed value gives a new
assertion, and the old one stays.

### Ingestion runs and run graphs

Each ingestion run gets an ID (`uuid4`) and its own named graph,
`urn:employee-knowledge:graph:run:{uuid}`, which holds:

```turtle
<urn:employee-knowledge:run:{uuid}> a ek:IngestionRun, prov:Activity ;
    ek:forSource       <urn:employee-knowledge:source:{source-id}> ;
    ek:mappingVersion  "1" ;
    prov:used          [ a prov:Entity ; ek:fileName "employees.xlsx" ; ek:sha256 "…" ] ;
    prov:startedAtTime "…"^^xsd:dateTime ;
    prov:endedAtTime   "…"^^xsd:dateTime ;
    ek:runStatus       ek:Completed .

<urn:employee-knowledge:observation:{sha256(run ␟ assertion ␟ source reference)}>
    a ek:Observation, prov:Entity ;
    ek:ofAssertion        <assertion> ;
    prov:wasGeneratedBy   <run> ;
    ek:sourceRecordKey    "E-1001" ;
    ek:sourceReference    "employees.xlsx#Employees!2" ;
    ek:rawValue           " Engineering " ;   # exact source text before normalisation
    ek:observedAt         "…"^^xsd:dateTime ; # only when the source supplies it
    ek:validationResult   ek:Conforms .       # ADR-0006

[] a ek:QuarantinedRecord ;                   # rows that could not become assertions
    prov:wasGeneratedBy <run> ;
    ek:sourceReference  "employees.xlsx#Employees!7" ;
    ek:quarantineReason "missing employee ID" .
```

- A run graph is never changed after its run completes.
- Ingestion time is the run's `prov:startedAtTime`/`prov:endedAtTime`. `ek:observedAt` is
  written only when the source supplies an observation time. It is never defaulted.
- `ek:runStatus ek:Completed` is written last. The whole store is saved atomically
  (ADR-0005), so a failed run is never stored. The status is still checked, so a later
  incremental store stays safe.
- Ingesting the same file twice gives two runs that observe the same assertions. Runs are
  events; assertions do not repeat.
- If one record key appears twice in a file, both rows are observed. If their values
  differ, the source contradicts itself, and the report shows that conflict.

### Not observed any more

An assertion counts as **not observed** when the latest completed run of its source has no
observation of it. This is computed at report time and never stored. It never changes
trust state (ADR-0002). Absence is never treated as deletion (architecture §4.2).

## Alternatives considered

- **Keep the row in the identity.** Not stable; reordering creates false new assertions.
  Rejected.
- **Exclude the value from the identity** (one assertion per source, record and
  property, value overwritten). Overwrites evidence. Rejected.
- **Observations on the assertion, in the trust graphs.** They would have to move with
  every review, and runs would have no single home. Rejected in favour of run graphs.
- **One standing provenance graph.** Workable, but it adds a fourth fixed graph, and an
  incomplete run is harder to isolate. Rejected.

## Consequences

- Re-ingesting unchanged data adds one run graph and one observation per assertion, and
  creates no new assertions.
- The store grows with every run. Retention for run graphs is an open question
  (architecture §13, question 8).
- Full history of what each run saw is available for reconciliation (architecture §4.6,
  "unexpected changes between runs").

## Migration

Only synthetic local stores exist. Delete them and re-ingest.

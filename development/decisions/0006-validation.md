# ADR-0006: Structural validation with SHACL

- **Status:** Accepted (2026-11-18). First approved 2026-11-17.
- **Related:** ADR-0001, ADR-0003

## Context

Structural validity is separate from factual correctness and from trust (architecture
§3.4, §4.4). The old `shapes.ttl` targeted `ek:Employee` with `ek:fullName`/`ek:workEmail`,
which the code never writes. pyshacl was never run. Its `maxCount 1` on names also clashed
with keeping multiple sources' values.

Two kinds of failure need different handling:

- **Source data problems:** a value of the wrong datatype, or a missing required field.
  These are the source's fault and must stay visible.
- **Model problems:** an assertion without an employee, or an observation without a run.
  These are a bug in this system.

## Decision

`src/ek/ontology/shapes.ttl` defines two groups of shapes.

**Model shapes** (one per class, `sh:targetClass`):

- `ek:FactAssertion`: exactly one each of `ek:aboutEmployee` (class `ek:Employee`),
  `ek:predicate` (class `ek:AssertableProperty`), `ek:value` and `ek:fromSource`.
- `ek:Observation`: exactly one each of `ek:ofAssertion`, `prov:wasGeneratedBy`,
  `ek:sourceReference` and `ek:rawValue`; at most one `ek:observedAt`
  (`xsd:dateTime`).
- `ek:IngestionRun`: exactly one each of `ek:forSource`, `ek:mappingVersion`,
  `prov:startedAtTime` and `prov:used`.
- `ek:ReviewEvent`: exactly one each of `prov:used`, `ek:reviewAction`, `ek:fromState`,
  `ek:toState`, `ek:reviewer` (non-empty), `ek:reviewReason` (non-empty) and
  `ek:sequence`.
- `ek:Employee`: exactly one each of `ek:employeeId` and `ek:issuer`.
- `ek:QuarantinedRecord`: exactly one each of `prov:wasGeneratedBy`,
  `ek:sourceReference` and `ek:quarantineReason`.
- The run's source file (through `prov:used`): exactly one `ek:fileName` and one
  `ek:sha256` (64 lowercase hex characters).

**Value shapes** (node shapes also typed `ek:ValueShape`): for now there is one,
`ek:AssertionValueShape`. It targets every `ek:FactAssertion` and uses a core SHACL
SPARQL constraint to require that `ek:value` be a non-blank literal whose datatype is the
`rdfs:range` of its `ek:predicate`. A new assertable property is therefore checked as soon
as the ontology declares its range. No shape edit is needed.

Add a property-specific value shape only when a real rule exists for that property. No
value constraints go beyond datatype and non-blank. Formats (email
patterns), controlled vocabularies (employment status) and required attributes are
business rules, and they wait for the data owner (architecture §13, questions 2 and 11).

**When validation runs.** At the end of each ingestion run, before saving, validate the
run graph together with the assertions it observed.

- A model-shape violation aborts the run. Nothing is saved, and the error is reported.
- A value-shape violation is recorded on the observation:
  `ek:validationResult ek:Violation` plus `ek:validationMessage`. The assertion is still
  stored, still untrusted, and appears in the report. Conforming observations get
  `ek:validationResult ek:Conforms`.
- Review actions validate the new event before saving and refuse to save on violation.

Validation never changes trust state.

## Alternatives considered

- **Shapes on a projected employee view.** Validates a derived view instead of the
  stored data. Multiple sources legitimately conflict there, so cardinality rules would
  misfire. Rejected.
- **One value shape per property, each selected by a SPARQL target.** This was the
  first draft of this ADR. It makes near-identical copies of the same rule and needs a
  shape edit for every new property. Superseded by the generic constraint, with
  per-property shapes kept for property-specific rules (decided 2026-11-17).
- **One assertion shape with `sh:or` over every property.** Error messages don't say
  which property failed, and every new property means editing one large shape. Rejected.
- **Validation in Python.** Simpler, but it departs from the SHACL choice in the
  architecture and AGENTS.md, and the rules would not be declarative. Rejected.

## Consequences

- The validator (`ek/validation.py`) merges the ontology into a copy of the data graph,
  because the class checks and the range lookup need it. pyshacl does not do this
  without inferencing. No SHACL advanced features are used.
- Findings are classified by shape: a violation from a shape typed `ek:ValueShape` is a
  value finding; anything else is a model finding.
- A new assertable property needs only its ontology entry with `rdfs:range`.
- Validation cost grows with run size. Fine at prototype scale.

## Migration

None. The old shapes are replaced.

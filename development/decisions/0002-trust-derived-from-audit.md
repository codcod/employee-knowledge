# ADR-0002: Trust state derived from the audit trail

- **Status:** Accepted (2026-11-17)
- **Supersedes:** ADR-002 (one-line entry)
- **Related:** ADR-0001, ADR-0003

## Context

Trust is per assertion and changes only through an explicit, authorised review action
with a reason (architecture §3.3, §4.7). The code recorded trust twice: through graph
membership (moving triples to the trusted graph) and through an `ek:reviewStatus`
literal. The two already disagree. After promote and then re-ingest, one assertion sat in
both graphs, marked `"untrusted"` in one and `"trusted"` in the other. There was also no
place for rejected, superseded or needs-evidence assertions.

## Decision

**The audit graph is the only record of trust state.** Graph membership is a projection
of it.

### Review events

Each review action writes one event to `urn:employee-knowledge:graph:audit`:

```turtle
<urn:employee-knowledge:review:{uuid}> a ek:ReviewEvent, prov:Activity ;
    prov:used        <assertion> ;
    ek:reviewAction  ek:Accept ;
    ek:fromState     ek:Candidate ;
    ek:toState       ek:Accepted ;
    ek:reviewer      "local-label" ;          # a label, not authentication
    ek:reviewReason  "Checked against HR" ;
    ek:policyVersion "none" ;                 # or the policy in force (ADR-0010)
    ek:sequence      42 ;                     # store-wide, strictly increasing
    prov:endedAtTime "…"^^xsd:dateTime ;
    ek:supersededBy  <other-assertion> .      # optional, only on supersede
```

Events are append-only. They are never edited or deleted. `ek:sequence` orders events
reliably even when two share a timestamp.

### States and transitions

An assertion's state is the `ek:toState` of its latest event. With no events, it is
`ek:Candidate`.

| Action | From | To |
|---|---|---|
| accept | candidate, needs-evidence | accepted |
| accept (restore) | superseded | accepted |
| reject | candidate, needs-evidence | rejected |
| reject (revoke) | accepted | rejected |
| request-evidence | candidate | needs-evidence |
| supersede | accepted | superseded |
| reopen | rejected | candidate |

All other transitions are refused. Every action needs a non-blank reviewer label and a
non-blank reason. `ek:supersededBy` must name an existing assertion about the same
employee and property (decided 2026-11-18).

### Projection

- `urn:employee-knowledge:graph:trusted` holds the assertions whose state is
  `accepted`, plus the identity triples of their employees.
- `urn:employee-knowledge:graph:untrusted` holds every other assertion (candidate,
  needs-evidence, rejected, superseded), plus their employees' identity triples.
- A review action updates the projection for that assertion, in the same save as the
  event.
- `rebuild-projection` recomputes both graphs from the audit graph. A consistency check
  reports any assertion whose graph does not match its derived state.
- Ingestion adds an assertion to the untrusted graph **only if it is in neither graph**.
  Re-observing an accepted assertion leaves it accepted.

### What is never automatic

- No state changes without a review event: not on re-ingestion, not when a value stops
  being observed, not because a policy matches.
- An accepted assertion that is no longer observed stays accepted. The report flags it
  for review (ADR-0003).
- Two conflicting assertions may both be accepted. The report flags it. Nothing picks
  one.

## Alternatives considered

- **Graph membership as the record.** Moves are destructive and leave no reason or
  history in the data itself. Rejected.
- **A mutable status literal on the assertion.** Breaks assertion immutability and
  duplicates the audit trail. Rejected.
- **Untrusted graph holds everything, trusted holds copies.** Simpler writes, but
  "untrusted" would then contain trusted facts, which contradicts the graph names in
  AGENTS.md. Rejected.

## Consequences

- Trust state is fully explainable: every state has an event with actor, reason, time and
  policy version.
- The projection can be wrong only through a bug, and the consistency check detects that.
- Reviewer labels are not authorisation (architecture §2, §4.7). Production needs real
  identity and roles before real data is connected.
- CLI: `promote` becomes `review accept`. New actions: `reject`, `request-evidence`,
  `supersede`, `reopen`. `rebuild-projection` is added.

## Migration

Old audit events (a bare `prov:Activity` with a reason) have no action or states. Only
synthetic local stores exist, so delete and re-ingest.

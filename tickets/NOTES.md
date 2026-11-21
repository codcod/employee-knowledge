# Notes

Hand-written planning notes live here — triage records, parked-ticket notes,
cross-ticket decisions, dependency rationale. `BOARD.md` is generated from the
ticket files (run `pickle board sync`), so nothing hand-written survives there.

## Pending external checks

- 2026-11-19 (EK-002): after perma-id/w3id.org merges
  https://github.com/perma-id/w3id.org/pull/7252 (replaces #7232, closed 2026-11-21 after a bad
  force-push; adds the maintainer README),
  `curl -sIL https://w3id.org/employee-knowledge/ontology` must end at the TTL with 200.

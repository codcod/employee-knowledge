# ADR-0009: Ontology namespace

- **Status:** Accepted (2026-11-18)
- **Related:** ADR-0001

## Context

The ontology used an `example.org` placeholder namespace (architecture §13, question 14).
The earlier answer, a company-owned domain, would tie a generic, openly licensed project to
one organisation. Every term IRI is stored in every assertion (ADR-0001), so the namespace
has to be fixed before IRIs are published or real data is stored.

## Decision

- The namespace is `https://w3id.org/employee-knowledge/ontology#`. The ontology IRI is
  `https://w3id.org/employee-knowledge/ontology`. Local names are unchanged.
- The ontology version becomes `0.3.0`: every term IRI changed.
- Instance IRIs (`urn:employee-knowledge:{assertion,employee,file,graph,observation,
  quarantine,review,run,source}:…`) are unchanged. They are internal identifiers, never
  published for dereferencing, and the URN namespace is not registered.
- `ek.constants.EK` and `src/ek/ontology/*.ttl` must name the same namespace; a test
  checks it.

## Alternatives considered

- **Company domain.** Ties the generic project to one organisation. Rejected.
- **A project-owned domain.** Lapses if the domain is not renewed. Rejected in favour of
  w3id.org, which is a persistent-ID service.
- **Slash IRIs.** A needless change of style; the hash form is kept.
- **Move the URN instance IRIs too.** About 65 uses, another rebuild, and no external
  consumer needs them. Deferred, not rejected; it would need its own ADR.

## Consequences

- The project owner registers the `employee-knowledge` redirect with w3id.org (a pull
  request to perma-id/w3id.org) before IRIs are published. Until then the IRIs are
  identifiers only and do not resolve.
- Any query or consumer built against the placeholder namespace stops matching.

## Migration

All term IRIs change. Only synthetic local stores exist, so delete them and re-ingest.
There is no migration code.

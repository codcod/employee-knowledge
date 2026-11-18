from urllib.parse import quote

from rdflib import URIRef


def employee_uri(issuer: str, employee_id: str) -> URIRef:
    """Canonical employee URI (ADR-0004). IDs from different issuers never merge."""
    issuer, cleaned = str(issuer).strip(), str(employee_id).strip()
    if not issuer or not cleaned:
        raise ValueError("issuer and employee_id must not be empty")
    return URIRef(
        f"urn:employee-knowledge:employee:{quote(issuer, safe='')}:"
        + quote(cleaned, safe="")
    )


def source_uri(source_id: str) -> URIRef:
    return URIRef("urn:employee-knowledge:source:" + quote(source_id, safe=""))

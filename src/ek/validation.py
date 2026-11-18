"""Structural validation with SHACL (ADR-0006).

Model findings mean this system wrote a malformed record (a bug); callers abort.
Value findings mean the source supplied bad data; callers record them and keep the
assertion. Validation never changes trust state.
"""

import functools
import typing as tp
from dataclasses import dataclass
from pathlib import Path

from pyshacl import validate as shacl_validate
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS, SH

from .constants import EK

# ponytail: resolves ontology/ from the source tree; works for editable installs only.
# Package the .ttl files as package data when the project is distributed as a wheel.
ONTOLOGY_DIR = Path(__file__).resolve().parents[2] / "ontology"

FindingKind = tp.Literal["model", "value"]


@dataclass(frozen=True)
class Finding:
    kind: FindingKind
    focus: str
    path: str | None
    message: str
    shape: str


@functools.cache
def _load(name: str) -> Graph:
    return Graph().parse(ONTOLOGY_DIR / name, format="turtle")


def property_range(predicate: URIRef) -> URIRef:
    """The datatype an assertable property's value must have (its rdfs:range)."""
    datatype = _load("employees.ttl").value(predicate, RDFS.range)
    if datatype is None:
        raise ValueError(f"{predicate} has no rdfs:range in the ontology")
    return URIRef(datatype)


def validate(data: Graph) -> list[Finding]:
    """Validate ``data`` against the ontology shapes and return all findings."""
    shapes, ontology = _load("shapes.ttl"), _load("employees.ttl")
    # The ontology supplies class memberships (e.g. ek:department a
    # ek:AssertableProperty) and rdfs:range for the value check. pyshacl only mixes
    # ont_graph in when inferencing, so merge explicitly; ``data`` is not modified.
    _, results, _ = shacl_validate(
        data + ontology, shacl_graph=shapes, inference="none", allow_warnings=False
    )
    findings = []
    for result in results.subjects(RDF.type, SH.ValidationResult):
        source = results.value(result, SH.sourceShape)
        node_shape = shapes.value(predicate=SH.property, object=source) or source
        kind: FindingKind = (
            "value" if (node_shape, RDF.type, EK.ValueShape) in shapes else "model"
        )
        path = results.value(result, SH.resultPath)
        findings.append(
            Finding(
                kind=kind,
                focus=str(results.value(result, SH.focusNode)),
                path=str(path) if path is not None else None,
                message=str(results.value(result, SH.resultMessage)),
                shape=str(node_shape),
            )
        )
    return sorted(findings, key=lambda f: (f.kind, f.focus, f.path or "", f.message))

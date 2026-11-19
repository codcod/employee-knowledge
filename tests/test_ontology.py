from importlib.resources import files

from rdflib import Graph, URIRef
from rdflib.namespace import RDFS

from ek.constants import EK


def test_every_term_has_one_label_and_a_definition():
    """EK-001: every ek: term is defined, so the vocabulary can be reviewed."""
    ttl = (files("ek") / "ontology" / "employees.ttl").read_text(encoding="utf-8")
    g = Graph().parse(data=ttl, format="turtle")
    terms = {s for s in g.subjects() if isinstance(s, URIRef) and str(s).startswith(EK)}
    assert terms
    bad = sorted(
        str(t)[len(EK) :]
        for t in terms
        if len(list(g.objects(t, RDFS.label))) != 1
        or not any(str(c).strip() for c in g.objects(t, RDFS.comment))
    )
    assert bad == [], f"terms without exactly one label and a comment: {bad}"

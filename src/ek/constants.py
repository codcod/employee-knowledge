from rdflib import Namespace, URIRef

EK = Namespace("https://w3id.org/employee-knowledge/ontology#")
TRUSTED_GRAPH = URIRef("urn:employee-knowledge:graph:trusted")
UNTRUSTED_GRAPH = URIRef("urn:employee-knowledge:graph:untrusted")
AUDIT_GRAPH = URIRef("urn:employee-knowledge:graph:audit")

# Configuration field name -> assertable property (src/ek/ontology/employees.ttl).
FIELD_PREDICATES = {
    "full_name": EK.fullName,
    "work_email": EK.workEmail,
    "department": EK.department,
    "job_title": EK.jobTitle,
    "manager_employee_id": EK.managerEmployeeId,
    "location": EK.location,
    "employment_status": EK.employmentStatus,
}

RUN_GRAPH_PREFIX = "urn:employee-knowledge:graph:run:"

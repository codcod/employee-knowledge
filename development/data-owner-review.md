# Data-owner review

Prepared for: the employee-data owner. Prepared by: the project owner (EK-001, 2026-11-19).

## Purpose and how to answer

Employee Knowledge collects what different systems say about employees, keeps track of
where each value came from, and only treats a value as trusted after a person has reviewed
it. Some decisions about that are yours to make, and this document collects them in one
place. For each question, either write an answer, or defer it by naming who decides and by
when. Answer with policy only. Never include real employee records or real examples,
because the filled-in copy will be read in an AI-assisted session. Return the filled-in
copy to the project owner.

## Open questions

### Q1 — Employee ID across rehire

> Which system issues the canonical employee ID, and does it remain stable across
> rehire or legal-entity changes?

The HR system issues the ID (already decided). Still open: does a person keep the same ID
when they are rehired, or when they move to another legal entity?

- **Why it matters:** the employee ID is the only key used to link records about the same
  person. If it changes on rehire, one person shows up as two employees, and nothing links
  them automatically.
- **Today's default:** each ID is a separate employee. Records are never merged on name,
  department or title, and ambiguous matches are left unresolved
  ([ADR-0004](decisions/0004-employee-identity.md)).
- **Needed by:** ADR-0004, and EK-003 (unresolved-identity findings).

Answer:

Or defer — who decides, by when:

### Q2 — Attribute scope

> Which employee attributes are in the initial business scope, and which are explicitly
> excluded?

- **Why it matters:** each attribute needs a defined purpose before it is collected
  (architecture §8). This scope also determines which attributes count as required when
  data quality is checked.
- **Today's default:** seven attributes, provisionally. These are full name, work email,
  department, job title, manager employee ID, work location and employment status. No
  sensitive attributes are collected, and none is required yet.
- **Needed by:** the ontology scope (architecture §4.4), and EK-003 (required-field
  findings).

Answer:

Or defer — who decides, by when:

### Q5 — Reviewers and evidence

> Who is allowed to review/promote facts, and what evidence is required for each
> property?

- **Why it matters:** a value becomes trusted only through a review. Who may review, and
  what evidence they need, decides what "trusted" means.
- **Today's default:** anyone running the local tool can review. The reviewer name is a
  label, not access control (architecture §4.7). Every review needs a reason, and no
  property requires specific evidence.
- **Needed by:** EK-004 (source-authority policy), and EK-003 (freshness windows).

Answer:

Or defer — who decides, by when:

### Q6 — AI-provider limits

> Which employee data may be sent to an AI provider, under what controls, and which
> fields must never leave the controlled environment?

- **Why it matters:** natural-language questions over the data would need an AI model to
  see at least the vocabulary, and possibly values.
- **Today's default:** no employee data is sent to any AI provider. Development uses
  synthetic data only (architecture §8).
- **Needed by:** EK-006 (natural-language-to-SPARQL).

Answer:

Or defer — who decides, by when:

### Q7 — Production store and environment

> What is the intended production graph store and deployment environment?

- **Why it matters:** it decides how access control, encryption and concurrent use are
  provided.
- **Today's default:** a single local file with one writer at a time, suitable for the
  prototype only ([ADR-0005](decisions/0005-storage.md)).
- **Needed by:** ADR-0005. No ticket yet.

Answer:

Or defer — who decides, by when:

### Q8 — Retention and data-subject obligations

> What retention, correction, deletion and access-request obligations apply?

- **Why it matters:** the system keeps every value it has seen, together with where it
  came from. Retention and deletion rules must be designed in before real data arrives.
- **Today's default:** none is defined. No real data is ingested.
- **Needed by:** EK-010 (operational controls).

Answer:

Or defer — who decides, by when:

### Q9 — Connector scope

> Which Confluence spaces, Jira projects and Power BI workspaces are in scope, and who
> owns access approval?

- **Why it matters:** each connector reads only what is explicitly allowed, through a
  read-only account that someone must approve.
- **Today's default:** connector access is disabled. Only Excel files are read.
- **Needed by:** EK-007 (Confluence), EK-008 (Jira), EK-009 (Power BI), and EK-010
  (access approval).

Answer:

Or defer — who decides, by when:

### Q10 — First business questions

> Which business questions must the first trusted query interface answer?

- **Why it matters:** the first query interface is built around named questions rather
  than open-ended queries.
- **Today's default:** a command-line report of values, conflicts and trust status
  (architecture §4.8).
- **Needed by:** EK-005 (trusted query interfaces).

Answer:

Or defer — who decides, by when:

## Decisions to confirm

The project owner made these decisions on 2026-11-18. Confirm them, or correct them.

| question | decided (2026-11-18) | confirm / correct |
|---|---|---|
| Q1: who issues the employee ID | The HR system issues it. | |
| Q3: which system owns each attribute | No source is authoritative until a versioned policy exists. Every fact needs a review. | |
| Q4: history and timestamps | Current state only. Each ingestion run keeps what it saw, and effective dates wait until a source provides them. An observation time is recorded only when the source supplies it, never as the time of ingestion. | |
| Q11: normalising values | Surrounding whitespace is trimmed, `work_email` is lowercased, and values are compared exactly. Controlled vocabularies, such as employment status, wait for the allowed values. | |
| Q12: employee ID format in Excel | A whole-number cell is read as its digits. Decimals, dates and booleans are quarantined. Leading zeros in numeric cells are lost, so ID columns should be text. The ID format itself is still unknown. | |
| Q13: who issues IDs in each source | An issuer is configured per source (the HR system for HR-keyed sources). IDs from different issuers are never merged automatically. | |
| Q15: how the manager is recorded | As a manager employee ID, exactly as the source states it. A later check resolves it to an employee and reports references that do not resolve. | |

## Business terms to confirm

These are the definitions the system uses. Confirm each one, or correct it. The source
field is the column name used in an Excel mapping.

| term | source field | definition | confirm / correct |
|---|---|---|---|
| `ek:Employee` | — | A person identified by an employee ID from one issuer. Carries identity only; everything a source says about the person is an ek:FactAssertion. | |
| `ek:employeeId` | `employee_id` | The employee identifier exactly as issued, trimmed. Unique only together with ek:issuer. | |
| `ek:issuer` | — | Who issues the employee ID, as configured per source. IDs from different issuers are never merged automatically. | |
| `ek:fullName` | `full_name` | The person's full or display name as the source records it. Never an identifier. | |
| `ek:workEmail` | `work_email` | Work email address as the source records it, trimmed and lowercased before comparison (ADR-0008). | |
| `ek:department` | `department` | Department or organisational unit as the source names it. | |
| `ek:jobTitle` | `job_title` | Job title as the source records it. | |
| `ek:managerEmployeeId` | `manager_employee_id` | Employee ID of the person's manager as the source states it, from the same issuer as the record. To be resolved to an employee, with broken references reported, by data-quality checks (Task-010; architecture §13, question 15). | |
| `ek:location` | `location` | Work location as the source records it (office, city or 'Remote'). | |
| `ek:employmentStatus` | `employment_status` | Employment status as the source records it. No controlled vocabulary yet (architecture §13, question 11). | |

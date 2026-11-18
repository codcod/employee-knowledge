---
id: EK-011
title: Package the ontology so ek installs as a regular dependency
project: employee-knowledge
depends-on: []
spawned-by: []
impact: high
complexity: low
cost: S
---

# EK-011 — Package the ontology so ek installs as a regular dependency

## Outcome

After this ships, `employee-knowledge` installed from a wheel or a git tag ingests and validates like the editable checkout does, so another package can declare it as a regular dependency instead of an editable path.

## Description

`src/ek/validation.py` resolves the ontology from the source tree (`ONTOLOGY_DIR = Path(__file__).resolve().parents[2] / "ontology"`, marked with a `ponytail:` comment). The built wheel contains only `ek/*.py`, so in a non-editable install `_load()` fails and every ingestion fails with it, because `ek.ingest` always calls `validate()` and `property_range()`. The data that has to ship is `employees.ttl` and `shapes.ttl`.

Fix: move `ontology/` to `src/ek/ontology/` (still the single, hand-edited copy), declare it as setuptools package data, and load it with `importlib.resources`. Nothing else reads the directory: the code reaches it only through `validation._load`, and tests reach it only through the validator. Prose that names the old path: `AGENTS.md` (ontology-first invariant), `development/architecture.md` §10, ADR-0001 (line 44), ADR-0006 (line 22) and the comment in `src/ek/constants.py`.

Found while wiring the closed corporate example, which depends on ek as a package and has to use an editable path dependency until this lands. Soft couplings: EK-012 (same downstream consumers), EK-013 (edits the same `.ttl` files to change the namespace; whichever lands second rebases onto the moved path).

Acceptance: a test builds the wheel and runs one ingestion, validation included, from the built package rather than the source tree; the editable install and the existing suite keep working.

## Implementation Plan

### 0. Feature branch (mandatory)

```
cd /Users/nka/Projects/codcod/employee-knowledge   # child employee-knowledge, path "."
git checkout main
git checkout -b feat/EK-011-package-ontology
```

Work and commit locally on this branch. In-tree layout: ticket and board bookkeeping is committed on `main`, never on this branch. No push and no merge request without explicit user approval; merging is the human's. Before pushing (after approval), `git fetch origin main && git diff --name-only origin/main...HEAD | grep '^tickets/'` must print nothing (skip if there is still no remote).

### Prerequisite gate (hard)

None. `depends-on: []`; clean tree on `main`. If EK-013 has merged first, its namespace change is already in `ontology/*.ttl`; move the files as they are.

### Confirmed design decisions (do not deviate without asking)

1. **The ontology moves to `src/ek/ontology/` with `git mv`.** It stays the single hand-edited copy; there is no build-time copy, no symlink and no build hook. (Chosen 2026-11-18 over keeping `ontology/` at the root plus a copy step.)
2. **Load through `importlib.resources`.** `importlib.resources.files("ek") / "ontology" / name`, read as text and parsed with `Graph().parse(data=..., format="turtle")`. No `Path(__file__)` arithmetic, no `pkg_resources`, no new dependency.
3. **Package data is declared explicitly in `pyproject.toml`.** `[tool.setuptools.package-data] ek = ["ontology/*.ttl"]`, so both the wheel and the sdist include it without a `MANIFEST.in`.
4. **The ontology files are unchanged.** Only their location changes: no new terms, no namespace edit (that is EK-013).
5. **The acceptance test builds a real wheel and runs from it.** `uv build --wheel` into `tmp_path`, extract it, then run one ingestion in a subprocess with the extracted directory first on `sys.path`, with dependencies coming from the current venv. It needs no network once uv's cache holds the setuptools build backend (CI downloads it), and it is not skipped by default; it fails if `uv` is missing, because CI has it. (Chosen 2026-11-18 over a fresh-venv install, which needs the network, and over a wheel-contents check, which never executes the package.)
6. **No ADR.** It is a file location, not an architectural change: architecture §10 and the ADR path mentions are edited in place (decided 2026-11-18).
7. **Remove the `ponytail:` comment.** Its ceiling is the subject of this ticket.

### Tasks

#### Task 1 — Move the ontology into the package
- `git mv ontology src/ek/ontology`.
- `pyproject.toml`: add `[tool.setuptools.package-data]` with `ek = ["ontology/*.ttl"]`.
- `.gitignore`: add `build/` and `dist/`. `uv build` writes `build/` into the source tree; this was observed during refinement.

#### Task 2 — Load with `importlib.resources`
In `src/ek/validation.py`: delete `ONTOLOGY_DIR`, its `ponytail:` comment and the `Path` import if it is now unused. `_load(name)` becomes `Graph().parse(data=(files("ek") / "ontology" / name).read_text(encoding="utf-8"), format="turtle")`. Keep `@functools.cache`. Update the comment in `src/ek/constants.py` line 8 to `src/ek/ontology/employees.ttl`.

#### Task 3 — Wheel acceptance test
New `tests/test_packaging.py` (synthetic examples only):
- Build from a clean copy, not the repo root: a stale `build/lib` or `src/*.egg-info` in a dev tree makes setuptools reuse old files, so the test passes even with the package-data entry removed (reproduced at the applicability gate). Copy `pyproject.toml`, `README.md` and `src/` (ignoring `*.egg-info` and `__pycache__`) into a `tmp_path_factory` directory and run `uv build --wheel --out-dir <tmp>` there. This also keeps the test from writing `build/` into the repo.
- `test_wheel_contains_ontology`: run that build (`subprocess.run(..., check=True)`), open the single `.whl` with `zipfile`, and assert that `ek/ontology/employees.ttl` and `ek/ontology/shapes.ttl` are present.
- `test_ingests_from_built_wheel`: extract that wheel into `tmp_path / "site"`, then run `sys.executable -c <script>` with `cwd=tmp_path` and `EMPLOYEE_KNOWLEDGE_STORE=tmp_path/"store.trig"`. The script runs `sys.path.insert(0, site)`, imports `ek`, asserts `Path(ek.__file__).resolve().is_relative_to(site.resolve())` (resolved on both sides, because macOS `/private/tmp` symlinks break a plain prefix check) (proving it is not the editable source tree), and then invokes `ek.cli.app` through `typer.testing.CliRunner` with `ingest-excel <repo>/examples/employees.xlsx --source-id hr-export --config <repo>/examples/sources.toml`, asserting exit code 0. The test then asserts the subprocess succeeded and that the store file exists and is not empty.
- Share the built wheel between the two tests with a module-scoped fixture (`tmp_path_factory`), so the wheel is built once.

#### Task 4 — Prose paths
Replace `ontology/employees.ttl` and `ontology/shapes.ttl` with `src/ek/ontology/…` in `AGENTS.md` §3 (ontology-first), `development/architecture.md` §10 (move the `ontology/` node under `src/ek/` in the tree), `development/decisions/0001-assertion-model.md:44` and `development/decisions/0006-validation.md:22`. Then run `grep -rn "ontology/" --exclude-dir=.venv --exclude-dir=tickets .` and confirm that every remaining hit is the new path or a generic phrase such as "ontology/SHACL".

### Acceptance test

```
uv run pytest tests/test_packaging.py -v   # both tests pass
uv run pytest                               # whole suite green (editable install still works)
uv run ruff check . && uv run ruff format --check .
test ! -e ontology && ls src/ek/ontology/employees.ttl src/ek/ontology/shapes.ttl
test -z "$(git status --porcelain build dist)"   # build output is ignored
```

Manual cross-check (optional): `uv build --wheel -o /tmp/ekw && unzip -l /tmp/ekw/*.whl | grep ttl` lists both files.

### Docs update (mandatory when user-facing)

No operator-facing behaviour changes, so `docs/` stays as it is; it does not mention the ontology path. Update the development docs and agent rules listed in Task 4. In `README.md`, add one line saying the package can be installed from a wheel or a git URL (e.g. `uv add "employee-knowledge @ git+<repo-url>@<tag>"`) only if the README already has an install section. Otherwise skip it.

### Finish (mandatory)

1. Acceptance test green; `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` clean.
2. Docs and path mentions updated (Task 4).
3. Write a summary: files moved and touched, the decisions above, and anything deferred (for example, publishing to an index is not part of this ticket).
4. Suggested commit message:

   ```
   build: ship the ontology as package data (EK-011)

   Move ontology/ to src/ek/ontology/, declare it as setuptools package data
   and load it with importlib.resources, so a wheel or git install validates
   and ingests like the editable checkout. Adds a test that builds the wheel
   and ingests from it.
   ```

5. Root-path child: tidy WIP commits into atomic ones (for example the `git mv` plus loader change, then the test, then the docs) before presenting them.
6. Commit locally on `feat/EK-011-package-ontology`; do not push. `pickle ticket move EK-011 in-review --reason "acceptance green"`.

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: found while checking adapter wiring for a downstream package
- 2026-11-18 — TO DO → READY: plan complete
- 2026-11-18 — plan amended inline: Task 3 builds the wheel from a clean temp copy (a stale build/ or egg-info made it pass falsely) and compares resolved paths; applicability gate found 6 non-blocking issues: 2 fixed inline, 1 absorbed by EK-013 (old ontology path in its description), 3 noted and closed
- 2026-11-18 — READY → IN DEVELOPMENT: picked up, branch feat/EK-011-package-ontology

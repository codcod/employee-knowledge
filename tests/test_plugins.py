"""EK-012: source kinds registered as entry points (ADR-0011). Synthetic data only."""

import hashlib
import os
import re
import subprocess
import sys
import types
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import EntryPoint
from pathlib import Path

import pytest
from rdflib import Dataset, URIRef
from rdflib.namespace import RDF
from typer.testing import CliRunner

from ek.adapters import registry
from ek.adapters.base import EmployeeRecord, ReadResult, SourceError
from ek.cli import app
from ek.config import ConfigError, SourceConfig, load_sources
from ek.constants import EK, TRUSTED_GRAPH, UNTRUSTED_GRAPH
from ek.graph.store import KnowledgeStore
from ek.ingest import ingest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
MAPPING = '[sources.mapping]\nemployee_id = "id"\nfull_name = "name"\n'


class FakePlugin:
    def parse_options(self, options, where):
        if unknown := set(options) - {"delimiter", "allowed_projects"}:
            raise ConfigError(f"{where}: unknown keys {sorted(unknown)}")
        return dict(options)

    def read(self, path, source):  # pragma: no cover - not read in unit tests
        raise NotImplementedError


@dataclass
class FakeEntryPoint:
    """A registered entry point bound to a distribution, which a hand-built
    EntryPoint is not (its dist is None)."""

    name: str
    value: str
    dist_name: str

    @property
    def dist(self):
        return types.SimpleNamespace(name=self.dist_name)

    def load(self):
        return EntryPoint(self.name, self.value, registry.GROUP).load()


@pytest.fixture
def register(monkeypatch):
    module = types.ModuleType("ek_fake_plugin")
    module.plugin = FakePlugin()
    monkeypatch.setitem(sys.modules, "ek_fake_plugin", module)
    eps: list[FakeEntryPoint] = []

    def entry_points(group):
        assert group == registry.GROUP
        return list(eps)

    monkeypatch.setattr(registry, "entry_points", entry_points)

    def add(name, value="ek_fake_plugin:plugin", dist="ek-fake"):
        eps.append(FakeEntryPoint(name, value, dist))

    return add


def load(tmp_path, text):
    path = tmp_path / "sources.toml"
    path.write_text(text, encoding="utf-8")
    return load_sources(path)


def source(kind, extra="", mapping=MAPPING):
    return (
        f'[[sources]]\nid = "s"\nkind = "{kind}"\nissuer = "example-hr"\n'
        f'mapping_version = "1"\n{extra}\n{mapping}'
    )


def test_plugin_kind_with_options_is_accepted(tmp_path, register):
    register("csv")
    s = load(tmp_path, source("csv", 'delimiter = ";"'))["s"]
    assert (s.kind, s.options, s.mapping["full_name"]) == (
        "csv",
        {"delimiter": ";"},
        "name",
    )


def test_unknown_option_is_refused(tmp_path, register):
    register("csv")
    with pytest.raises(ConfigError, match=r"unknown keys \['quote'\]"):
        load(tmp_path, source("csv", 'quote = "x"'))


def test_unknown_kind_is_refused(tmp_path, register):
    register("csv")
    with pytest.raises(ConfigError, match="unknown kind 'tsv'"):
        load(tmp_path, source("tsv"))


def test_duplicate_kind_names_both_distributions(tmp_path, register):
    register("csv", dist="ek-csv-a")
    register("csv", dist="ek-csv-b")
    with pytest.raises(
        ConfigError, match=r"registered twice: \['ek-csv-a', 'ek-csv-b'\]"
    ):
        load(tmp_path, source("csv"))


def test_import_failure_is_a_config_error(tmp_path, register):
    register("csv", value="ek_no_such_module:plugin")
    with pytest.raises(ConfigError) as exc:
        load(tmp_path, source("csv"))
    message = str(exc.value)
    assert "csv = ek_no_such_module:plugin" in message
    assert "ModuleNotFoundError" in message


def test_only_configured_kinds_are_loaded(tmp_path, register):
    register("csv")
    register("broken", value="ek_no_such_module:plugin")
    assert load(tmp_path, source("csv"))["s"].kind == "csv"


def test_plugin_overrides_placeholder_kind(tmp_path, register):
    register("jira")
    s = load(tmp_path, source("jira", "allowed_projects = []"))["s"]
    assert (s.enabled, s.options) == (True, {"allowed_projects": []})


def test_placeholder_without_plugin_must_stay_disabled(tmp_path, register):
    with pytest.raises(ConfigError, match="not implemented"):
        load(tmp_path, '[[sources]]\nid = "j"\nkind = "jira"\n')
    disabled = '[[sources]]\nid = "j"\nkind = "jira"\nenabled = false\n'
    assert not load(tmp_path, disabled)["j"].enabled


@pytest.mark.parametrize(
    ("extra", "mapping", "error"),
    [
        ("enabled = false", "", "employee_id"),
        ('enabled = false\nquote = "x"', MAPPING, "unknown keys"),
        (
            "enabled = false",
            '[sources.mapping]\nemployee_id = "id"\nnick = "n"\n',
            "unknown mapping fields",
        ),
    ],
)
def test_disabled_plugin_source_is_validated(tmp_path, register, extra, mapping, error):
    register("csv")
    with pytest.raises(ConfigError, match=error):
        load(tmp_path, source("csv", extra, mapping))


# End to end: a real distribution on the path, run through the installed CLI.

PLUGIN = """
import csv
import hashlib
import io
from pathlib import Path

from ek.adapters.base import EmployeeRecord, ReadResult, SourceError
from ek.config import ConfigError


class CsvPlugin:
    def __init__(self, sha=None, name=None, ref=None, extra=None):
        self.sha, self.name, self.ref, self.extra = sha, name, ref, extra

    def parse_options(self, options, where):
        if unknown := set(options) - {"delimiter"}:
            raise ConfigError(f"{where}: unknown keys {sorted(unknown)}")
        delimiter = options.get("delimiter", ",")
        if not isinstance(delimiter, str) or len(delimiter) != 1:
            raise ConfigError(f"{where}: 'delimiter' must be one character")
        return {"delimiter": delimiter}

    def read(self, path, source):
        path = Path(path)
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceError(f"{path.name}: not UTF-8") from exc
        sha = self.sha or hashlib.sha256(data).hexdigest()
        result = ReadResult(self.name or path.name, sha)
        rows = csv.DictReader(io.StringIO(text), delimiter=source.options["delimiter"])
        for n, row in enumerate(rows, start=2):
            values = {
                f: row[c] for f, c in source.mapping.items()
                if f != "employee_id" and row.get(c)
            }
            if self.extra:
                values[self.extra] = "x"
            emp = row[source.mapping["employee_id"]].strip()
            ref = self.ref or f"{path.name}!row {n}"
            result.records.append(EmployeeRecord(emp, values, ref))
        return result


plugin = CsvPlugin()
lie_sha = CsvPlugin(sha="0" * 64)
abs_name = CsvPlugin(name="/elsewhere/people.csv")
bad_ref = CsvPlugin(ref=" ")
extra_field = CsvPlugin(extra="nickname")
"""

CONFIG = """
[[sources]]
id = "{id}"
kind = "{kind}"
issuer = "example-hr"
mapping_version = "1"
delimiter = ";"
[sources.mapping]
employee_id = "Staff"
full_name = "Name"
department = "Team"
"""


@pytest.fixture
def csv_env(tmp_path):
    site = tmp_path / "site"
    (site / "ek_test_csv-0.0.0.dist-info").mkdir(parents=True)
    (site / "ek_test_csv.py").write_text(PLUGIN, encoding="utf-8")
    info = site / "ek_test_csv-0.0.0.dist-info"
    (info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: ek-test-csv\nVersion: 0.0.0\n", encoding="utf-8"
    )
    (info / "entry_points.txt").write_text(
        f"[{registry.GROUP}]\ncsv = ek_test_csv:plugin\n"
        "csv-lie-sha = ek_test_csv:lie_sha\ncsv-abs-name = ek_test_csv:abs_name\n"
        "csv-bad-ref = ek_test_csv:bad_ref\ncsv-extra = ek_test_csv:extra_field\n",
        encoding="utf-8",
    )
    config = tmp_path / "sources.toml"
    config.write_text(
        "".join(
            CONFIG.format(id=i, kind=k)
            for i, k in [
                ("csv-src", "csv"),
                ("lie-sha", "csv-lie-sha"),
                ("abs-name", "csv-abs-name"),
                ("bad-ref", "csv-bad-ref"),
                ("extra", "csv-extra"),
            ]
        ),
        encoding="utf-8",
    )
    people = tmp_path / "people.csv"
    people.write_text("Staff;Name;Team\nE-1;Ada Example;Eng\nE-2;Bo Example;Ops\n")
    store = tmp_path / "store.trig"

    def run(*args):
        env = {
            **os.environ,
            "PYTHONPATH": str(site),
            "EMPLOYEE_KNOWLEDGE_STORE": str(store),
            "COLUMNS": "1000",
        }
        return subprocess.run(
            [sys.executable, "-m", "ek.cli", *args, "--config", str(config)],
            check=False,
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
        )

    return types.SimpleNamespace(run=run, people=people, store=store)


def test_plugin_ingests_with_provenance_and_validation(csv_env):
    proc = csv_env.run("ingest", str(csv_env.people), "--source-id", "csv-src")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "4 observations of 4 assertions" in proc.stdout

    ds = Dataset(default_union=True)
    ds.parse(csv_env.store, format="trig")
    (file,) = ds.subjects(EK.fileName, None)
    assert str(ds.value(file, EK.fileName)) == "people.csv"
    sha = hashlib.sha256(csv_env.people.read_bytes()).hexdigest()
    assert str(ds.value(file, EK.sha256)) == sha
    observations = set(ds.subjects(RDF.type, EK.Observation))
    assert {str(ds.value(o, EK.sourceReference)) for o in observations} == {
        "people.csv!row 2",
        "people.csv!row 3",
    }
    assert all(ds.value(o, EK.validationResult) == EK.Conforms for o in observations)
    assertions = set(ds.subjects(RDF.type, EK.FactAssertion))
    assert len(assertions) == 4
    untrusted = ds.graph(UNTRUSTED_GRAPH)
    trusted = ds.graph(TRUSTED_GRAPH)
    assert all((a, RDF.type, EK.FactAssertion) in untrusted for a in assertions)
    assert not any((a, None, None) in trusted for a in assertions)


@pytest.mark.parametrize(
    ("source_id", "message"),
    [
        ("lie-sha", "sha256 does not match the file"),
        ("abs-name", "reported another file name"),
    ],
)
def test_plugin_file_provenance_is_verified(csv_env, source_id, message):
    # EK-012 review F2: ek checks file provenance; an adapter cannot assert it.
    proc = csv_env.run("ingest", str(csv_env.people), "--source-id", source_id)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert message in proc.stdout
    assert not csv_env.store.exists()


def test_plugin_model_finding_aborts_and_saves_nothing(csv_env):
    proc = csv_env.run("ingest", str(csv_env.people), "--source-id", "bad-ref")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "Nothing was saved" in proc.stdout
    assert not csv_env.store.exists()


def test_plugin_unmapped_field_is_refused(csv_env):
    proc = csv_env.run("ingest", str(csv_env.people), "--source-id", "extra")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "unmapped fields ['nickname']" in proc.stdout
    assert not csv_env.store.exists()


def test_ingest_excel_refuses_plugin_source(csv_env):
    proc = csv_env.run("ingest-excel", str(csv_env.people), "--source-id", "csv-src")
    assert proc.returncode == 1
    assert "not an Excel source" in proc.stdout
    assert not csv_env.store.exists()


def _assertions(store: Path) -> set[URIRef]:
    ds = Dataset(default_union=True)
    ds.parse(store, format="trig")
    return set(ds.subjects(RDF.type, EK.FactAssertion))


def test_excel_unchanged_through_generic_ingest(tmp_path, monkeypatch):
    outputs, stores = [], []
    for command in ("ingest", "ingest-excel"):
        store = tmp_path / f"{command}.trig"
        monkeypatch.setenv("EMPLOYEE_KNOWLEDGE_STORE", str(store))
        result = CliRunner().invoke(
            app,
            [
                command,
                str(EXAMPLES / "employees.xlsx"),
                "--source-id",
                "hr-export",
                "--config",
                str(EXAMPLES / "sources.toml"),
            ],
        )
        assert result.exit_code == 0, result.output
        run_id = r"urn:employee-knowledge:run:[0-9a-f-]+"
        outputs.append(re.sub(run_id, "RUN", result.output))
        stores.append(store)
    assert outputs[0] == outputs[1]
    assert "File sha256" in outputs[0]
    assert _assertions(stores[0]) == _assertions(stores[1])
    assert _assertions(stores[0])


def test_installed_excel_entry_point():
    plugin = registry.load_adapter("excel")
    assert plugin is not None and hasattr(plugin, "read")


# EK-012 review F1: every adapter's records are held to the Excel adapter's guarantees.


def _records(*records):
    return [
        EmployeeRecord(emp, values, f"p.csv!row {n}")
        for n, (emp, values) in enumerate(records, start=2)
    ]


@pytest.mark.parametrize(
    ("records", "message"),
    [
        ([(" ", {})], "unusable employee ID at p.csv!row 2"),
        ([("", {})], "unusable employee ID"),
        ([(" E-1", {})], "unusable employee ID"),
        ([(1001, {})], "unusable employee ID"),
        (
            [("E-1", {"department": "Eng"}), ("E-1", {"department": "Ops"})],
            "same employee ID at p.csv!row 2 and p.csv!row 3",
        ),
        ([("E-1", {"department": 5})], "not text at p.csv!row 2"),
        ([("E-1", {"nickname": "x"})], r"unmapped fields \['nickname'\]"),
    ],
)
def test_ingest_refuses_unusable_records(tmp_path, records, message):
    cfg = SourceConfig(
        "s",
        "csv",
        issuer="example-hr",
        mapping_version="1",
        mapping={"employee_id": "id", "department": "d"},
    )
    store = KnowledgeStore(tmp_path / "store.trig")
    before = len(store.dataset)
    with pytest.raises(SourceError, match=message):
        ingest(
            store,
            cfg,
            ReadResult("p.csv", "a" * 64, _records(*records)),
            datetime.now(UTC),
        )
    assert len(store.dataset) == before
    assert not (tmp_path / "store.trig").exists()

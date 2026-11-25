"""Source configuration loader (ADR-0007)."""

from pathlib import Path

import pytest

from ek.config import ConfigError, get_source, load_sources

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sources.toml"

EXCEL = """
[[sources]]
id = "hr"
kind = "excel"
issuer = "example-hr"
mapping_version = "1"
{extra}
[sources.mapping]
employee_id = "employee_id"
{mapping}
"""


def load(tmp_path, text):
    path = tmp_path / "sources.toml"
    path.write_text(text, encoding="utf-8")
    return load_sources(path)


def test_example_config_loads():
    sources = load_sources(EXAMPLE)
    hr = get_source(sources, "hr-export")
    assert (hr.kind, hr.issuer, hr.options.get("sheet"), hr.mapping_version) == (
        "excel",
        "example-hr",
        "Employees",
        "1",
    )
    assert hr.mapping["employee_id"] == "employee_id"
    assert not sources["jira-user-directory"].enabled


def test_minimal_excel_source(tmp_path):
    hr = get_source(load(tmp_path, EXCEL.format(extra="", mapping="")), "hr")
    assert hr.options == {} and hr.mapping == {"employee_id": "employee_id"}


@pytest.mark.parametrize(
    ("extra", "mapping", "error"),
    [
        ('trust_on_ingest = "trusted"', "", "unknown keys"),
        ('allowed_spaces = ["x"]', "", "unknown keys"),
        ("", 'nickname = "nick"', "unknown mapping fields"),
        ("", 'full_name = "  "', "'full_name' must be a non-blank string"),
        ('enabled = "yes"', "", "'enabled' must be true or false"),
    ],
)
def test_invalid_excel_source(tmp_path, extra, mapping, error):
    with pytest.raises(ConfigError, match=error):
        load(tmp_path, EXCEL.format(extra=extra, mapping=mapping))


@pytest.mark.parametrize(
    ("text", "error"),
    [
        (
            (
                '[[sources]]\nid = "hr"\nkind = "excel"\nmapping_version = "1"\n'
                '[sources.mapping]\nemployee_id = "id"\n'
            ),
            "'issuer'",
        ),
        (
            (
                '[[sources]]\nid = "hr"\nkind = "excel"\nissuer = "x"\n'
                'mapping_version = "1"\n[sources.mapping]\nfull_name = "n"\n'
            ),
            "employee_id",
        ),
        ('[[sources]]\nid = "j"\nkind = "jira"\n', "not implemented"),
        ('[[sources]]\nid = "x"\nkind = "csv"\nenabled = false\n', "unknown kind"),
        (
            (
                '[[sources]]\nid = "j"\nkind = "jira"\nenabled = false\n'
                '[[sources]]\nid = "j"\nkind = "jira"\nenabled = false\n'
            ),
            "duplicate",
        ),
        ('trust = "all"\n', "unknown top-level"),
        ("sources = [", "invalid TOML"),
    ],
)
def test_invalid_config(tmp_path, text, error):
    with pytest.raises(ConfigError, match=error):
        load(tmp_path, text)


def test_missing_file_points_to_example(tmp_path):
    with pytest.raises(ConfigError, match="examples/sources.toml"):
        load_sources(tmp_path / "nope.toml")


def test_unknown_and_disabled_source_ids_are_refused():
    sources = load_sources(EXAMPLE)
    with pytest.raises(ConfigError, match="Unknown source id"):
        get_source(sources, "hr-export-typo")
    with pytest.raises(ConfigError, match="disabled"):
        get_source(sources, "jira-user-directory")

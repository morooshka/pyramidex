import yaml

from pyramidex.reindex import (
    compute_additions,
    dump_schema,
    has_additions,
    merge,
    parse_schema,
    summarize,
)


TEMPLATE_SCHEMA = """\
nodes:
  Root: [version, schema, catalog, instructions]
  Domain: [name, description]
  Rule: [name, text]
  Skill: [name, description, prompt]
  Memory: [name, body, why, how_to_apply]
  Workflow: [name, description, config]
  Trigger: [idx, text]
  Step: [idx, text, notes]

relationships:
  - {type: HAS_DOMAIN, from: Root, to: Domain}
  - {type: HAS_RULE, from: Root, to: Rule}
  - {type: HAS_SKILL, from: Root, to: Skill}
  - {type: HAS_MEMORY, from: Root, to: Memory}
  - {type: HAS_WORKFLOW, from: Root, to: Workflow}
  - {type: HAS_TRIGGER, from: Workflow, to: Trigger}
  - {type: HAS_STEP, from: Workflow, to: Step}
  - {type: IN_DOMAIN, from: Rule, to: Domain}
  - {type: IN_DOMAIN, from: Skill, to: Domain}
  - {type: IN_DOMAIN, from: Memory, to: Domain}
  - {type: IN_DOMAIN, from: Workflow, to: Domain}
"""


def test_parse_schema_roundtrips_template() -> None:
    parsed = parse_schema(TEMPLATE_SCHEMA)
    assert parsed["nodes"]["Rule"] == ["name", "text"]
    assert parsed["nodes"]["Memory"] == ["name", "body", "why", "how_to_apply"]
    assert len(parsed["relationships"]) == 11
    assert {"type": "HAS_RULE", "from": "Root", "to": "Rule"} in parsed["relationships"]


def test_parse_handles_missing_sections() -> None:
    assert parse_schema("") == {"nodes": {}, "relationships": []}
    assert parse_schema("nodes:\n  Rule: [name]\n") == {
        "nodes": {"Rule": ["name"]},
        "relationships": [],
    }


def test_dump_schema_is_parseable() -> None:
    parsed = parse_schema(TEMPLATE_SCHEMA)
    dumped = dump_schema(parsed)
    reparsed = yaml.safe_load(dumped)
    assert reparsed["nodes"]["Rule"] == ["name", "text"]
    assert {"type": "IN_DOMAIN", "from": "Rule", "to": "Domain"} in reparsed["relationships"]


def test_no_drift_when_live_matches_known() -> None:
    known = parse_schema(TEMPLATE_SCHEMA)
    live = parse_schema(TEMPLATE_SCHEMA)
    additions = compute_additions(known, live)
    assert not has_additions(additions)
    assert additions == {"new_nodes": {}, "new_node_props": {}, "new_relationships": []}


def test_detects_new_label() -> None:
    known = parse_schema(TEMPLATE_SCHEMA)
    live = parse_schema(TEMPLATE_SCHEMA)
    live["nodes"]["Tag"] = ["name", "color"]
    additions = compute_additions(known, live)
    assert additions["new_nodes"] == {"Tag": ["name", "color"]}
    assert additions["new_node_props"] == {}
    assert additions["new_relationships"] == []


def test_detects_new_property_on_existing_label() -> None:
    known = parse_schema(TEMPLATE_SCHEMA)
    live = parse_schema(TEMPLATE_SCHEMA)
    live["nodes"]["Rule"] = ["name", "text", "severity"]
    additions = compute_additions(known, live)
    assert additions["new_nodes"] == {}
    assert additions["new_node_props"] == {"Rule": ["severity"]}


def test_detects_new_relationship() -> None:
    known = parse_schema(TEMPLATE_SCHEMA)
    live = parse_schema(TEMPLATE_SCHEMA)
    live["relationships"].append({"type": "DEPENDS_ON", "from": "Rule", "to": "Rule"})
    additions = compute_additions(known, live)
    assert additions["new_relationships"] == [
        {"type": "DEPENDS_ON", "from": "Rule", "to": "Rule"}
    ]


def test_merge_preserves_order_and_is_additive() -> None:
    known = parse_schema(TEMPLATE_SCHEMA)
    live = parse_schema(TEMPLATE_SCHEMA)
    live["nodes"]["Tag"] = ["name"]
    live["nodes"]["Rule"] = ["name", "text", "severity"]
    live["relationships"].append({"type": "DEPENDS_ON", "from": "Rule", "to": "Rule"})

    additions = compute_additions(known, live)
    merged = merge(known, additions)

    assert list(merged["nodes"].keys())[:8] == [
        "Root", "Domain", "Rule", "Skill", "Memory", "Workflow", "Trigger", "Step",
    ]
    assert merged["nodes"]["Tag"] == ["name"]
    assert merged["nodes"]["Rule"] == ["name", "text", "severity"]
    assert merged["relationships"][-1] == {
        "type": "DEPENDS_ON", "from": "Rule", "to": "Rule",
    }
    assert len(merged["relationships"]) == 12


def test_merge_never_removes_missing_entries() -> None:
    known = parse_schema(TEMPLATE_SCHEMA)
    live = {"nodes": {"Rule": ["name"]}, "relationships": []}
    additions = compute_additions(known, live)
    merged = merge(known, additions)

    assert "Skill" in merged["nodes"]
    assert "Memory" in merged["nodes"]
    assert merged["nodes"]["Rule"] == ["name", "text"]
    assert len(merged["relationships"]) == 11


def test_summarize_formats_each_kind() -> None:
    additions = {
        "new_nodes": {"Tag": ["name", "color"]},
        "new_node_props": {"Rule": ["severity"]},
        "new_relationships": [{"type": "DEPENDS_ON", "from": "Rule", "to": "Rule"}],
    }
    s = summarize(additions)
    assert "Node(:Tag {name, color})" in s
    assert "Props on :Rule [severity]" in s
    assert "[:DEPENDS_ON] Rule→Rule" in s

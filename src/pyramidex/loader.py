from pathlib import Path

import yaml
from neo4j import Driver, Session

from pyramidex.bootstrap import TEMPLATE_PATH


def load_dump(driver: Driver, dump_path: Path, template_path: Path = TEMPLATE_PATH) -> None:
    with open(dump_path) as f:
        dump = yaml.safe_load(f)

    with open(template_path) as f:
        template = yaml.safe_load(f)

    _ensure_domains(driver, dump.get("domains", []))

    with driver.session() as session:
        for schema_entry in dump["schema"]:
            key = schema_entry["key"]
            reserved = {item["name"] for item in template.get(key, []) if "name" in item}
            items = dump["data"].get(key, [])
            for item in items:
                if item.get("name") in reserved:
                    continue
                _create_node(session, schema_entry, item, parent_nid=None)


def _ensure_domains(driver: Driver, domains: list[dict]) -> None:
    with driver.session() as session:
        for domain in domains:
            session.run(
                "MATCH (r:Root) "
                "MERGE (d:Domain {name: $name}) "
                "SET d.description = $description "
                "MERGE (r)-[:HAS_DOMAIN]->(d)",
                name=domain["name"],
                description=domain["description"],
            )


def _labels(schema_entry: dict) -> str:
    label = schema_entry["node_label"]
    return ":".join(label) if isinstance(label, list) else label


def _props(item: dict, schema_entry: dict) -> dict:
    allowed = set(schema_entry["properties"])
    return {k: v for k, v in item.items() if k in allowed and v is not None}


def _create_node(session: Session, schema_entry: dict, item: dict, parent_nid: str | None) -> None:
    labels = _labels(schema_entry)
    props = _props(item, schema_entry)

    if parent_nid is None:
        root_rel = schema_entry["root_rel"]
        result = session.run(
            f"MATCH (r:Root) CREATE (r)-[:{root_rel}]->(n:{labels} $props) RETURN elementId(n) AS nid",
            props=props,
        )
    else:
        rel = schema_entry["relationship"]
        result = session.run(
            f"MATCH (p) WHERE elementId(p) = $pid "
            f"CREATE (p)-[:{rel}]->(n:{labels} $props) RETURN elementId(n) AS nid",
            pid=parent_nid,
            props=props,
        )

    nid = result.single()["nid"]

    if "domain_rel" in schema_entry:
        for domain_name in item.get("domains", []):
            session.run(
                "MATCH (n) WHERE elementId(n) = $nid "
                "MATCH (d:Domain {name: $domain}) "
                "CREATE (n)-[:IN_DOMAIN]->(d)",
                nid=nid,
                domain=domain_name,
            )

    for child_schema in schema_entry.get("children", []):
        for child_item in item.get(child_schema["key"], []):
            _create_node(session, child_schema, child_item, parent_nid=nid)

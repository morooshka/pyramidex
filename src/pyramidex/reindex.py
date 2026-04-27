from dataclasses import dataclass, field
from pathlib import Path

import yaml
from neo4j import Driver


LOG_PATH = Path.home() / ".pyramidex" / "reindex.log"


@dataclass
class ReindexResult:
    drifted: bool
    new_nodes: dict = field(default_factory=dict)
    new_node_props: dict = field(default_factory=dict)
    new_relationships: list = field(default_factory=list)


def parse_schema(schema_str: str) -> dict:
    data = yaml.safe_load(schema_str) or {}
    nodes = {
        label: list(props or [])
        for label, props in (data.get("nodes") or {}).items()
    }
    relationships = list(data.get("relationships") or [])
    return {"nodes": nodes, "relationships": relationships}


def dump_schema(schema: dict) -> str:
    return yaml.safe_dump(
        schema,
        sort_keys=False,
        default_flow_style=None,
        width=120,
    )


def fetch_known_schema(driver: Driver) -> dict:
    with driver.session() as session:
        record = session.run("MATCH (r:Root) RETURN r.schema AS schema").single()
    if record is None or record["schema"] is None:
        return {"nodes": {}, "relationships": []}
    return parse_schema(record["schema"])


def fetch_live_schema(driver: Driver) -> dict:
    with driver.session() as session:
        label_rows = session.run(
            "CALL db.schema.nodeTypeProperties() "
            "YIELD nodeLabels, propertyName "
            "RETURN nodeLabels, propertyName"
        ).data()

        nodes: dict[str, list[str]] = {}
        for row in label_rows:
            labels = row.get("nodeLabels") or []
            prop = row.get("propertyName")
            for label in labels:
                props = nodes.setdefault(label, [])
                if prop and prop not in props:
                    props.append(prop)

        rel_rows = session.run(
            "MATCH (a)-[r]->(b) "
            "WITH DISTINCT labels(a)[0] AS src, type(r) AS t, labels(b)[0] AS dst "
            "RETURN src, t, dst"
        ).data()

    relationships = [
        {"type": row["t"], "from": row["src"], "to": row["dst"]}
        for row in rel_rows
        if row["src"] and row["dst"]
    ]

    return {"nodes": nodes, "relationships": relationships}


def _rel_key(rel: dict) -> tuple:
    return (rel["type"], rel["from"], rel["to"])


def compute_additions(known: dict, live: dict) -> dict:
    known_nodes = known.get("nodes", {})
    live_nodes = live.get("nodes", {})

    new_nodes: dict[str, list[str]] = {}
    new_node_props: dict[str, list[str]] = {}
    for label, props in live_nodes.items():
        if label not in known_nodes:
            new_nodes[label] = list(props)
            continue
        missing = [p for p in props if p not in known_nodes[label]]
        if missing:
            new_node_props[label] = missing

    known_rel_keys = {_rel_key(r) for r in known.get("relationships", [])}
    new_relationships = [
        r for r in live.get("relationships", [])
        if _rel_key(r) not in known_rel_keys
    ]

    return {
        "new_nodes": new_nodes,
        "new_node_props": new_node_props,
        "new_relationships": new_relationships,
    }


def merge(known: dict, additions: dict) -> dict:
    merged_nodes = {
        label: list(props) for label, props in known.get("nodes", {}).items()
    }
    for label, props in additions.get("new_node_props", {}).items():
        for p in props:
            if p not in merged_nodes[label]:
                merged_nodes[label].append(p)
    for label, props in additions.get("new_nodes", {}).items():
        merged_nodes[label] = list(props)

    merged_rels = list(known.get("relationships", []))
    for r in additions.get("new_relationships", []):
        merged_rels.append(r)

    return {"nodes": merged_nodes, "relationships": merged_rels}


def has_additions(additions: dict) -> bool:
    return bool(
        additions.get("new_nodes")
        or additions.get("new_node_props")
        or additions.get("new_relationships")
    )


def summarize(additions: dict) -> str:
    parts = []
    for label, props in additions.get("new_nodes", {}).items():
        parts.append(f"Node(:{label} {{{', '.join(props)}}})")
    for label, props in additions.get("new_node_props", {}).items():
        parts.append(f"Props on :{label} [{', '.join(props)}]")
    for r in additions.get("new_relationships", []):
        parts.append(f"[:{r['type']}] {r['from']}→{r['to']}")
    return "; ".join(parts)


def reindex(driver: Driver, *, dry_run: bool = False) -> ReindexResult:
    known = fetch_known_schema(driver)
    live = fetch_live_schema(driver)
    additions = compute_additions(known, live)

    if not has_additions(additions):
        return ReindexResult(drifted=False)

    result = ReindexResult(
        drifted=True,
        new_nodes=additions["new_nodes"],
        new_node_props=additions["new_node_props"],
        new_relationships=additions["new_relationships"],
    )

    if dry_run:
        return result

    merged = merge(known, additions)
    new_schema_str = dump_schema(merged)
    with driver.session() as session:
        session.run("MATCH (r:Root) SET r.schema = $s", s=new_schema_str)
    return result

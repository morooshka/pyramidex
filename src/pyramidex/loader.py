import yaml


def load_dump(driver, dump_path):
    with open(dump_path) as f:
        dump = yaml.safe_load(f)

    _ensure_domains(driver, dump.get("domains", []))

    with driver.session() as session:
        for schema_entry in dump["schema"]:
            items = dump["data"].get(schema_entry["key"], [])
            for item in items:
                _create_node(session, schema_entry, item, parent_nid=None)


def _ensure_domains(driver, domains):
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


def _labels(schema_entry):
    label = schema_entry["node_label"]
    return ":".join(label) if isinstance(label, list) else label


def _props(item, schema_entry):
    allowed = set(schema_entry["properties"])
    return {k: v for k, v in item.items() if k in allowed and v is not None}


def _create_node(session, schema_entry, item, parent_nid):
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

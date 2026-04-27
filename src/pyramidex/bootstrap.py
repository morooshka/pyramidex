from pathlib import Path

import yaml
from neo4j import Driver

TEMPLATE_PATH = Path(__file__).parent / "assets" / "root-template.yaml"


def init_graph(driver: Driver, template_path: Path = TEMPLATE_PATH) -> None:
    with open(template_path) as f:
        template = yaml.safe_load(f)

    root = template["root"]
    domains = template["domains"]
    workflows = template.get("workflows", [])

    with driver.session() as session:
        session.run(
            "CREATE (r:Root {version: $version, schema: $schema, "
            "catalog: $catalog, instructions: $instructions})",
            version=root["version"],
            schema=root["schema"].strip(),
            catalog=root["catalog"].strip(),
            instructions=root["instructions"].strip(),
        )

        for domain in domains:
            session.run(
                "MATCH (r:Root) "
                "CREATE (d:Domain {name: $name, description: $description}) "
                "CREATE (r)-[:HAS_DOMAIN]->(d)",
                name=domain["name"],
                description=domain["description"],
            )

        for workflow in workflows:
            result = session.run(
                "MATCH (r:Root) "
                "CREATE (r)-[:HAS_WORKFLOW]->(w:Workflow "
                "{name: $name, description: $description, config: $config}) "
                "RETURN elementId(w) AS wid",
                name=workflow["name"],
                description=workflow["description"],
                config=workflow.get("config"),
            )
            wid = result.single()["wid"]

            for trigger in workflow.get("triggers", []):
                session.run(
                    "MATCH (w) WHERE elementId(w) = $wid "
                    "CREATE (w)-[:HAS_TRIGGER]->(:Trigger {idx: $idx, text: $text})",
                    wid=wid,
                    idx=trigger["idx"],
                    text=trigger["text"],
                )

            for step in workflow.get("steps", []):
                session.run(
                    "MATCH (w) WHERE elementId(w) = $wid "
                    "CREATE (w)-[:HAS_STEP]->(:Step "
                    "{idx: $idx, text: $text, notes: $notes})",
                    wid=wid,
                    idx=step["idx"],
                    text=step["text"],
                    notes=step.get("notes"),
                )

            for domain_name in workflow.get("domains", []):
                session.run(
                    "MATCH (w) WHERE elementId(w) = $wid "
                    "MATCH (d:Domain {name: $name}) "
                    "CREATE (w)-[:IN_DOMAIN]->(d)",
                    wid=wid,
                    name=domain_name,
                )

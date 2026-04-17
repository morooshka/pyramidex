from pathlib import Path
import yaml

TEMPLATE_PATH = Path(__file__).parent.parent.parent / "assets" / "root-template.yaml"


def init_graph(driver, template_path=TEMPLATE_PATH):
    with open(template_path) as f:
        template = yaml.safe_load(f)

    root = template["root"]
    domains = template["domains"]

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

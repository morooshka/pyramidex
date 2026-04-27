from dataclasses import dataclass, field
from pathlib import Path

import yaml
from neo4j import Driver

from pyramidex.bootstrap import TEMPLATE_PATH


@dataclass
class VerifyResult:
    ok: bool
    mismatches: list[str] = field(default_factory=list)


def verify(driver: Driver, dump_path: Path, template_path: Path = TEMPLATE_PATH) -> VerifyResult:
    with open(dump_path) as f:
        dump = yaml.safe_load(f)

    with open(template_path) as f:
        template = yaml.safe_load(f)

    mismatches = []

    with driver.session() as session:
        for schema_entry in dump["schema"]:
            label = schema_entry["node_label"]
            if isinstance(label, list):
                label = label[0]

            key = schema_entry["key"]
            reserved = {item["name"] for item in template.get(key, []) if "name" in item}
            dump_items = dump["data"].get(key, [])
            dump_count = sum(1 for item in dump_items if item.get("name") not in reserved)
            template_count = len(template.get(key, []))
            expected = dump_count + template_count

            actual = session.run(
                f"MATCH (n:{label}) RETURN count(n) AS c"
            ).single()["c"]

            if expected != actual:
                mismatches.append(f"{label}: expected {expected}, got {actual}")

    return VerifyResult(ok=not mismatches, mismatches=mismatches)

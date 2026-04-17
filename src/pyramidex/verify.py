from dataclasses import dataclass, field
import yaml


@dataclass
class VerifyResult:
    ok: bool
    mismatches: list[str] = field(default_factory=list)


def verify(driver, dump_path) -> VerifyResult:
    with open(dump_path) as f:
        dump = yaml.safe_load(f)

    mismatches = []

    with driver.session() as session:
        for schema_entry in dump["schema"]:
            label = schema_entry["node_label"]
            if isinstance(label, list):
                label = label[0]

            expected = len(dump["data"].get(schema_entry["key"], []))
            actual = session.run(
                f"MATCH (n:{label}) RETURN count(n) AS c"
            ).single()["c"]

            if expected != actual:
                mismatches.append(f"{label}: expected {expected}, got {actual}")

    return VerifyResult(ok=not mismatches, mismatches=mismatches)

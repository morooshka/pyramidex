from neo4j import Driver, GraphDatabase

from pyramidex.config import resolve_neo4j


def get_driver() -> Driver:
    n = resolve_neo4j()
    return GraphDatabase.driver(
        n["uri"],
        auth=(n["username"], n["password"]),
        database=n.get("database") or None,
    )

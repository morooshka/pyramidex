import os
from neo4j import GraphDatabase


def get_driver():
    uri = os.environ["NEO4J_URI"]
    auth = (os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"])
    return GraphDatabase.driver(uri, auth=auth)

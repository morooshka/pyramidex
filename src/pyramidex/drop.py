def drop_all(driver):
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

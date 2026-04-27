#!/usr/bin/env python3
"""Drop the graph, re-init from root-template.yaml, load dump.yaml, verify."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pyramidex.db import get_driver
from pyramidex.drop import drop_all
from pyramidex.bootstrap import init_graph
from pyramidex.loader import load_dump
from pyramidex.verify import verify

REPO = Path(__file__).parent.parent
TEMPLATE = REPO / "assets" / "root-template.yaml"
DUMP = REPO / "dump.yaml"


def main():
    if not DUMP.exists():
        print(f"Error: dump.yaml not found at {DUMP}")
        sys.exit(1)

    driver = get_driver()

    print("Dropping graph ...")
    drop_all(driver)

    print("Initialising Root and type domains ...")
    init_graph(driver, TEMPLATE)

    print(f"Loading {DUMP.name} ...")
    load_dump(driver, DUMP)

    print("Verifying ...")
    result = verify(driver, DUMP)

    driver.close()

    if result.ok:
        print("Done.")
    else:
        print("Verification failed:")
        for m in result.mismatches:
            print(f"  {m}")
        sys.exit(1)


if __name__ == "__main__":
    main()

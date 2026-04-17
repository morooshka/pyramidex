import argparse
import sys
from pathlib import Path

from pyramidex.db import get_driver
from pyramidex.drop import drop_all
from pyramidex.bootstrap import init_graph
from pyramidex.loader import load_dump
from pyramidex.verify import verify
from pyramidex.symlink import create_symlink

REPO = Path(__file__).parent.parent.parent
TEMPLATE = REPO / "assets" / "root-template.yaml"
DUMP = REPO / "dump.yaml"


def cmd_init(_args):
    if not DUMP.exists():
        print("Error: dump.yaml not found.")
        print("Generate it first by running the export prompt, then re-run: pyramidex init")
        sys.exit(1)

    driver = get_driver()

    print("Dropping graph...")
    drop_all(driver)

    print("Initialising Root and type domains...")
    init_graph(driver, TEMPLATE)

    print("Loading dump.yaml...")
    load_dump(driver, DUMP)

    print("Verifying...")
    result = verify(driver, DUMP)

    driver.close()

    if not result.ok:
        print("Verification failed — dump.yaml kept for inspection:")
        for m in result.mismatches:
            print(f"  {m}")
        sys.exit(1)

    print("Creating CLAUDE.md symlink...")
    create_symlink()

    DUMP.unlink()
    print("Done.")


def main():
    parser = argparse.ArgumentParser(prog="pyramidex")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Initialise or re-initialise the knowledge graph")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

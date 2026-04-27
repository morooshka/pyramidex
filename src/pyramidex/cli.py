import argparse
import getpass
import sys
import traceback
from datetime import datetime
from pathlib import Path

import yaml
from neo4j.exceptions import Neo4jError

from pyramidex.bootstrap import init_graph
from pyramidex.claude_bootstrap import install_claude_bootstrap
from pyramidex.config import (
    CONFIG_PATH,
    NEO4J_KEYS,
    NEO4J_REQUIRED,
    READY_TO_INIT_PATH,
    load_config,
    load_from_claude_settings,
    load_template,
    write_config,
)
from pyramidex.db import get_driver
from pyramidex.drop import drop_all
from pyramidex.hooks import SETTINGS_PATH, sync_claude_settings, verify_reindex_hook
from pyramidex.loader import load_dump
from pyramidex.reindex import LOG_PATH, reindex, summarize
from pyramidex.verify import verify

TEMPLATE = Path(__file__).parent / "assets" / "root-template.yaml"
DUMP = Path.cwd() / "dump.yaml"

_INIT_BLOCKED_MSG = """\
Error: pyramidex init is destructive and must be run after an AI-supervised export.

Run init through Claude Code instead of calling the CLI directly:
  1. Open this repo in Claude Code (`claude .`).
  2. Claude follows docs/prompts/setup.md, which runs the export prompt
     (docs/prompts/migrate-export.md) to produce {dump_name} from your
     existing AI configuration.
  3. On a successful export, the prompt creates {ready_token} as a
     one-shot token authorising the next init. This init consumes it.

If you are intentionally re-initialising and know what you are doing, you can
create the token manually: `touch {ready_token}` - but note that init
will drop the entire graph and reload it from {dump_name}.\
"""


def _gather_neo4j_from_flags(args) -> dict | None:
    if not any([args.uri, args.username, args.password, args.database]):
        return None
    return {
        "uri": args.uri or "",
        "username": args.username or "",
        "password": args.password or "",
        "database": args.database or "",
    }


def _gather_neo4j_interactively(defaults: dict) -> dict:
    out = {}
    for key in NEO4J_KEYS:
        default = defaults.get(key) or ""
        suffix = " (optional)" if key not in NEO4J_REQUIRED else ""
        if key == "password":
            value = getpass.getpass(f"neo4j.{key}{suffix}: ")
            if not value and default:
                value = default
        else:
            hint = f" [{default}]" if default else ""
            value = input(f"neo4j.{key}{suffix}{hint}: ").strip() or default
        out[key] = value
    return out


def _resolve_neo4j_for_write(args, existing_config: dict) -> dict:
    existing_neo4j = dict(existing_config.get("neo4j") or {})

    if getattr(args, "from_claude_settings", False):
        try:
            claude_creds = load_from_claude_settings()
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        merged = {**existing_neo4j, **claude_creds}
        return merged, "~/.claude/settings.json"

    flag_creds = _gather_neo4j_from_flags(args)
    if flag_creds:
        merged = {**existing_neo4j, **{k: v for k, v in flag_creds.items() if v}}
        return merged, "command-line flags"

    merged = _gather_neo4j_interactively(existing_neo4j)
    return merged, "interactive input"


def _write_config_and_sync(neo4j: dict, source: str) -> None:
    missing = [k for k in NEO4J_REQUIRED if not neo4j.get(k)]
    if missing:
        print(f"Error: missing required neo4j keys: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    config = load_config() or load_template()
    config["neo4j"] = {k: neo4j.get(k, "") for k in NEO4J_KEYS}
    write_config(config)
    print(f"Wrote {CONFIG_PATH} (from {source}).")

    sync_claude_settings(config["neo4j"])
    print(f"Synced Claude settings at {SETTINGS_PATH}.")


def cmd_init(args: argparse.Namespace) -> None:
    existing_config = load_config()
    has_creds = all(
        (existing_config.get("neo4j") or {}).get(k) for k in NEO4J_REQUIRED
    )

    source_flags_given = (
        getattr(args, "from_claude_settings", False)
        or _gather_neo4j_from_flags(args) is not None
    )

    if not has_creds or source_flags_given:
        # Fresh install or explicit cred update.
        if not has_creds and not source_flags_given:
            # Auto-seed from claude settings if available, else prompt.
            try:
                load_from_claude_settings()
                args.from_claude_settings = True
            except FileNotFoundError:
                pass
        neo4j, source = _resolve_neo4j_for_write(args, existing_config)
        _write_config_and_sync(neo4j, source)

    if not READY_TO_INIT_PATH.exists():
        print(_INIT_BLOCKED_MSG.format(dump_name=DUMP.name, ready_token=READY_TO_INIT_PATH))
        sys.exit(1)

    if not DUMP.exists():
        print(
            f"Error: {DUMP.name} not found, but {READY_TO_INIT_PATH} exists.\n"
            "Re-run the export prompt (docs/prompts/migrate-export.md) to regenerate it."
        )
        sys.exit(1)

    driver = get_driver()

    print("Dropping graph ...")
    drop_all(driver)

    print("Initialising Root, domains, and system workflows ...")
    init_graph(driver, TEMPLATE)

    print("Loading dump.yaml ...")
    load_dump(driver, DUMP)

    print("Verifying ...")
    result = verify(driver, DUMP)

    driver.close()

    if not result.ok:
        print("Verification failed - dump.yaml kept for inspection:")
        for m in result.mismatches:
            print(f"  {m}")
        sys.exit(1)

    print("Installing Claude bootstrap symlink ...")
    install_claude_bootstrap()

    READY_TO_INIT_PATH.unlink(missing_ok=True)

    print("Done.")


def _log_reindex_error(exc: BaseException) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(f"--- {datetime.now().isoformat(timespec='seconds')} ---\n")
            f.write(f"{type(exc).__name__}: {exc}\n")
            f.write(traceback.format_exc())
            f.write("\n")
    except OSError:
        pass


def cmd_reindex(args: argparse.Namespace) -> None:
    try:
        driver = get_driver()
        try:
            result = reindex(driver, dry_run=args.dry_run)
        finally:
            driver.close()
    except (Neo4jError, OSError, yaml.YAMLError) as exc:
        _log_reindex_error(exc)
        print(f"pyramidex reindex failed: {exc}", file=sys.stderr)
        print(f"See {LOG_PATH} for details.", file=sys.stderr)
        sys.exit(1)

    if not result.drifted:
        if args.verbose:
            print("No schema drift.")
        return

    additions = {
        "new_nodes": result.new_nodes,
        "new_node_props": result.new_node_props,
        "new_relationships": result.new_relationships,
    }
    prefix = "Would add: " if args.dry_run else "Added: "
    print(prefix + summarize(additions))


def cmd_set_credentials(args: argparse.Namespace) -> None:
    existing_config = load_config()
    neo4j, source = _resolve_neo4j_for_write(args, existing_config)
    _write_config_and_sync(neo4j, source)


CURRENT_SCHEMA_VERSION = 1


def cmd_upgrade(_args: argparse.Namespace) -> None:
    driver = get_driver()
    try:
        with driver.session() as session:
            record = session.run("MATCH (r:Root) RETURN r.version AS version").single()
    finally:
        driver.close()

    if record is None:
        print("No Root node found. Run `pyramidex init` first.", file=sys.stderr)
        sys.exit(1)

    current = record["version"]
    print(f"Current Root.version: {current}")
    print(f"Target version: {CURRENT_SCHEMA_VERSION}")

    if current == CURRENT_SCHEMA_VERSION:
        print(
            "No migrations available - `pyramidex upgrade` is reserved for future "
            "schema changes."
        )
        return

    print(
        f"Migration from v{current} to v{CURRENT_SCHEMA_VERSION} is not yet "
        "implemented.",
        file=sys.stderr,
    )
    sys.exit(1)


def cmd_install_claude_hooks(_args: argparse.Namespace) -> None:
    config = load_config()
    neo4j = config.get("neo4j") or {}
    missing = [k for k in NEO4J_REQUIRED if not neo4j.get(k)]
    if missing:
        print(
            f"Error: {CONFIG_PATH} missing keys: {', '.join(missing)}. "
            f"Run `pyramidex init` or `pyramidex set-credentials` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    sync_claude_settings(neo4j)
    print(f"Synced Claude settings at {SETTINGS_PATH}.")

    if verify_reindex_hook():
        print("Verification passed.")
    else:
        print("Verification failed - hook not found in expected format.", file=sys.stderr)
        sys.exit(1)


def _add_cred_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--from-claude-settings",
        action="store_true",
        help="Seed neo4j values from ~/.claude/settings.json mcpServers.neo4j-cloud.env",
    )
    parser.add_argument("--uri")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--database")


def main() -> None:
    parser = argparse.ArgumentParser(prog="pyramidex")
    sub = parser.add_subparsers(dest="command")

    init_parser = sub.add_parser("init", help="Initialise or re-initialise the knowledge graph")
    _add_cred_flags(init_parser)

    reindex_parser = sub.add_parser(
        "reindex",
        help="Detect new labels, properties, and relationships and update Root.schema",
    )
    reindex_parser.add_argument("--dry-run", action="store_true")
    reindex_parser.add_argument("--verbose", action="store_true")

    sub.add_parser(
        "install-claude-hooks",
        help="Re-sync ~/.claude/settings.json from ~/.pyramidex/config.yaml",
    )

    set_creds_parser = sub.add_parser(
        "set-credentials",
        help="Update Neo4j credentials in ~/.pyramidex/config.yaml and re-sync Claude settings",
    )
    _add_cred_flags(set_creds_parser)

    sub.add_parser(
        "upgrade",
        help="Apply pending schema migrations (no migrations exist yet - stub)",
    )

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "reindex":
        cmd_reindex(args)
    elif args.command == "install-claude-hooks":
        cmd_install_claude_hooks(args)
    elif args.command == "set-credentials":
        cmd_set_credentials(args)
    elif args.command == "upgrade":
        cmd_upgrade(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

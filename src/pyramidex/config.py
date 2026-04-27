import json
import os
import re
import stat
from pathlib import Path

import yaml

CONFIG_DIR = Path.home() / ".pyramidex"
CONFIG_PATH = CONFIG_DIR / "config.yaml"
READY_TO_INIT_PATH = CONFIG_DIR / "ready-to-init"
TEMPLATE_PATH = Path(__file__).parent / "assets" / "config-template.yaml"

CLAUDE_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
CLAUDE_MCP_SERVER = "neo4j-cloud"

NEO4J_REQUIRED = ("uri", "username", "password")
NEO4J_OPTIONAL = ("database",)
NEO4J_KEYS = NEO4J_REQUIRED + NEO4J_OPTIONAL


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def write_config(config: dict, path: Path = CONFIG_PATH) -> None:
    """Write config.yaml, preserving template comments by substituting values.

    Substitutes values into the commented template (or existing file) line-by-line.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    source_text = path.read_text() if path.exists() else TEMPLATE_PATH.read_text()
    new_text = _substitute_neo4j_values(source_text, config.get("neo4j") or {})
    path.write_text(new_text)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def _substitute_neo4j_values(text: str, neo4j: dict) -> str:
    """Replace `<key>: ...` lines under the `neo4j:` section with supplied values.
    Preserves indentation, comments, and ordering of the source text.
    """
    lines = text.splitlines(keepends=True)
    in_neo4j = False
    neo4j_indent = None
    out = []
    for raw in lines:
        stripped = raw.lstrip()
        indent = len(raw) - len(stripped)
        if stripped.startswith("neo4j:"):
            in_neo4j = True
            neo4j_indent = indent
            out.append(raw)
            continue
        if in_neo4j:
            if stripped and not stripped.startswith("#") and indent <= neo4j_indent:
                in_neo4j = False
            else:
                m = re.match(r"^(\s*)([a-zA-Z_][\w]*)(\s*):(.*)$", raw.rstrip("\n"))
                if m and not stripped.startswith("#"):
                    key = m.group(2)
                    if key in NEO4J_KEYS:
                        value = neo4j.get(key, "") or ""
                        newline = raw[-1] if raw.endswith("\n") else ""
                        dumped = yaml.safe_dump({key: value}, default_flow_style=False).rstrip()
                        out.append(f"{m.group(1)}{dumped}{newline}")
                        continue
        out.append(raw)
    return "".join(out)


def load_template() -> dict:
    return yaml.safe_load(TEMPLATE_PATH.read_text()) or {}


def load_from_claude_settings(path: Path = CLAUDE_SETTINGS_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")
    data = json.loads(path.read_text())
    env = (
        data.get("mcpServers", {})
        .get(CLAUDE_MCP_SERVER, {})
        .get("env", {})
        or {}
    )
    mapping = {
        "uri": env.get("NEO4J_URI"),
        "username": env.get("NEO4J_USERNAME"),
        "password": env.get("NEO4J_PASSWORD"),
        "database": env.get("NEO4J_DATABASE"),
    }
    return {k: v for k, v in mapping.items() if v}


def resolve_neo4j() -> dict:
    config = load_config()
    neo4j = dict(config.get("neo4j") or {})

    env_map = {
        "uri": "NEO4J_URI",
        "username": "NEO4J_USERNAME",
        "password": "NEO4J_PASSWORD",
        "database": "NEO4J_DATABASE",
    }
    for key, env_name in env_map.items():
        if os.environ.get(env_name):
            neo4j[key] = os.environ[env_name]

    missing = [k for k in NEO4J_REQUIRED if not neo4j.get(k)]
    if missing:
        raise RuntimeError(
            f"Missing Neo4j config keys: {', '.join(missing)}. "
            f"Run `pyramidex init` or `pyramidex set-credentials` to configure, "
            f"or set NEO4J_* env vars for CI/tests."
        )
    return neo4j

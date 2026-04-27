import json
import os
import stat
import tempfile
from pathlib import Path


SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
MATCHER = "mcp__neo4j-cloud__write-cypher"
COMMAND = "pyramidex reindex"
MCP_SERVER_NAME = "neo4j-cloud"
MCP_SERVER_COMMAND = "uvx"
MCP_SERVER_ARGS = ["mcp-neo4j-cloud"]
READ_CYPHER_PERMISSION = "mcp__neo4j-cloud__read-cypher"


def install_reindex_hook(settings_path: Path = SETTINGS_PATH) -> bool:
    settings = _load(settings_path)
    changed = _merge_reindex_hook(settings)
    if changed:
        _atomic_write(settings_path, settings)
    return changed


def verify_reindex_hook(settings_path: Path = SETTINGS_PATH) -> bool:
    post_tool_use = _load(settings_path).get("hooks", {}).get("PostToolUse", [])
    for entry in post_tool_use:
        if entry.get("matcher") == MATCHER:
            inner = entry.get("hooks", [])
            if any(
                h.get("type") == "command" and h.get("command") == COMMAND
                for h in inner
            ):
                return True
    return False


def sync_claude_settings(neo4j: dict, settings_path: Path = SETTINGS_PATH) -> None:
    """Write all Pyramidex-managed entries into ~/.claude/settings.json.

    Manages: mcpServers.neo4j-cloud, PostToolUse reindex hook, and the
    read-cypher permission. All other keys are preserved.
    """
    settings = _load(settings_path)
    _merge_mcp_server(settings, neo4j)
    _merge_reindex_hook(settings)
    _merge_read_cypher_allow(settings)
    _atomic_write(settings_path, settings)


def _merge_mcp_server(settings: dict, neo4j: dict) -> None:
    env = {
        "NEO4J_URI": neo4j["uri"],
        "NEO4J_USERNAME": neo4j["username"],
        "NEO4J_PASSWORD": neo4j["password"],
    }
    if neo4j.get("database"):
        env["NEO4J_DATABASE"] = neo4j["database"]

    servers = settings.setdefault("mcpServers", {})
    servers[MCP_SERVER_NAME] = {
        "command": MCP_SERVER_COMMAND,
        "args": list(MCP_SERVER_ARGS),
        "env": env,
    }


def _merge_reindex_hook(settings: dict) -> bool:
    hooks = settings.setdefault("hooks", {})
    post_tool_use = hooks.setdefault("PostToolUse", [])

    for entry in post_tool_use:
        if entry.get("matcher") == MATCHER:
            inner = entry.get("hooks", [])
            if any(h.get("command") == COMMAND for h in inner):
                return False

    hooks["PostToolUse"] = [e for e in post_tool_use if e.get("matcher") != MATCHER]
    hooks["PostToolUse"].append(
        {"matcher": MATCHER, "hooks": [{"type": "command", "command": COMMAND}]}
    )
    return True


def _merge_read_cypher_allow(settings: dict) -> None:
    allow = settings.setdefault("permissions", {}).setdefault("allow", [])
    if READ_CYPHER_PERMISSION not in allow:
        allow.append(READ_CYPHER_PERMISSION)


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    replaced = False
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
        replaced = True
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    finally:
        if not replaced and os.path.exists(tmp):
            os.unlink(tmp)

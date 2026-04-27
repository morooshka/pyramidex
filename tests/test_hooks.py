import json

from pyramidex.hooks import (
    COMMAND,
    MATCHER,
    MCP_SERVER_NAME,
    READ_CYPHER_PERMISSION,
    install_reindex_hook,
    sync_claude_settings,
    verify_reindex_hook,
)


NEO4J = {
    "uri": "neo4j+s://example.databases.neo4j.io",
    "username": "neo4j",
    "password": "secret",
    "database": "neo4j",
}


def test_install_creates_settings_and_hook(tmp_path) -> None:
    settings = tmp_path / "settings.json"
    added = install_reindex_hook(settings)
    assert added is True

    data = json.loads(settings.read_text())
    entries = data["hooks"]["PostToolUse"]
    assert entries == [{"matcher": MATCHER, "hooks": [{"type": "command", "command": COMMAND}]}]


def test_install_is_idempotent(tmp_path) -> None:
    settings = tmp_path / "settings.json"
    install_reindex_hook(settings)
    added = install_reindex_hook(settings)
    assert added is False

    data = json.loads(settings.read_text())
    entries = data["hooks"]["PostToolUse"]
    assert len(entries) == 1


def test_install_preserves_existing_settings(tmp_path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({
        "model": "opus",
        "hooks": {
            "PostToolUse": [
                {"matcher": "SomethingElse", "command": "echo hi"}
            ],
            "PreToolUse": [
                {"matcher": "Other", "command": "echo pre"}
            ],
        },
    }))

    install_reindex_hook(settings)
    data = json.loads(settings.read_text())

    assert data["model"] == "opus"
    assert {"matcher": "Other", "command": "echo pre"} in data["hooks"]["PreToolUse"]
    entries = data["hooks"]["PostToolUse"]
    assert {"matcher": "SomethingElse", "command": "echo hi"} in entries
    assert {"matcher": MATCHER, "hooks": [{"type": "command", "command": COMMAND}]} in entries


def test_sync_writes_all_three_managed_entries(tmp_path) -> None:
    settings = tmp_path / "settings.json"
    sync_claude_settings(NEO4J, settings)

    data = json.loads(settings.read_text())

    server = data["mcpServers"][MCP_SERVER_NAME]
    assert server["env"]["NEO4J_URI"] == NEO4J["uri"]
    assert server["env"]["NEO4J_USERNAME"] == NEO4J["username"]
    assert server["env"]["NEO4J_PASSWORD"] == NEO4J["password"]
    assert server["env"]["NEO4J_DATABASE"] == NEO4J["database"]

    assert verify_reindex_hook(settings) is True
    assert READ_CYPHER_PERMISSION in data["permissions"]["allow"]


def test_sync_preserves_unrelated_keys_and_is_idempotent(tmp_path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({
        "model": "opus",
        "mcpServers": {"other-server": {"command": "stay"}},
        "permissions": {"allow": ["mcp__something__else"]},
    }))

    sync_claude_settings(NEO4J, settings)
    sync_claude_settings(NEO4J, settings)

    data = json.loads(settings.read_text())

    assert data["model"] == "opus"
    assert data["mcpServers"]["other-server"] == {"command": "stay"}
    assert "mcp__something__else" in data["permissions"]["allow"]
    assert data["permissions"]["allow"].count(READ_CYPHER_PERMISSION) == 1
    assert len(data["hooks"]["PostToolUse"]) == 1


def test_sync_omits_database_env_when_blank(tmp_path) -> None:
    settings = tmp_path / "settings.json"
    sync_claude_settings({**NEO4J, "database": ""}, settings)

    env = json.loads(settings.read_text())["mcpServers"][MCP_SERVER_NAME]["env"]
    assert "NEO4J_DATABASE" not in env

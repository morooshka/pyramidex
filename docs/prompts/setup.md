# Pyramidex Setup Guide

You are guiding a user through a fresh Pyramidex installation. Follow each step in order.
Check in with the user after each step before proceeding.
Steps marked [NOT IMPLEMENTED] are stubs - announce them, tell the user what will go here,
and move on without executing anything.

---

## Step 1 - Check uv is installed

Run `uv --version`. If it fails, tell the user to install uv:
  https://docs.astral.sh/uv/getting-started/installation/
Wait for them to confirm it is installed before continuing.

## Step 2 - Install pyramidex

Run `uv sync` in the repo root to materialise the project venv, then install the CLI
globally:

  uv tool install .

The reindex hook runs in a detached shell with no CWD and no venv activation, so
`pyramidex` must be on PATH globally. Verify with `command -v pyramidex` - it should
resolve to a path under `~/.local/bin/`. If not, tell the user to ensure
`~/.local/bin` is on their PATH.

## Step 3 - Create Neo4j Aura instance

Guide the user through creating a free Neo4j Aura database:

1. Open https://console.neo4j.io in a browser. Sign up for a free account or log in.
2. Click "New instance".
3. Select the "AuraDB Free" tier.
4. Enter a name for the instance (e.g. `pyramidex`) and click "Create free database".
5. A credentials dialog appears immediately. IMPORTANT: these are shown only once.
   Ask the user to copy all four values before closing the dialog:
   - URI (starts with `neo4j+s://`)
   - Username
   - Password
   - Database (the instance ID, same as the subdomain in the URI)
6. The instance takes roughly 2 minutes to spin up. Wait until status shows "Running".

Ask the user to confirm they have all four credentials and the instance is running.

## Step 4 - Configure credentials and Claude settings

### 4.1 - Check for existing configuration

Read `~/.claude/settings.json`. If `.mcpServers.neo4j-cloud.env` already contains
`NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and `NEO4J_DATABASE`, ask the user:
  "neo4j-cloud is already configured in ~/.claude/settings.json. Keep existing
  settings or redefine them?"
  Options: Keep / Redefine

If the user chooses Keep, run:

  pyramidex set-credentials --from-claude-settings

This seeds `~/.pyramidex/config.yaml` from the existing settings.json values.
Skip ahead to step 4.3.

### 4.2 - Write configuration

Run a single command - it writes `~/.pyramidex/config.yaml` (chmod 0600) and syncs
the three pyramidex-managed entries in `~/.claude/settings.json` (MCP server env,
PostToolUse reindex hook, read-cypher allow). All other settings.json keys are
preserved.

  pyramidex set-credentials --uri <uri> --username <username> --password <password> --database <database>

Replace each placeholder with the value collected in step 3.

The MCP server is launched via `uvx`, which is already available from step 1 - no
separate install is needed. (If the user prefers a permanent install, they can run
`uv tool install mcp-neo4j-cloud` or `brew install mcp-neo4j-cloud`.)

`write-cypher` is intentionally NOT auto-allowed - it only runs on explicit user
requests and should keep its confirmation prompt.

### 4.3 - Test the connection

Run:

  pyramidex set-credentials --from-claude-settings

This is a no-op re-sync if the config is already in place; if it errors, the
credentials are wrong and the user should re-run step 4.2 with corrected values.
For an explicit driver round-trip:

  uv run python -c "
  from pyramidex.db import get_driver
  d = get_driver()
  d.verify_connectivity()
  d.close()
  print('Connection OK')
  "

If the test fails, show the full error and return to step 4.2.

### 4.4 - Inform about MCP activation

Tell the user:
  "MCP configured, connection verified, and permissions set. The neo4j-cloud MCP
  server will become active in new Claude Code sessions - not in this one. The
  remaining setup steps will use the credentials directly."

## Step 5 - Export existing configuration

Read `docs/prompts/migrate-export.md` and follow it exactly. It will discover the user's
existing AI configuration (from files or a graph) and write `dump.yaml` to the repo root.

When the export is complete, tell the user how many rules, memories, and workflows were found,
and ask them to confirm the export looks correct before proceeding.

Once the user confirms, create the one-shot init authorisation token:

  mkdir -p ~/.pyramidex && touch ~/.pyramidex/ready-to-init

`pyramidex init` refuses to run without this token and consumes it on success. It exists
so that init cannot be run manually against a stale dump or without a fresh export.

## Step 6 - Run pyramidex init

Run `pyramidex init` from the repo root (the CLI reads `dump.yaml` from the current
working directory).

Report each stage as it completes (Dropping, Initialising, Loading, Verifying, Symlinking).
If init exits with an error, show the output and stop - do not continue.

## Step 7 - Confirm setup is complete

Verify that `~/.claude/CLAUDE.md` is now a symlink pointing to
`src/pyramidex/assets/claude-bootstrap.md` inside the repo.

Ask the user: "Init is complete. Delete dump.yaml now? It contains your full configuration
in plaintext. You can always re-export it later."

Delete `dump.yaml` only if the user answers yes. Do not delete it otherwise.

Tell the user:
  "Setup complete. Your knowledge graph is live. Open a new Claude Code session anywhere
  and Claude will bootstrap from the graph automatically."

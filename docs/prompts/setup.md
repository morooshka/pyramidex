# Pyramidex Setup Guide

You are guiding a user through a fresh Pyramidex installation. Follow each step in order.
Check in with the user after each step before proceeding.
Steps marked [NOT IMPLEMENTED] are stubs — announce them, tell the user what will go here,
and move on without executing anything.

---

## Step 1 — Check uv is installed

Run `uv --version`. If it fails, tell the user to install uv:
  https://docs.astral.sh/uv/getting-started/installation/
Wait for them to confirm it is installed before continuing.

## Step 2 — Install Python dependencies

Run `uv sync` in the repo root. Report the result.

## Step 3 — Create Neo4j database [NOT IMPLEMENTED]

Tell the user:
  "This step will guide you through creating a free Neo4j Aura instance and obtaining
  the connection URI, username, and password. Not yet implemented — please create your
  Aura instance manually at https://neo4j.com/cloud/platform/aura-graph-database/ and
  note the credentials. Continue when ready."

Wait for the user to confirm they have the credentials before continuing.

## Step 4 — Configure neo4j-cloud MCP [NOT IMPLEMENTED]

Tell the user:
  "This step will automatically add the neo4j-cloud MCP server to your
  ~/.claude/settings.json with the credentials from step 3. Not yet implemented —
  please add it manually. Example entry for ~/.claude/settings.json:

  {
    \"mcpServers\": {
      \"neo4j-cloud\": {
        \"command\": \"uvx\",
        \"args\": [\"mcp-neo4j-cloud\"],
        \"env\": {
          \"NEO4J_URI\": \"<your URI>\",
          \"NEO4J_USERNAME\": \"<your username>\",
          \"NEO4J_PASSWORD\": \"<your password>\"
        }
      }
    }
  }

  Continue when the MCP entry is in place."

Wait for the user to confirm before continuing.

## Step 5 — Export existing configuration

Read `docs/prompts/migrate-export.md` and follow it exactly. It will discover the user's
existing AI configuration (from files or a graph) and write `dump.yaml` to the repo root.

When the export is complete, tell the user how many rules, memories, and workflows were found,
and ask them to confirm the export looks correct before proceeding.

## Step 6 — Run pyramidex init

Read the Neo4j credentials from the `neo4j-cloud` entry in `~/.claude/settings.json`.
Inject them as environment variables and run:

  NEO4J_URI="..." NEO4J_USERNAME="..." NEO4J_PASSWORD="..." uv run pyramidex init

Report each stage as it completes (Dropping, Initialising, Loading, Verifying, Symlinking).
If init exits with an error, show the output and stop — do not continue.

## Step 7 — Confirm setup is complete

Verify that `~/.claude/CLAUDE.md` is now a symlink pointing to `assets/claude-bootstrap.md`.

Ask the user: "Init is complete. Delete dump.yaml now? It contains your full configuration
in plaintext. You can always re-export it later."

Delete `dump.yaml` only if the user answers yes. Do not delete it otherwise.

Tell the user:
  "Setup complete. Your knowledge graph is live. Open a new Claude Code session anywhere
  and Claude will bootstrap from the graph automatically."

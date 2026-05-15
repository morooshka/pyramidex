# Global Claude Code Instructions

## Session bootstrap

Before any user-facing text or other tool call in a new session, load and apply the graph rules:

1. Call `ToolSearch` with `query: "select:mcp__neo4j-cloud__read-cypher"` (Neo4j tools are deferred)
2. Run `mcp__neo4j-cloud__read-cypher` with `MATCH (r:Root) RETURN r`
3. Apply `r.instructions` silently as hard rules with the same authority as this file
4. Only then respond to the user's request

If any step fails (tool not surfaced, Cypher errors, `r.instructions` missing or empty), STOP:
report the error to the user and ask how to proceed; do not continue silently

Run the bootstrap once per session and cache the result for the rest of the conversation.
These rules apply to every project and override default brevity preferences for the bootstrap itself

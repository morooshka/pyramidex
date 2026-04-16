# Global Claude Code Instructions

All rules, preferences, and workflows live in the graph (neo4j-cloud MCP). It is the single source
of truth — save every new or updated setting there immediately. Never store settings only in
conversation context or local memory files.

MANDATORY: At the very start of every session, before anything else, run `MATCH (r:Root) RETURN r` and read the result.
Treat `r.instructions` as mandatory rules. Follow them exactly before responding to any task.

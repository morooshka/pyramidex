# pyramidex

A `CLAUDE.md` that loads on demand.

Pyramidex stores your AI configuration in a knowledge graph. Each
Claude Code session starts with a small index, and the tool fetches
only the rules, memories, and workflows the current task actually
needs. Less context per session, no duplicate rules drifting between
files, a config that keeps up as it grows.

Built for Claude Code only - other AI hosts are out of scope

## Why use Pyramidex?

For the data model and design rationale, see
[docs/knowledge-design-guide.md](docs/knowledge-design-guide.md)

What you get:

1. Lazy, tiered loading. Sessions start with a ~275-token domain index;
   only the domains the task touches are fetched
2. No duplication. A rule that applies to two contexts is one node with two
   edges, not two copies that drift apart
3. Self-describing. The graph carries its own schema and bootstrap query,
   no external docs to keep in sync
4. Atomic edits. Adding or changing a rule is one write, not "edit the file,
   update the index, fix the description"
5. Portable when hosted in the cloud. Same rules and memories on every machine,
   no dotfile sync

What it costs:

1. A graph database. Managed (Aura free tier works) or self-hosted, either way
   another moving part
2. An MCP server per machine. One-time install, but credentials must be
   configured wherever you use it
3. A learning curve. You edit config by talking to Claude, not by editing
   a file

When it is worth it:

Your `CLAUDE.md` feels crowded, you have rules duplicated across contexts,
or you work from more than one machine. If your config is a dozen lines in
a single file on one laptop, stick with plain Markdown

## Getting started

~~~shell
git clone https://github.com/morooshka/pyramidex
cd pyramidex
claude
~~~

Then ask Claude:

~~~text
Follow docs/prompts/setup.md and set up Pyramidex for me
~~~

First-time setup runs about 10-15 minutes, mostly waiting for the Neo4j Aura
instance to spin up. Claude handles the rest

## License

MIT - see [LICENSE](LICENSE)

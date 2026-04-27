# Migration Export Prompt

Used by `pyramidex init` step 1. Passed to the AI to produce `dump.yaml`.
Before classifying any content, read `docs/knowledge-design-guide.md` and use it as the
quality standard for every classification decision.

---

You are an expert knowledge graph engineer specialising in AI assistant configuration systems.
You have deep experience parsing heterogeneous configuration sources, inferring schemas from
unstructured data, and producing clean, lossless structured exports for graph database ingestion.

You are performing a one-time export of a user's AI assistant configuration into a structured
knowledge graph migration file called `dump.yaml`.

## Your task

Discover all user configuration, analyse it fully, infer the complete schema, and write the result
to `dump.yaml` in the format specified below. Nothing must be lost. Every piece of configuration
the user has defined - regardless of where it lives or what structure it has - must appear in the
output.

## Source discovery

Read `{claude_md_path}` and follow whatever instructions it contains to locate and retrieve the
user's configuration. Do not assume any particular source type or location - the instructions
in that file are authoritative. If it points to a database, query it. If it references files,
read them. If it describes a different mechanism, follow it.

When the source is a graph database, apply this retrieval protocol:

1. Run a schema discovery query (e.g. `CALL db.schema.visualization()` or `CALL apoc.meta.graph()`)
   to identify all node labels and relationship types present. If schema introspection is
   unavailable, run `MATCH (n) RETURN DISTINCT labels(n)` and
   `MATCH ()-[r]->() RETURN DISTINCT type(r)` separately.
2. For each node label, run a dedicated query that follows all outgoing relationships to their
   full depth. Never assume a single query returns the complete tree. Example pattern:
   `MATCH (root)-[:HAS_X]->(parent) OPTIONAL MATCH (parent)-[:HAS_Y]->(child) RETURN parent, collect(child)`.
3. Before writing the dump, verify that every parent node's child collection is non-empty
   where children are expected. If a collection is empty, re-query before concluding there
   is no data - empty results on a first query are a retrieval failure, not evidence of absence.
4. Leaf nodes (rules, steps, triggers, field options, etc.) must be fetched explicitly.
   They will never appear in a query that only matches the root or parent nodes.

## Classification rules

The target schema is authoritative. Map all source content to the standard types below
regardless of how the source organises it - the source structure is irrelevant. What matters
is the meaning of the content, not the form it was stored in.

Standard types:

1. Rule - a single behavioral instruction or constraint. Atomic: one rule, one requirement.
   Has a `name` (short label) and `text` (the instruction itself).
2. Skill - a reusable prompt or slash command. Has a `name`, `description`, and `prompt`
   (the full prompt text).
3. Memory - a retained piece of knowledge the AI should carry across sessions. Has `name`,
   `body` (the knowledge), `why` (the reason it matters), and `how_to_apply` (when it applies).
4. Workflow - a structured process triggered by a user request. Has ordered steps and
   optional trigger phrases. Any associated configuration data (e.g. API field IDs, project
   metadata, option IDs) must be serialised as a JSON string in the `config` property on the
   Workflow node itself - not as nested child nodes.

If content does not fit any standard type, do not force it. Infer a new type from the content
itself: name it descriptively, define its properties, and include it in the schema. Every custom
type you invent must appear in the `schema` section so the loader knows how to create it.

## Domain assignment

Every node must declare a `domains` list. Domains serve two purposes:

1. Type domain - always include the built-in type domain for the node's type:
   `rules`, `skills`, `memories`, or `workflows`. This enables listing all nodes of a type
   on request.
2. Contextual domain(s) - add one or more domains describing when this node is relevant.
   Common values: `code`, `shell`, `deploy`, `python`, `ticket`, `infra`, `formatting`.
   Add new domain values as needed - the domain list in the output is authoritative.

Example: a rule about shell variable syntax gets `domains: [rules, shell]`.
Example: a workflow for ticket creation gets `domains: [workflows, ticket]`.

### Domain descriptions

The `description` field is the sole signal the runtime uses to route tasks to domains.
Every description must follow this shape:

```
[tier] Load when <concrete trigger predicates>
```

Tier tag rubric:

1. `[broad]` - the domain applies whenever the task touches its surface. Use for
   cross-cutting contexts that most sessions need: `code`, `formatting`
2. `[specific]` - the domain applies only on concrete evidence in the task (language,
   tool, environment). Use for targeted contexts: `python`, `shell`, `deploy`, `infra`,
   `ticket`
3. `[meta]` - fixed for the four type domains below. Do not apply `[meta]` to a
   contextual domain

When in doubt between broad and specific, choose specific. Broad domains load on every
matching task, so over-tagging broad inflates per-task cost.

Contextual domain description examples:

1. `code` - `[broad] Load when editing any source, configuration, script, or data file`
2. `formatting` - `[broad] Load when producing code, markdown, prose, or any written output`
3. `python` - `[specific] Load when editing .py files or working with Python syntax, imports, or stdlib`
4. `shell` - `[specific] Load when writing shell commands, bash scripts, or command-line expressions`
5. `deploy` - `[specific] Load when using helm, kubectl, ArgoCD, or other cluster-state actions`

Fixed type domain descriptions - copy verbatim, do not infer:

1. `rules` - `[meta] Load when the user asks to list or review rules`
2. `skills` - `[meta] Load when the user asks to list available skills or slash commands`
3. `memories` - `[meta] Load when the user asks to review or manage memories`
4. `workflows` - `[meta] Load when the user asks to follow a process or list available procedures`

## Output format

Write the result to `{dump_path}`. The file must be valid YAML and must follow this structure
exactly:

```yaml
meta:
  created_at: <ISO 8601 date>
  pyramidex_version: 1
  warnings:                  # optional - list any assumptions or unresolved questions here
    - "<description>"        # omit the key entirely if there are no warnings

domains:
  - name: <string>          # complete list of all domains used anywhere in the data section
    description: <string>   # one-line description; use fixed descriptions for type domains

schema:
  - key: <string>              # matches a top-level key in the data section
    node_label: <string>       # Neo4j node label to apply
    root_rel: <string>         # relationship name from Root node to this node type
    domain_rel: IN_DOMAIN      # always present - loader creates [:IN_DOMAIN] rels from domains list
    properties: [<string>]     # all properties that appear on nodes of this type (excluding domains)
    children:                  # optional - nested node types owned by this node
      - key: <string>
        node_label: <string>
        relationship: <string> # relationship from parent to child
        properties: [<string>]
        children: [...]        # arbitrarily deep nesting is supported

data:
  <key>:                       # top-level key matching schema[*].key
    - <property>: <value>
      domains: [<string>]      # list of domain names - loader creates [:IN_DOMAIN] for each
      <child_key>:             # nested key matching schema[*].children[*].key
        - <property>: <value>
```

## Schema rules

1. Every node type present in `data` must have a corresponding entry in `schema`.
2. Every property that appears on any node must be listed in `schema[*].properties` for that
   type. Do not list `domains` in properties - it is handled by `domain_rel`.
3. Nested child nodes (e.g. Steps under Workflow) must be declared in `children` and appear
   as nested lists in the data.
4. The `root_rel` value should follow Neo4j naming conventions: uppercase with underscores,
   prefixed with `HAS_` (e.g. `HAS_RULE`, `HAS_MEMORY`).

## Quality requirements

1. Every node must have a `name` property.
2. Do not invent or infer content that is not present in the source files. Export only what exists.
3. Do not drop properties that appear in the source. If a property has no clear mapping, include
   it as-is on the most appropriate node type and add it to the schema.
4. Preserve all field IDs, option IDs, API identifiers, and numeric values exactly as found.
5. If two source items appear to describe the same thing, merge them into one node with the most
   complete set of properties. Do not create duplicates.
6. System-provided nodes - do not export. Some domains and workflows are restored from
   `assets/root-template.yaml` on every init. Re-exporting them causes duplicates. Currently
   reserved names:
   1. domain `authoring`
   2. workflow `add-content` (with its triggers and steps)

   Skip these when reading from the source graph, even if present.

## After a successful export

Once `{dump_path}` has been written and you have confirmed it contains everything expected,
create the init authorisation token so the destructive `pyramidex init` step can proceed:

  mkdir -p ~/.pyramidex && touch ~/.pyramidex/ready-to-init

This token is a one-shot - `pyramidex init` consumes it on success. It exists so that init
cannot be run manually against a stale dump or without a fresh export. Do not create it
unless the export just completed successfully.

## Handling uncertainty

Never stop or ask for clarification. If you encounter ambiguous content, make the most reasonable
assumption and record it as a warning in `meta.warnings`. Each warning must describe what was
ambiguous and what assumption was made. If there are no warnings, omit the `meta.warnings` key
entirely. Do not write warnings, comments, or notes anywhere else in the file - any text outside
the defined YAML structure will corrupt the output.

# pyramidex migrate

Imports the user's existing configuration into the graph. Runs as part of `pyramidex init` or standalone.

## Steps

1. Analyse - AI-driven: `pyramidex migrate` prints the migration export prompt to the terminal.
   Claude (the active session) reads it, uses its tools to discover and analyse all source files,
   and writes `dump.yaml`
2. Dump - `dump.yaml` written to repo root by Claude in step 1
3. Init graph - Python: create `Root` node with queries and schema, create `Domain` nodes
4. Load - Python: read `schema` from `dump.yaml`, create all nodes and relationships generically
5. Verify - Python: re-read graph, compare against `dump.yaml`, report any mismatches
6. Delete dump - ask user whether to delete `dump.yaml`; keep unconditionally if verify failed

## Orchestration

Step 1 runs in the active Claude session - no subprocess, no tool restrictions. Claude already
has the tools it needs (`Read`, `Glob`) and can follow file references autonomously. The prompt
in `docs/prompts/migrate-export.md` is what `pyramidex migrate` outputs to the terminal for
Claude to act on.

Python takes over from step 3. It detects `dump.yaml`, checks `meta.warnings`, then executes
steps 3–5 directly without further AI involvement.

After step 1, the orchestrator checks `meta.warnings` in the dump:

1. No warnings - proceed automatically to step 3
2. Warnings present - print each warning to the user and ask for confirmation to continue.
   If the user declines, exit with a non-zero code and keep `dump.yaml` for inspection.

## dump.yaml

Intermediate artifact produced in step 1 and consumed in step 4. Lives in the repo root. Added to `.gitignore`.

If `dump.yaml` already exists when migrate starts, the user is asked whether to overwrite it, resume
from it (skip step 1), or abort.

The dump is self-describing. It contains a `schema` section that defines all node types, labels,
relationships, and properties. The Python load script is schema-agnostic - it follows whatever is
in the dump without any hardcoded type knowledge. This means custom user-defined types (any structure
the user invented in their config) are migrated correctly alongside standard types.

```yaml
meta:
  created_at: <ISO date>
  pyramidex_version: <int>

domains:
  - <string>

schema:
  - key: <string>              # matches a top-level key in data section
    node_label: <string|list>  # Neo4j label(s) to apply
    root_rel: <string>         # relationship from Root to this node
    properties: [<string>]     # list of properties to map from data
    children:                  # optional - nested node types
      - key: <string>
        node_label: <string|list>
        relationship: <string> # relationship from parent to this node
        properties: [<string>]
        children: [...]        # arbitrarily deep

data:
  <key>:                       # matches schema[*].key
    - <properties>
      <child_key>:             # matches schema[*].children[*].key
        - <properties>
```

### Example - standard types

```yaml
schema:
  - key: sections
    node_label: Section
    root_rel: HAS_SECTION
    properties: [name, domain, description]
    children:
      - key: rules
        node_label: Rule
        relationship: HAS_RULE
        properties: [idx, text]

  - key: memories
    node_label: Memory
    root_rel: HAS_MEMORY
    subtype_field: subtype    # value becomes an additional label e.g. Feedback, Project
    properties: [name, file, domain, description, rule, body, why, how_to_apply, subtype]

  - key: workflows
    node_label: Workflow
    root_rel: HAS_WORKFLOW
    properties: [name, domain, description]
    children:
      - key: triggers
        node_label: Trigger
        relationship: HAS_TRIGGER
        properties: [idx, text]
      - key: steps
        node_label: Step
        relationship: HAS_STEP
        properties: [idx, text, notes]

data:
  sections:
    - name: Code Style
      domain: code
      description: "..."
      rules:
        - {idx: 1, text: "..."}
```

### Example - custom type inferred by AI

```yaml
schema:
  - key: pets
    node_label: Pet
    root_rel: HAS_PET
    properties: [name, species, tricks]

data:
  pets:
    - name: Buddy
      species: dog
      tricks: [sit, stay]
```

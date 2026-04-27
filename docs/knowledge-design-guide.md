# Knowledge Design Guide

## The Core Idea

The config entry point is minimal - a single bootstrap query. All rules, skills, memories,
and workflows live in the graph. The AI discovers only what is relevant to the current task,
loads it on demand, and never misses it because discovery is structural, not optional.

The three-phase session lifecycle is the mechanism that makes this work.

1. Bootstrap: the AI runs `MATCH (r:Root) RETURN r` and reads the result. `Root` carries a
   behavior protocol (`instructions`), a schema reference (`schema`), and the catalog query
   (`catalog`).
2. Catalog load: the AI runs the catalog query once and keeps the result in session memory.
   The catalog returns only each domain's `name` and `description` - a thin routing index.

   ~~~cypher
   MATCH (r:Root)-[:HAS_DOMAIN]->(d:Domain)
   RETURN d.name AS name, d.description AS description
   ~~~
3. Lazy fetch: before executing any task, the AI matches the task against every domain
   description, loads every matching domain that is not yet cached, then proceeds.

Nothing is pre-loaded. Nothing is skipped. The catalog is a routing index, not a content index.
Content lives inside each domain and is fetched only when that domain matches a task.

---

## The Graph Schema

```yaml
nodes:
  Root: [version, schema, catalog, instructions]
  Domain: [name, description]
  Rule: [name, text]
  Skill: [name, description, prompt]
  Memory: [name, body, why, how_to_apply]
  Workflow: [name, description, config]
  Trigger: [idx, text]
  Step: [idx, text, notes]

relationships:
  - {type: HAS_DOMAIN, from: Root, to: Domain}
  - {type: HAS_RULE, from: Root, to: Rule}
  - {type: HAS_SKILL, from: Root, to: Skill}
  - {type: HAS_MEMORY, from: Root, to: Memory}
  - {type: HAS_WORKFLOW, from: Root, to: Workflow}
  - {type: HAS_TRIGGER, from: Workflow, to: Trigger}
  - {type: HAS_STEP, from: Workflow, to: Step}
  - {type: IN_DOMAIN, from: Rule, to: Domain}
  - {type: IN_DOMAIN, from: Skill, to: Domain}
  - {type: IN_DOMAIN, from: Memory, to: Domain}
  - {type: IN_DOMAIN, from: Workflow, to: Domain}
```

`IN_DOMAIN` is many-to-many: any content node can belong to multiple domains.

`Root` is the bootstrap entry point - the only node a fresh session knows how to find.
Its four properties are:

1. `version` - schema version, bumped by migrations applied via `pyramidex upgrade`. Lets
   the system know whether the graph matches the running CLI's expectations
2. `schema` - YAML description of node labels, properties, and relationships. Used by
   `pyramidex reindex` to detect drift after writes
3. `catalog` - the query shown above, run once per session
4. `instructions` - the behavior protocol the AI loads at session start, including the
   authoring gate

Each content node type has a distinct role:

1. `Domain` - defines the scope of a lazy-load unit. Its `description` is the only signal
   the AI uses to decide what to load.
2. `Rule` - a single timeless behavioral constraint.
3. `Skill` - a reusable prompt, the graph equivalent of a slash command.
4. `Memory` - a retained piece of knowledge with reasoning and application context.
5. `Workflow` - a multi-step procedure the AI follows on explicit request.

---

## The Two-Domain System

Every content node belongs to at least two domains:

1. Type domain - `rules`, `skills`, `memories`, or `workflows`. Assigned automatically.
   Enables the user to request "list all my rules" or "show available workflows" at any time.
2. Contextual domain(s) - `code`, `shell`, `deploy`, etc. Assigned based on when the
   content is relevant. Enables lazy loading by work context.

A rule about shell syntax gets `[:IN_DOMAIN]` links to both `rules` and `shell`.
A workflow for ticket creation links to both `workflows` and `ticket`.

The same mechanism handles both axes - no special cases.

---

## How to Design Contextual Domains

A contextual domain is the unit of lazy loading. All content linked to a domain is fetched
together, so the domain must represent a coherent work context - not a topic.

The right question is: "When the AI is about to do X, what set of rules, skills, and memories
does it need simultaneously?" That set defines a domain.

Guidelines:

1. One domain per work surface, not per concept. `code` is one domain because writing YAML,
   Python, and shell scripts all share style rules.
2. Descriptions should route correctly. Since routing is additive (multiple domains can match
   a single task), descriptions do not need to be mutually exclusive - but each one must have
   clear triggers that only fire for tasks where its content actually applies.
3. Cross-cutting concerns (formatting, prose output) deserve their own domain.
4. When a domain grows large, split by sub-context - only when the two halves are never
   relevant at the same time.

### Tier assignment

Every domain carries a tier tag in its description. The tier governs when the domain loads

1. `[broad]` - load whenever the task touches the domain's surface. Acts as a floor: if
   nothing else matches but the task touches files, broad domains load anyway. Use for
   cross-cutting surfaces like `code` and `formatting`
2. `[specific]` - load on concrete evidence in the task (language, tool, environment).
   Use for targeted contexts like `python`, `shell`, `deploy`, `infra`, `ticket`
3. `[meta]` - load only when the user explicitly asks to list or review content of this
   type. Reserved for the four type domains: `rules`, `skills`, `memories`, `workflows`

When in doubt between broad and specific, choose specific. Broad domains load on every
matching task, so misclassifying a narrow domain as broad inflates the per-task cost

---

## How to Write Domain Descriptions

The `description` on a `Domain` node is the most critical text in the system. It is the sole
input to the AI's domain inference step.

A description must satisfy four properties:

1. Tier-tagged - starts with `[broad]`, `[specific]`, or `[meta]`. The tier governs when
   the domain loads. See "Tier assignment" above
2. Trigger-predicate shaped - starts with the word `Load when` followed by concrete
   conditions. Routing is evidence-based, not topic-based. "Load when the file being
   edited is `.py`" routes better than "Python-related tasks"
3. Surface-anchored - names the artifact, tool, or environment, not the abstract concept
4. Trigger-complete - covers every entry point that should activate this domain

Bad: `[specific] General coding tasks`

Good: `[broad] Load when editing any file - source code, configuration (YAML, JSON, TOML,
HCL, INI), scripts, or data files`

Type domain descriptions are fixed and must not be changed:

| Domain      | Description                                                                                  |
| :---------- | :------------------------------------------------------------------------------------------- |
| `rules`     | `[meta] Load when the user asks to list or review rules`                                     |
| `skills`    | `[meta] Load when the user asks to list available skills or slash commands`                  |
| `memories`  | `[meta] Load when the user asks to review or manage memories`                                |
| `workflows` | `[meta] Load when the user asks to follow a process or list available procedures`            |

---

## How to Write Rules

A `Rule` node is a single behavioral instruction. It has two fields: `name` (short label)
and `text` (the instruction itself).

Rules within a domain are a set, not a sequence - there is no ordering.

A rule should satisfy the following properties:

1. Atomic - one rule, one constraint. If a rule contains "and," ask whether the two
   halves could apply independently. If yes, split them.
2. Imperative and unambiguous - "Prefer X" is weak. "Always use X; never use Y" is
   strong. The AI should be able to evaluate compliance without interpretation.
3. Context-scoped - "always do X in bash scripts" not "always do X." Scope explicitly.
4. Falsifiable - a clear pass/fail condition. "Write clean code" cannot be checked.
   "Maximum line length is 119 characters" can.
5. Positively framed where possible - "Always end files with a newline" is easier to
   apply than "never omit the trailing newline."

---

## How to Write Skills

A `Skill` node captures a reusable prompt - the graph equivalent of a slash command.
It has three fields: `name`, `description` (one line - what it does), and `prompt`
(the full prompt text the AI executes when the skill is invoked).

Use skills for tasks the user runs repeatedly with the same intent: code review, security
audit, PR description, test generation. If you find yourself writing the same prompt in
conversation more than once, it belongs in a skill.

---

## How to Write Memories

A `Memory` node captures retained knowledge the AI should carry across sessions.
It has four fields: `name`, `body` (the knowledge itself), `why` (the reason it matters),
and `how_to_apply` (when and where it kicks in).

All four fields are required for a memory to be useful:

1. Without `name`, the memory cannot be looked up or referenced from elsewhere.
2. Without `body`, there is nothing to apply.
3. Without `why`, the AI cannot reason about edge cases.
4. Without `how_to_apply`, the AI cannot recognize when the memory is relevant.

`body` should state the policy directly: "Do not ask for permission to proceed after
presenting a plan." Not "User said stop asking."

`why` should capture the real reason - a past incident, a strong preference, a failure mode.
"User explicitly stated: I will say when to apply" is useful. "User preference" alone is not.

`how_to_apply` should describe the trigger and the correct response: "After presenting a
plan, analysis, or proposed change - stop. Do not ask for permission to proceed."

Record both corrections and confirmations. Systems that only record corrections drift toward
overcaution.

Project memories (time-bound context, decisions, deadlines) must always use absolute dates.
"Next Thursday" becomes "2026-04-24." Relative dates become meaningless after the session ends.
Always include `why` so future sessions can tell whether the memory is still load-bearing.

---

## How to Write Workflows

A `Workflow` node describes a multi-step procedure the AI follows on explicit user request.
It belongs to the `workflows` type domain and optionally to contextual domains.

Use workflows for processes that have failed due to missed steps, processes with external
side effects (pushing code, creating tickets, sending messages), or processes that require
decisions at specific points.

Each `Trigger` node describes the exact conditions under which the workflow applies.
Keep triggers specific enough that they do not fire for similar but different tasks.

Each `Step` node should be one action. Put rationale in `notes`, not in `text`.
The `text` is the instruction; `notes` is the explanation.

---

## The Authoring Gate

Every write-cypher that modifies the graph passes through an authoring gate
before it executes. The gate exists so new content (rules, memories, skills,
workflows) gets classified and attached to domains consistently, instead of
accumulating as orphan nodes that no routing query can find.

The gate has three pieces, all installed by `pyramidex init`:

1. A paragraph in `Root.instructions` that loads the `authoring` domain before
   any write-cypher
2. The `authoring` domain (`[broad]`), which brings the workflow into context
   when the gate fires
3. The `add-content` workflow (6 steps), which the AI walks before issuing
   the write

Reserved names - do not export from another graph, do not modify by hand:

1. domain `authoring`
2. workflow `add-content` and its `Trigger` and `Step` children

These are restored from `src/pyramidex/assets/root-template.yaml` on every
`pyramidex init`. The migrate-export prompt is instructed to skip them so
re-init does not duplicate them.

### What the workflow does

The 6 steps map onto the design rules in the rest of this guide:

1. Gate - decide if the write changes meaning. Skip for typos, bookkeeping
   (Root.version bumps, reindex output), bulk loader writes, and the
   workflow's own internal writes
2. Classify - match the new content against every domain description in the
   cached catalog. Multiple matches are normal and encouraged
3. Name - produce a short label (~5-6 words) from the content. Avoid generic
   labels like "user preference" or "note"
4. Attach - write the node with `IN_DOMAIN` edges to every matched domain.
   Workflows must also create their `Trigger` and `Step` children in the
   same write
5. Refine - update the matched domain's description if the new content
   stretches its scope. Keep the `[tier]` tag
6. Create a new domain only if no existing domain fits. Prefer expanding an
   existing description over creating a new domain

The gate does not re-trigger itself: writes issued by the workflow's own
steps 4-6 pass through without re-entering. That is the only exception

---

## How to Keep the System Healthy

The catalog query is the connective tissue of the system. When adding new nodes, verify
the catalog query returns them before relying on them.

Maintenance rules:

1. When a domain description changes, review content previously routed to it and confirm
   it still matches.
2. When a rule is deleted, check whether any memory's `how_to_apply` references it.
3. When a project memory becomes stale, delete it. Stale memories mislead more than they help.
4. Periodically query for memories with empty `why` fields - these are the most common source
   of degraded quality.

The system is only as reliable as the descriptions and `why` fields. Those two fields are
where meaning lives. Everything else is structure.

---

## Summary: Design Principles

1. The config entry point is minimal. It contains only the bootstrap query. Anything written
   there is always active - use it only for the bootstrap mechanism itself.
2. The catalog is descriptive, not prescriptive. It tells the AI what exists and where;
   it does not tell the AI what to do. The rules, skills, and memories do that.
3. Domain descriptions are the inference layer. Every description is tier-tagged
   (`[broad]` / `[specific]` / `[meta]`) and phrased as a load-when predicate, so routing
   runs on explicit evidence rather than topic association.
4. Every memory carries its reasoning. `why` and `how_to_apply` transform memories from
   lookup tables into judgment inputs.
5. Two domains per node minimum. Type domain enables on-demand listing; contextual domain
   enables lazy loading by work surface. Both use the same mechanism.

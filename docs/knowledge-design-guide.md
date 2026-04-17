# Knowledge Design Guide

## The Core Idea

The config entry point is minimal — a single bootstrap query. All rules, skills, memories,
and workflows live in the graph. The AI discovers only what is relevant to the current task,
loads it on demand, and never misses it because discovery is structural, not optional.

The three-phase session lifecycle is the mechanism that makes this work.

1. Bootstrap: the AI reads the `Root` node, which hands it a behavior protocol and a catalog query.
2. Catalog load: the AI runs the catalog query once and keeps the result in session memory.
   It now knows every domain's name, description, and what content exists inside it.
3. Lazy fetch: before executing any task, the AI infers the relevant domain from the catalog
   and fetches that domain's full data if not already loaded.

Nothing is pre-loaded. Nothing is skipped. The catalog is the discovery layer.

---

## The Graph Schema

```
(:Root)-[:HAS_DOMAIN]───► (:Domain {name, description})
(:Root)-[:HAS_RULE]──────► (:Rule {name, text})
(:Root)-[:HAS_SKILL]─────► (:Skill {name, description, prompt})
(:Root)-[:HAS_MEMORY]────► (:Memory {name, body, why, how_to_apply})
(:Root)-[:HAS_WORKFLOW]──► (:Workflow {name, description})
                             -[:HAS_TRIGGER]──► (:Trigger {idx, text})
                             -[:HAS_STEP]─────► (:Step {idx, text, notes})

(:Rule)─────[:IN_DOMAIN]──► (:Domain)   ← many-to-many
(:Skill)────[:IN_DOMAIN]──► (:Domain)   ← many-to-many
(:Memory)───[:IN_DOMAIN]──► (:Domain)   ← many-to-many
(:Workflow)─[:IN_DOMAIN]──► (:Domain)   ← many-to-many
```

Each node type has a distinct role.

- `Domain` — defines the scope of a lazy-load unit. Its `description` is the only signal
  the AI uses to decide what to load.
- `Rule` — a single timeless behavioral constraint.
- `Skill` — a reusable prompt, the graph equivalent of a slash command.
- `Memory` — a retained piece of knowledge with reasoning and application context.
- `Workflow` — a multi-step procedure the AI follows on explicit request.

---

## The Two-Domain System

Every content node belongs to at least two domains:

1. **Type domain** — `rules`, `skills`, `memories`, or `workflows`. Assigned automatically.
   Enables the user to request "list all my rules" or "show available workflows" at any time.
2. **Contextual domain(s)** — `code`, `shell`, `deploy`, etc. Assigned based on when the
   content is relevant. Enables lazy loading by work context.

A rule about shell syntax gets `[:IN_DOMAIN]` links to both `rules` and `shell`.
A workflow for ticket creation links to both `workflows` and `ticket`.

The same mechanism handles both axes — no special cases.

---

## How to Design Contextual Domains

A contextual domain is the unit of lazy loading. All content linked to a domain is fetched
together, so the domain must represent a coherent work context — not a topic.

The right question is: "When the AI is about to do X, what set of rules, skills, and memories
does it need simultaneously?" That set defines a domain.

Guidelines:

1. One domain per work surface, not per concept. `code` is one domain because writing YAML,
   Python, and shell scripts all share style rules.
2. Descriptions should be mutually exclusive enough for correct routing. A description like
   "any file editing" would match everything and defeat lazy loading.
3. Cross-cutting concerns (formatting, prose output) deserve their own domain.
4. When a domain grows large, split by sub-context — only when the two halves are never
   relevant at the same time.

---

## How to Write Domain Descriptions

The `description` on a `Domain` node is the most critical text in the system. It is the sole
input to the AI's domain inference step.

A description must satisfy three properties:

1. **Discriminative** — distinguishes this domain from all others.
2. **Surface-anchored** — describes the artifact being worked on, not the abstract concept.
   "Writing or reviewing Python code" is better than "Python-related tasks."
3. **Trigger-complete** — includes all entry points that should activate this domain.

Bad: "General coding tasks."

Good: "Writing, reviewing, or refactoring any file — source code, configuration
(YAML, JSON, TOML, HCL, INI), scripts, or data files."

Type domain descriptions are fixed and must not be changed:

| Domain | Description |
| :----- | :---------- |
| `rules` | All behavioral rules — load when the user asks to list or review rules |
| `skills` | All skills — load when the user asks to list available skills or slash commands |
| `memories` | All retained memories — load when the user asks to review or manage memories |
| `workflows` | All workflows — load when the user asks to follow a process or list available procedures |

---

## How to Write Rules

A `Rule` node is a single behavioral instruction. It has two fields: `name` (short label)
and `text` (the instruction itself).

Rules within a domain are a set, not a sequence — there is no ordering.

A rule should satisfy the following properties:

1. **Atomic** — one rule, one constraint. If a rule contains "and," ask whether the two
   halves could apply independently. If yes, split them.
2. **Imperative and unambiguous** — "Prefer X" is weak. "Always use X; never use Y" is
   strong. The AI should be able to evaluate compliance without interpretation.
3. **Context-scoped** — "always do X in bash scripts" not "always do X." Scope explicitly.
4. **Falsifiable** — a clear pass/fail condition. "Write clean code" cannot be checked.
   "Maximum line length is 119 characters" can.
5. **Positively framed where possible** — "Always end files with a newline" is easier to
   apply than "never omit the trailing newline."

---

## How to Write Skills

A `Skill` node captures a reusable prompt — the graph equivalent of a slash command.
It has three fields: `name`, `description` (one line — what it does), and `prompt`
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
- Without `body`, there is nothing to apply.
- Without `why`, the AI cannot reason about edge cases.
- Without `how_to_apply`, the AI cannot recognize when the memory is relevant.

`body` should state the policy directly: "Do not ask for permission to proceed after
presenting a plan." Not "User said stop asking."

`why` should capture the real reason — a past incident, a strong preference, a failure mode.
"User explicitly stated: I will say when to apply" is useful. "User preference" alone is not.

`how_to_apply` should describe the trigger and the correct response: "After presenting a
plan, analysis, or proposed change — stop. Do not ask for permission to proceed."

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

## How to Keep the System Healthy

The catalog query is the connective tissue of the system. When adding new nodes, verify
the catalog query returns them before relying on them.

Maintenance rules:

1. When a domain description changes, review content previously routed to it and confirm
   it still matches.
2. When a rule is deleted, check whether any memory's `how_to_apply` references it.
3. When a project memory becomes stale, delete it. Stale memories mislead more than they help.
4. Periodically query for memories with empty `why` fields — these are the most common source
   of degraded quality.

The system is only as reliable as the descriptions and `why` fields. Those two fields are
where meaning lives. Everything else is structure.

---

## Summary: Design Principles

1. The config entry point is minimal. It contains only the bootstrap query. Anything written
   there is always active — use it only for the bootstrap mechanism itself.
2. The catalog is descriptive, not prescriptive. It tells the AI what exists and where;
   it does not tell the AI what to do. The rules, skills, and memories do that.
3. Domain descriptions are the inference layer. They must be specific, surface-anchored,
   and mutually exclusive enough for correct routing.
4. Every memory carries its reasoning. `why` and `how_to_apply` transform memories from
   lookup tables into judgment inputs.
5. Two domains per node minimum. Type domain enables on-demand listing; contextual domain
   enables lazy loading by work surface. Both use the same mechanism.

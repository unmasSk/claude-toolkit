---
name: unmassk-groundhog
version: 1.0.0
description: >
  Use when the user asks to "run the groundhog protocol", "protocolo marmota",
  "protocolo día de la marmota", "pásale la marmota", "what repeats in this project",
  "what do we do every session", "should this be a skill", "turn this into a skill",
  "what skills is this project missing", "qué se repite aquí", "esto debería ser una skill",
  "convierte esto en skill", "qué skills le faltan a este proyecto", or wants to find
  what a project does or needs REPEATEDLY — across sessions, git memory, documents,
  agent memories, commit history — and turn the uncovered repetitions into skills.
  Agnostic on purpose — a candidate can be a procedure, a block of knowledge, or a
  recurring operation. Analysis is read-only and proposes at most 1-3 candidates with
  cited evidence; a skill is created only after the owner approves it. NOT for one-off
  facts (git memory), how the owner wants to be worked with (a rule), or auditing
  memory content for rot (unmassk-memory-doctor).
---

# Protocolo Día de la Marmota (Groundhog Protocol)

One open question, asked of the whole project, with no category in mind:

> **"What does this project do — or need to know — repeatedly, every session or nearly, that no skill already covers?"**

Anything can be the answer: a procedure (a release, a deploy), a block of knowledge (a machine's access and layout), a recurring operation. The scout looks AT everything and lets the repetition surface.

**Read-only until approval.** The scout proposes; it creates nothing until the owner picks.

## Phase 1 — Inventory the repetition signals

Sweep every place where repetition leaves traces. Read files whole — grep only to locate.

| Source | Repetition looks like |
|---|---|
| `gitmem zones list` + `gitmem search` on the largest zones | The same procedure or facts described in more than one note |
| `gitmem rule` | A correction the owner had to repeat |
| Next history — `git log --grep='\[NEXT\]' --oneline` | What every session start and close actually re-reads or re-does |
| CLAUDE.md, root and nested | Anything re-explained to every session |
| Agent memories — `.claude/agent-memory/<agent>/*.md` (in the repo, versioned) | A fact an agent wrote down came up more than once |
| `git log --oneline -50` | Recurring kinds of commits: releases, deploys, same-area fixes |
| Project docs and operational notes | Procedures and system descriptions sessions keep returning to |

## Phase 2 — Check coverage first

List the skills that already exist: the project's own (`.claude/skills/`) plus installed plugin skills. For each repetition found: **covered** → name the covering skill, discard; **not covered** → candidate.

## Phase 3 — Qualify each candidate

All three must hold — when one fails, say where that knowledge belongs instead:

| Question | If NO → it belongs in… |
|---|---|
| **Stable?** — survives weeks unchanged | git memory (dated, carries the why) |
| **Mechanical?** — a HOW: commands, paths, specs, steps | a memory note (a why/decision) or a rule (how the owner works) |
| **Recurrent?** — real evidence, with source and count | nothing — one-offs are not automated |

Every fact must come from a source that can be opened: a file, a note, a command's output. A gap is reported as a gap, never filled in.

## Phase 4 — Report, then wait

At most **1-3 candidates**, ordered by real frequency. Template:

```markdown
## Skill candidates for <project>

### 1. <name>
**What repeats**: <one line>
**Evidence**: <source + count>
**Would contain**: <content, and the exact files/notes it comes from>
**Trigger words**: <the words the user actually says — they become the description>

### Discarded, and where they live instead
- <repetition> → covered by <skill> / belongs in git memory: <why>
```

The owner can ask for more. **The owner picks; only then is anything created.**

## Creating an approved skill — the craft

Distilled from Anthropic's official `skill-creator`. Follow it so every generated skill respects the canonical format.

**Anatomy:**

```
skill-name/
├── SKILL.md              (required: YAML frontmatter + instructions)
└── optional resources
    ├── scripts/          (executable code for deterministic tasks)
    ├── references/       (docs loaded only when needed)
    └── assets/           (templates, files used in output)
```

**The three loading levels** — write for them:
1. **name + description** — always in context (~100 words). ALL "when to use" info lives here, none in the body.
2. **SKILL.md body** — loads when the skill fires. Keep it under 500 lines; near the limit, push detail into `references/` with clear pointers.
3. **Resources** — loaded only as needed; a reference file over 300 lines gets a table of contents.

**The description is the trigger — write it "pushy".** Claude tends to under-trigger skills, so the description states what the skill does AND every context where it should fire, using **the owner's own trigger words** (the scout collected them in Phase 4). Cover casual phrasings, not just the formal name.

**The body:**
- Imperative form. Explain the WHY behind each instruction instead of rigid all-caps MUSTs — a skill that explains its reasoning generalizes; one that only commands overfits.
- Include 1-2 concrete examples (input → output) and exact output templates where format matters.
- If the same helper work would be redone on every use, bundle it once as a script in `scripts/` and point to it.
- Content only from the cited sources; point to files that change rather than copying them in. Never invent content. Never copy a secret in unless the project already keeps it written by the owner's explicit decision.

**Verify before handing over:** write 2-3 realistic prompts a real session would say (casual wording, typos included) and check the skill fires on them and NOT on near-miss prompts that merely share keywords. Then show the owner the result.

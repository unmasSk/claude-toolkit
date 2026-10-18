---
name: outside-sources
description: Where the good sources are for agent/subagent topics outside the repo, and which ones not to trust — each with the date it was read.
metadata:
  type: reference
---

All read 2026-10-16 unless stated. Re-read before quoting any figure from them.

## Trust

- **Claude Code subagents, official:** https://code.claude.com/docs/en/sub-agents — has the full
  frontmatter field table (tools, `disallowedTools`, model, `permissionMode`, `maxTurns`, skills, hooks,
  memory, background, `omitClaudeMd`, effort, isolation, …) and the built-in Explore details (read-only,
  skips CLAUDE.md, quick/medium/very thorough). Read the first 100,000 of 110,964 characters; the last
  ~11,000 were not read.
- **Codex subagents, official:** https://learn.chatgpt.com/docs/agent-configuration/subagents
  (`developers.openai.com/codex/subagents` answers 308 and redirects there). Built-in `explorer`;
  custom agents are TOML (`name`, `description`, `developer_instructions`); a custom agent file cannot
  override sandbox or approval settings, so "read-only" is not guaranteed by the agent definition.
- **Anthropic's own explorer example:**
  https://github.com/anthropics/claude-code/blob/main/plugins/feature-dev/agents/code-explorer.md —
  `code-explorer`: 4-phase trace, output = entry points `file:line`, flow, key files; no output template.

## Do not trust for figures

- Third-party guides (CodeSignal lesson, skills.sh listing, Morph docs) say Explore runs on Haiku with only
  Read/Glob/Grep. The official page says it inherits the main conversation's model. Official wins.
- **VoltAgent awesome-claude-code-subagents** (https://github.com/VoltAgent/awesome-claude-code-subagents):
  only the README index was read, not individual agent files. It lists no dedicated explorer or dead-code
  agent.
- **Serena MCP** (official repo `github.com/oraios/serena`): only secondary articles were read; the repo
  itself was not. Language-count claims differ between sources (30+ vs 40+). UNVERIFIED.

## Local reference repo

- `.ref-repos/spec-kit` (read 2026-07-04, still present 2026-10-16, contents not re-read): its
  "Constitution Check gate" is a prose placeholder the AI fills in (`plan-template.md`); the only real
  automated gate step is `workflows/steps/gate/__init__.py`, a human approve/reject pause. Use it to tell
  deterministic code gates from instructions-as-gates.

## CLAUDE.md for real products (read 2026-10-18)

- Official: https://code.claude.com/docs/en/memory (target <200 lines; @imports load at launch, no saving; path rules in `.claude/rules/` with `paths:` load on file touch; root CLAUDE.md survives /compact) and https://code.claude.com/docs/en/best-practices (include/exclude table; "would removing this cause mistakes?").
- Big products moved to AGENTS.md with a 1-line CLAUDE.md (`@AGENTS.md`): sentry, supabase, n8n, grafana, trigger.dev, formbricks, posthog. Fetch raw `.../AGENTS.md` for the real text. Good real ones: twentyhq/twenty (CLAUDE.md, 60 lines), openstatusHQ/openstatus (AGENTS.md 102), getsentry/sentry (129), supabase (75).

## Writing for models (read 2026-10-18)

- Official, trusted: https://code.claude.com/docs/en/memory ("Write effective instructions": concrete, <200 lines, headers+bullets, no contradictions), https://code.claude.com/docs/en/best-practices (include/exclude table; emphasis on ONE skipped line), https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices (description what+when, <1,024 chars, SKILL.md <500 lines, one level of references, consistent terms), https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices (positive form, reason in a clause, dial back CRITICAL/MUST).
- Real repos: openstatus AGENTS.md is the best verbatim model (whole file read). WebFetch refuses to quote Twenty/Sentry/Supabase whole: only summaries.
- Guide written: .claude/informes/guia-escritura-para-modelos-2026-10-18.md

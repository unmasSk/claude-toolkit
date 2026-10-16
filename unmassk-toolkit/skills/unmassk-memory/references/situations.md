# Which of the three situations you are in

Check this once, at the start, before writing anything. The three look alike from the outside and behave very differently.

| | How you tell | What it means |
|---|---|---|
| **New project** | No memory yet: nothing to read at boot, and no zone list | Nothing to recover. The first note creates the memory. **Zones do not exist yet**: the first ones get created as they are needed |
| **Project already running** | Memory reads back, zones are there | Ordinary work: read before building, save when the signal fires |
| **Project carrying memory from a previous or different system** | The history holds memory, but none of it reads back through these commands | **Nothing is lost and nothing is migrated.** That memory is distilled once, additively — the earlier commits are never touched. Until that pass runs, the past is only reachable by reading the raw history |

**Each agent's own memory is a fourth thing entirely** — what it learned about this codebase, kept apart from the project's (only the agents that build keep one; the three that judge do not, see R-021). Nobody checks whether it is still true, and it rots the same way: `references/agent-memory-compaction.md` is the pass that fixes it, one agent at a time, each compacting only its own.

**The third one is not ordinary work and does not happen on its own.** It is a deliberate pass: harvest the zones first and get them approved, then distil oldest to newest, each round reading what the previous ones produced. The protocol is in `references/distill.md` — read it when that pass is what you are doing, not before.

**Never mix them up.** Treating the third as if it were the first leaves years of decisions unreachable while the memory looks perfectly healthy — the worst of the three, because nothing warns you.

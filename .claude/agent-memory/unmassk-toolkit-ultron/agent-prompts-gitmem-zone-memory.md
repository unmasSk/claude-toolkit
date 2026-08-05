---
name: agent-prompts-gitmem-zone-memory
description: Fixing the 9 agent prompts' Step-5 zone-memory mechanism (memoria-v2) -- CLAUDE_PLUGIN_ROOT is inert in Bash, zsh glob-nomatch crash, and search --file structurally never finds a source file's notes
metadata:
  type: project
---

## CLAUDE_PLUGIN_ROOT does not exist in the Bash tool's shell -- verified live, not assumed

`${CLAUDE_PLUGIN_ROOT}` only gets substituted by Claude Code for **hooks.json
"command" entries** (it spawns those subprocesses itself with the var
injected into `os.environ`, confirmed by `hooks/pre-validate-commit-trailers.py:121`
reading it via `os.environ.get`). It is **NOT** exported into the shell a
Bash tool call runs in -- confirmed by launching a real
`unmassk-toolkit:ultron` subagent and running
`echo "[$CLAUDE_PLUGIN_ROOT]"; env | grep -i CLAUDE_PLUGIN`: both empty.
CLAUDE.md's own boot step 4 (`Read CALIBRATION.md:
${CLAUDE_PLUGIN_ROOT}/skills/...`) rests on the same false premise -- flagged,
not fixed (out of scope: that task was `unmassk-toolkit/agents/*.md` only).
Any future instruction that wants an agent's Bash command to find "my own
plugin's install root" needs the dev-mode-path + cache-glob fallback below,
never a bare `${CLAUDE_PLUGIN_ROOT}` in a bash block.

## zsh crashes on a no-match glob -- `ls -d pattern*` is not portable here

This repo's shell is zsh (`env` confirms it), and zsh's default `nomatch`
option makes an unmatched glob **abort the command** with
`no matches found: ...` instead of passing the literal string through (bash's
behavior). `ls -d "$HOME"/.claude/plugins/cache/*/unmassk-toolkit/*/bin/gitmem`
reproduced this live when the plugin cache had zero matches. Fix: use
`find "$DIR" -path "*/pattern*" 2>/dev/null | sort -V | tail -1` instead --
`-path` takes a literal string argument, never shell-expanded, so a
zero-match search returns empty output with exit 0, never an error.

**Reusable resolution snippet** (now in all 9 `unmassk-toolkit/agents/*.md`
Step 5 blocks, for locating `bin/gitmem` from an arbitrary project):
```bash
GITMEM="$GIT_ROOT/unmassk-toolkit/bin/gitmem"          # dev mode: inside this repo
[ -f "$GITMEM" ] || GITMEM="$(find "$HOME/.claude/plugins/cache" -path "*/unmassk-toolkit/*/bin/gitmem" 2>/dev/null | sort -V | tail -1)"
if [ -n "$GITMEM" ]; then python3 "$GITMEM" search <word>; else echo "gitmem: command not found -- could not check zone memory" >&2; fi
```
Verified end-to-end in a real *other* repo, both with a fake cache tree
(built by copying `unmassk-toolkit/bin` + `lib` + `.claude-plugin/plugin.json`
into a scratch `$HOME`) and against the real (currently gitmem-less) cache.

**CORRECTION, 2026-08-03 (2nd review round):** this file's own snippet above
used to show `[ -n "$GITMEM" ] && python3 ... || echo "gitmem not found"`, but
what actually shipped in all 9 prompts was the bare
`[ -n "$GITMEM" ] && python3 "$GITMEM" search ...` -- **no `|| echo` at all**.
Consequence, reproduced live: when `$GITMEM` resolves to empty (the normal
case today -- `bin/gitmem` and `bin/memory/` are uncommitted, so no installed
cache has them), the `&&` guard is false, the right side never runs, and the
line prints **nothing**, silently -- exactly the failure this project's
threat model forbids (a lookup that never ran must never look identical to a
lookup that ran and found nothing). Trusting this memory's own snippet as
"what's in the file" instead of re-grepping was itself the mistake this repo's
CLAUDE.md rule #1 warns about. Fixed by replacing the `&&`/`||` chain with an
explicit `if/else` in all 9 files (6 comment-block boot sections + 3 inline
prose sentences in argus/cerberus/bilbo) -- `else echo "gitmem: command not
found -- could not check zone memory" >&2`. Also note: a bare
`A && B || C` is a footgun even with the echo present -- if `B` itself exits
non-zero (e.g. `python3` found but the search itself errors), `C` fires too,
falsely claiming "not found" when the command *was* found. `if/else` avoids
that ambiguity entirely; prefer it over `&&`/`||` chaining for this kind of
presence check whenever there's a real command on the right side.

## `gitmem search --file <path>` structurally cannot find a note about a real source file

Proposed by two reviewers as the fix for "git log --follow never shows
`[ID][zone]` on a code file" (true, confirmed: those tags only appear on
`notes.write()`'s own commits). But `search --file` is *also* broken for the
stated goal, for a different, deeper reason -- verified live, not assumed:

`gitcmd.commit(message, paths, ...)` commits **exactly** `paths` (raises if
empty) -- `notes.write()` calls it with `[index_path]` only, the memory
index file under `.claude/project-memory/`, **never** the code file the note
is conceptually about. So `query.by_file(path)` (`git log -- <path>`) can
only ever return commits that literally diffed `<path>` -- and a memory-note
commit never does, by construction, for any file outside the index. Live
repro: created a zone, committed a real code file (`app.py`, plain
`feat` commit), wrote a real `I` note about it keyed `security`+`antipattern`
in that exact zone -- `gitmem search --file app.py` still printed
`"ninguna nota tocó app.py"`. Not a missing-data problem; the mechanism
cannot work for this case, ever.

**The actual working bridge**, verified live in the same repro: a **word**
search on the file's own basename/module, `gitmem search app.py` (not
`--file`) -- `query.by_word` full-text-matches the raw commit body of every
note regardless of zone, and the note's own description text happened to
say "app.py", so it surfaced the right zone + the incident. This is the
mechanism now written into all 9 agent prompts' Step 5, replacing both the
git-log-on-the-code-file claim and the `--file` suggestion. Caveat stated
explicitly in the prompts: it is a text-match heuristic (works only if a
note's own text happens to mention the file/module name), not a guaranteed
lookup -- "nothing found" is the expected, normal case for most files and is
handled as such, never a crash.

**Decision, 2026-08-03 (2nd review round):** `bin/memory/search.py --file`
itself was left in place, not removed -- removing it would touch the CLI
grammar the spec/PIEZAS/TESTIGO docs declare, which is other agents' surface,
and no test in `test_search_script.py` exercises `--file` at all (checked --
zero references), so nothing regresses either way. Instead both
`_render_by_file`'s empty-result message and the module docstring now state
the structural reason explicitly (a note's commit only ever touches the
memory index file, never the code file it discusses) and point at the word-
search workaround, so `search.py --file real_file.py` no longer reads like a
legitimate "no notes on this file" (data) when the true state is "this entry
point cannot find notes on a code file" (limitation of the option itself).

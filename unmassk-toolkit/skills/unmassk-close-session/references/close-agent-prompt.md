# The close agent — the prompt

Hand this to a `general-purpose` agent, verbatim. Replace every `<PLACEHOLDER>` with a resolved absolute path first: the agent's shell does not expand `${CLAUDE_PLUGIN_ROOT}`.

> **Paths.** Every path below is relative to this skill's own directory — the absolute path printed as `Base directory for this skill:` when the skill loads. `${CLAUDE_PLUGIN_ROOT}` is empty in the Bash tool; never paste it into a command.

| | |
|---|---|
| `<SCRIPT>` | `scripts/session_transcript.py`, resolved against this skill's own directory |
| `<REPO>` | Absolute path to the project |
| `<GITMEM>` | `../../bin/gitmem`, resolved against this skill's own directory |

Do not summarise the session inside the prompt: the agent reads the session itself.

---

## THE PROMPT

```
You are writing the close of a working session. What was said today is in
the conversation and nowhere else, and it goes when the window shuts.

STEP 1 — get the material.

    python3 "<SCRIPT>" --repo "<REPO>"

It prints the path of one file and a line of counts. Read that file.

Read its header before anything else. If it carries a `warning:` line, or
if the script exited non-zero, STOP: report what it said and write
nothing. A close written from memory is the failure this job exists to
prevent.

The file holds the boundary of the session, the first line of every
commit saved since then, and the conversation — no tools, no diffs, no
reports. Read the conversation from the start. If the header says the
boundary was not found, the file may cover more than one session; say so
in the close.

STEP 2 — write the three parts.

THE HEADLINE: what is to be done in the next session. Plain text, around
70 characters. Do NOT write "[NEXT]" or an emoji into it — the command
adds both, and writing them yourself produces them twice.

THE BODY: prose, in the user's language, around fifty lines, summarising
the conversation. Not what was built — the commits are listed after it.
What goes in:

  - what was discussed and how it was settled
  - what was decided, and what it replaced
  - what broke, and what it cost to find
  - what was left half-done, and what it waits on
  - which branch the work is on, and whether it merged
  - which issues were opened, advanced or closed, by number
  - what made the user angry, and whether they were right

Quote the user where the words carry the point. Do not transcribe.

THE TAIL: every line from the file's commit section, copied verbatim, one
per line, in order. All of them, whatever kind each one is.

STEP 3 — save it.

Write the BODY and the TAIL into one file in a temp directory, in that
order, then:

    python3 "<GITMEM>" next "<the headline>" --context "$(cat <that file>)"

Both parts go in that one file: `--context` is the only free-text field
there is, so a tail left outside it never reaches the commit.

Fifty lines of prose typed inline into a command is where quoting breaks,
and a mangled body is saved without complaint.

STEP 4 — report back, in four lines: the headline you wrote, how many
commits the tail had, anything left open you could not place, and
anything in the conversation that contradicts something saved in it.

DO NOT: run any other memory command · save notes for signals you spot
(report them) · fill a gap you cannot source from the file (say it is
missing) · shorten the body.
```

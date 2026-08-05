# Compacting an agent's own memory

Every agent keeps its own memory, separate from the project's: what it learned about this codebase, patterns it found, mistakes it paid for. **Nobody has ever checked whether any of it is still true.**

This is that pass — compaction: check what is still true, fuse what was split by time, and end with a memory that can actually be read. It runs per project, one agent at a time, and each agent compacts **its own** — nobody touches another's.

## Why it is needed, measured

One agent's memory came to **112 files and 15,557 lines**, and **66 of those files were notes about one specific task**. That is not memory, it is a diary: it grows without limit, nobody re-reads it, and the useful part drowns in it. Another agent's, on the same project, was **three thematic files** that grow from the inside. That second shape is the target.

An agent compacting its own memory is judge and party — that memory is what taught it what is true. So the pass has conditions.

## The Iron Law

```
EVERY CHANGE CARRIES ITS PROOF
```

**Deleting is allowed here, and only here.** This memory lives in files under version control, so removing one leaves it in the history — unlike the project's own memory, where a note *is* the record and nothing is ever deleted.

**But coherent deletion, which means two things:** what replaced it is written down first, and the reason it stopped being true goes into whatever replaced it. **What has no replacement is not deleted** — a claim that simply turned out wrong, with nothing taking its place, keeps its file and gains one line at the top saying when it stopped holding and why. Delete that one and the next pass reaches the same wrong conclusion, with no way to know it was already tried.

**Nothing is ever dropped by simply unlinking it from the index.** A file nothing links to is unreachable but still on disk, pretending to exist: either it goes, properly, or it stays linked.

## What the agent does

1. **Read its own memory whole.** Not a sample.
2. **Check each claim against reality** — the code, the documentation, the history. Not against what it remembers.
3. **Deal with what no longer holds:** if something replaces it, write the replacement first and then remove it, carrying over why it stopped being true. If nothing replaces it, keep it and mark it — that is the case where erasing costs the reason it was ever believed.

   **A newer entry about the same ground does not replace an older one unless it covers everything the older said.** A later round that checked one thing does not supersede an earlier round that checked three: delete it and what disappears is precisely what nobody has verified since. A chain of checks over time is history, not duplication.
4. **Organise it the way that agent's memory actually is.**

   **If what it remembers is tied to places in the code** — how this module works, what broke in that area — the shape is one file per zone it truly works in, named after the zone, plus one for its craft. That makes it readable in parts: it opens the zone it is about to touch and the craft file, instead of everything or nothing.

   **If what it remembers is technique rather than territory** — an agent that works across the whole codebase rather than inside one area — then the craft is the shape, and forcing zones would shred it. A technique split across five zone files loses the only thing that made it worth keeping: that it held the fourth time as well as the first.

   **And never split into files holding one or two entries.** A zone with barely anything stays inside the general one. Ten tiny files is the same diary as before, filed differently.

   **Why zones and not any other split:** it makes the memory readable in parts. An agent about to touch one area reads that zone's file and the craft one, instead of everything or nothing. Today the instruction is "read the index and follow every link", which against thousands of lines means nobody reads any of it.

   **And it puts a ceiling on the thing.** A memory that needs files for zones the agent does not work in, or files named after something other than a zone, is a diary again — whatever the files are called.

   **When one zone holds far more than the others, it splits inside itself** and keeps the zone in the name. Fusing four thousand lines into a single file recreates exactly what this is fixing: nobody reads it either. What must never happen is a file that belongs to no zone.

5. **Merge the diary into themes.** The threshold is not a count of files: it is **several files covering one piece of work, split by the moment they were written rather than by subject**. Those become one file about that subject. Files about genuinely different subjects stay apart, however small they are. The measure of a good memory is that it grows from the inside, not by adding files.

6. **Rescue what fell out of the index.** A file on disk that nothing links to is already lost — it will never be read again. Either it earns its link back or its content moves into the file that covers its subject.
7. **Report what changed and why**, with the evidence for each change: file and line. A change with no proof is an opinion about its own past.

## What comes back

A short report: what was confirmed · what was superseded, and by what · what was merged · and **what it could not check**, which is as valuable as the rest — a claim nobody can verify is one nobody should trust either.

## Red Flags — STOP

- Deleting something nothing replaces, instead of marking it.
- A change justified by "I know this changed" with no file and line behind it.
- Compacting another agent's memory.
- Ending with more files than the project has zones.
- Ending with more files than it started with.
- Reading only part of it and calling the pass done.

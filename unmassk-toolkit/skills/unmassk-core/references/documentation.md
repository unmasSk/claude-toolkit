# Documentation discipline: every new thing goes in THREE places

When you ship anything new — a feature, a script, a flag, a convention, a hook, a decision — document it for all three audiences (a capability nobody can discover is dead weight):

1. **Humans visiting the repo** → the README (and deeper docs for walkthroughs).
2. **Us, working** → the roadmap / working docs.
3. **Claude at load** → the relevant skill and/or instruction file, so a future session knows it exists.

The duplication is deliberate. Because manual duplication drifts, do all surfaces **in the same commit**, and never leave a new capability documented in only one place. When in doubt, hand the sync to **Alexandria** and tell her: all three audiences.

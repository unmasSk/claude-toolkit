# Reference repos (`.ref-repos/`)

These repos are cloned locally for reference while building toolkit skills. The repos
themselves are **gitignored** (they don't travel between machines) — only this manifest
is tracked, so any machine can re-clone them.

**To re-download on another machine**, from the repo root:

```bash
mkdir -p .ref-repos && cd .ref-repos
git clone --depth 1 https://github.com/Eyadkelleh/awesome-skills-security
git clone --depth 1 https://github.com/transilienceai/communitytools
git clone --depth 1 https://github.com/Orizon-eu/claude-code-pentest
git clone --depth 1 https://github.com/blader/humanizer
git clone --depth 1 https://github.com/lguz/humanize-writing-skill
git clone --depth 1 https://github.com/kjmagnan1s/anti-slop
```

## Sources

| Repo | URL | Purpose |
|------|-----|---------|
| `awesome-skills-security` | https://github.com/Eyadkelleh/awesome-skills-security | Source material for the pentesting skill (#19) |
| `communitytools` | https://github.com/transilienceai/communitytools | Source material for the pentesting skill (#19) |
| `claude-code-pentest` | https://github.com/Orizon-eu/claude-code-pentest | Source material for the pentesting skill (#19) |
| `humanizer` | https://github.com/blader/humanizer | Source material for the humanize-text skill (base catalog, MIT) |
| `humanize-writing-skill` | https://github.com/lguz/humanize-writing-skill | Source material for the humanize-text skill (3-pass method + patterns dictionary, MIT) |
| `anti-slop` | https://github.com/kjmagnan1s/anti-slop | Source material for the humanize-text skill (protect-list seam + living-corpus, MIT) |

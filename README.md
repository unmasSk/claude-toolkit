<h1 align="center">unmassk toolkit</h1>

<p align="center">
  <strong>Claude Code that remembers what you told it — and a crew of nine agents that catch each other's mistakes before you ever see the code.</strong>
</p>

<p align="center">
  One install. No config file to maintain. You give instructions, Claude delivers.
</p>

---

## The problem this solves

Every new Claude Code session starts from zero. You repeat the same preference for the third time. You re-explain a decision you already made last week. Claude writes code without reading how the rest of the project already solved the same thing. And when the same model reviews its own work, that's not a review — it's the author marking their own homework.

This toolkit gives Claude a memory that survives you closing the laptop, and a team that doesn't grade itself.

---

## Proof, not promises

Marketing copy is cheap. Here's what this system actually caught — on itself, this week, with the receipts still in the git history.

**A search bug quietly wiped out an agent's memory, and nothing on screen said so.** `gitmem search ultron` returned 0 real memories. `gitmem search Ultron` — same word, one capital letter — returned 10. Every agent whose own name has a capital letter was reading a near-empty memory and concluding, wrongly, that nothing had ever been decided. No crash, no warning. Found by reading the code, fixed same day, with a test that checks both cases so it can't come back quiet.

**One of the nine agents had been writing to a memory it never read.** Bilbo, the agent that explores unfamiliar code, believed it automatically received a block of "dead ends already ruled out" at the start of every session. It didn't — that channel had been shut off months earlier, and nothing told Bilbo. So it kept writing down what it ruled out, session after session, and reading back none of it. The exact institutional-memory loss this whole project exists to prevent — happening inside the project itself, until someone actually read the agent's own instructions instead of trusting what they claimed.

**The most common moment of all — a brand-new install, first commit, zero memory — crashed instead of showing "nothing yet."** The security reviewer found it, and it was confirmed by running it, not by reading the diff: the very first thing a new user would see was a raw Python error. Fixed the same session it was found, with a test that pins the empty-state as valid instead of a crash.

**A concurrency fix passed 60 out of 60 tests run directly against the function — then failed 16 out of 30 tries run the way a person actually triggers it.** Calling the function in-process and typing the two ordinary commands a user types are not the same test. The fix that looked perfect from the inside had a real gap that only showed up from the outside — which is now the standard this whole toolkit tests itself against: measure how the user enters, never how the code is called from within.

None of these shipped as bugs users hit. They shipped as regression tests, the day they were found, because the crew that builds this toolkit is the same crew documented below.

---

## What you get

**Memory that's actually memory.** Decisions, corrections, and rules persist as git commits — readable, diffable, yours. Working across two machines, it fetches and warns you when local is behind before you start (it never pulls on its own; bringing the work over stays your call). One command, `/remember`, puts your own rules file in front of Claude and every line becomes binding from that moment.

**A groundhog-day detector.** The Groundhog Protocol (`unmassk-groundhog`) asks one open question of any project: what does this do repeatedly, every session, that no skill already covers? It sweeps the git memory, the agents' own memories, the instruction files and the commit history, and proposes at most 1-3 skill candidates with cited evidence — a skill is only created after the owner approves it.

**Nine agents, one job each, and they don't take each other's word for it.** Bilbo explores, Ultron implements, Dante tests, Cerberus and Argus review code quality and security in parallel, then Moriarty attacks whatever they let through — that order never gets shortened. It's not a formality: Moriarty has caught four real problems the first two reviewers already approved, including a silent loss of saved memory while every test stayed green, and a session start that fed one project's plan into a different one. House diagnoses when something breaks anyway, Yoda gives the final verdict, Alexandria documents what's real.

**Two structured pipelines instead of improvisation.** An 8-step build pipeline (triage → brainstorm → research → plan → execute → verify → document → close) for features and fixes. A 14-step enterprise audit with a weighted /110 score for reviewing existing code — same crew, adversarial validation included, nothing self-graded.

**Quality rules that assume the code will try to lie to you.** Tiered findings, producer↔consumer round-trip checks (a fix isn't verified until it's proven against the real data on both ends, not a fixture someone guessed at), and a fail-loud rule: a silent failure ranks worse than a loud one, every time.

---

## Also covers, if you need it

Install only what applies to your project — every plugin below is optional, on top of the core.

| Plugin | What it's for |
|--------|---------------|
| **unmassk-db** | Postgres, MySQL, MongoDB, Redis — schema design, migrations, vector/RAG search |
| **unmassk-ops** | Terraform, Docker/K8s/Helm, CI/CD, observability, deploy scripts, error tracking |
| **unmassk-compliance** | GDPR, LOPDGDD, NIS2, ENS, SOC2/ISO, OWASP, cookies, i18n, legal docs |
| **unmassk-media** | Video (Remotion/ffmpeg), image generation/editing, mermaid diagrams, PDF, screenshots, transcription |
| **unmassk-design** | Design systems, motion, 3D/WebGL, scroll animation, Lottie/Rive/Anime.js, named style directions, Flutter UI |
| **unmassk-seo** | Technical SEO, schema markup, Core Web Vitals, GEO/AEO |
| **unmassk-marketing** | Copywriting, CRO, email, retention, paid ads, analytics, growth |
| **unmassk-pentesting** | Web/API/mobile/cloud/blockchain pentesting, recon, AD attacks, DFIR, CTF |
| **unmassk-humanizer** | Makes text stop reading as AI-written, in English and Spanish |
| **unmassk-3d** | 3D-printable parts sized to real objects from real measurements, not guesses |
| **unmassk-electronics** | Microcontroller firmware, Raspberry Pi, robotics — the device has to confirm, or it isn't done |
| **unmassk-trading** | Conversational trading on Kraken — teaches a beginner on a paper account, sizes from risk, never trades on its own |
| **unmassk-frontend** | React component quality, UI state, accessibility, styling discipline |
| **unmassk-typescript** | Strict TypeScript — type safety, type guards, no silent `any` |

---

## Install

Add the marketplace and install the core:

```
/plugin marketplace add unmassk/claude-toolkit
/plugin install unmassk-toolkit@unmassk-claude-toolkit
```

Then install whatever domain plugins you need:

```
/plugin install unmassk-db@unmassk-claude-toolkit
/plugin install unmassk-ops@unmassk-claude-toolkit
/plugin install unmassk-compliance@unmassk-claude-toolkit
/plugin install unmassk-media@unmassk-claude-toolkit
/plugin install unmassk-design@unmassk-claude-toolkit
/plugin install unmassk-seo@unmassk-claude-toolkit
/plugin install unmassk-marketing@unmassk-claude-toolkit
/plugin install unmassk-pentesting@unmassk-claude-toolkit
/plugin install unmassk-humanizer@unmassk-claude-toolkit
/plugin install unmassk-3d@unmassk-claude-toolkit
/plugin install unmassk-electronics@unmassk-claude-toolkit
/plugin install unmassk-trading@unmassk-claude-toolkit
/plugin install unmassk-frontend@unmassk-claude-toolkit
/plugin install unmassk-typescript@unmassk-claude-toolkit
```

Restart Claude Code. Done.

---

## Attribution

Several domain skills build on prior open-source work instead of reinventing it. Credit where it's owed:

- **unmassk-db** — `pg-aiguide` by Timescale (MIT), `database-skills` by PlanetScale (MIT), `agent-skills` by Redis (MIT), `claude-skills` by alirezarezvani (MIT)
- **unmassk-ops** — `cc-devops-skills` by akin-ozer (Apache-2.0)
- **unmassk-compliance** — `privacy-security-skills` by Jeremy Longshore (MIT), the NIS2 SMB package by Paolo Carner / BARE Consulting (CC BY 4.0), `comply` by Alireza Rezvani (MIT)
- **unmassk-media** — `@remotion/skills` by Remotion Inc. (MIT), `claude-screenshots` by Shpigford (MIT)
- **unmassk-design** — `claudedesignskills` by freshtechbro (Apache-2.0), `Impeccable` by Paul Bakaus (Apache-2.0), `UI/UX Pro Max` by nextlevelbuilder (MIT), plugins by bencium.io (MIT), the `emil-design-eng` and `animation-vocabulary` skills by Emil Kowalski (MIT), the `apple-design` skill (MIT), the `taste-skill` collection by leonxlnx (MIT), and `flutter-ui` from `claude-flutter-ui-skills` by Naimehossein77 (no license stated at source)
- **unmassk-marketing** — `marketingskills` by coreyhaines31 (MIT)
- **unmassk-seo** — `claude-seo` by AgriciDaniel (MIT)
- **unmassk-pentesting** — techniques from `communitytools` by Transilience AI (MIT)
- **unmassk-humanizer** — a fusion of `humanizer` by blader (MIT), `humanize-writing` by lguz (MIT), and `anti-slop` by kjmagnan1s (MIT, itself building on `avoid-ai-writing` by Conor Bronsdon (MIT) and `stop-slop` by Hardik Pandya (MIT)); its content-pattern catalog traces back to Wikipedia's "Signs of AI writing" (CC BY-SA 4.0)

A few skills are written from official product documentation rather than from someone else's skill — MongoDB's own docs behind `db-mongodb`, the OWASP Top 10 and ASVS behind `compliance-owasp-privacy`. Those are cited inside each skill; they are not listed above because there is no third-party author to credit.

Everything not listed here — the core toolkit, the agent crew, memory, Flow, Audit, and any plugin not named above — is original to this repo.

---

## License

MIT

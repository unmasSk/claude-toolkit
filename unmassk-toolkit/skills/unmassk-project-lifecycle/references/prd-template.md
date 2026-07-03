# PRD — [name] · (reader: AI + owner, no external human audience)

## 0. META
- project_name: / version: / last_updated: / owner: / status:

## 1. PROBLEM AND GOAL
- problem: (what's missing today, concrete)
- goal: (one sentence, what it solves)
- why: (the reason — so the AI doesn't re-question the decision)

## 2. SCOPE  ← critical section to avoid scope creep
IN:
- 
OUT / NON-GOALS (explicit — the AI does NOT build anything from here):
- 

## 3. FUNCTIONAL REQUIREMENTS
Numbered, unambiguous. Each one verifiable.
1. 
2. 

## 4. CONTRACT / BEHAVIOR  ← precision for the AI
For each piece with a defined input/output:
- input: / output: / rules: / error_format:
(If the piece isn't a data function —a skill, a hook—, describe the
 expected behavior instead, without forcing JSON.)

## 5. EDGE CASES AND LIMITS
- empty_input → / invalid → / ambiguity →
- limits: (size, time, whatever applies)

## 6. SUCCESS CRITERIA  (verifiable, not "should go well")
- 
- 

## 7. DEPENDENCIES AND ORDER
- depends_on:
- order: (what goes before what)
- production_blockers:

## 8. DECISIONS MADE  ← so the AI doesn't re-discuss them
- decision: — reason: — date:

## 9. OPEN DECISIONS
- [ ] (what's left to decide BEFORE building)

## 10. EXECUTION RULES (AI)
- Do not infer unspecified fields/scope. If something is missing → ask, don't assume.
- Do not expand scope beyond section 2.
- Follow the order in section 7.
- Deterministic over creative.
- Nothing enters "built" without meeting the project's DoD.

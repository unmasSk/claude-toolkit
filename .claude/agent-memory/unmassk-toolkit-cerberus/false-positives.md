---
name: false-positives
description: Patterns that look wrong but are intentional in this project
type: project
---

# False Positives

## tombstones set passed through memory dict
`memory.get("tombstones", set())` — the set() default is intentional.
If no tombstones exist, an empty set is safe and the filter logic is a no-op.

## extract_memory() returns tombstones in dict
The `tombstones` key in the return dict of extract_memory() is not exposed in the boot output.
It's an internal field consumed only by the glossary merge step. Correct by design.

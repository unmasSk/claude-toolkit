---
name: doctor-zones-check-retirement-notes
description: git-memory-doctor.py zones.json check (#13) — anti-vacuity control retirement pattern once the gap it proved closes
metadata:
  type: project
---

`test_doctor_derived_expectations.py` had a `TestDoctorNeverMentionsZonesToday`
class whose single test (`test_no_check_in_the_report_mentions_zones`)
existed purely as an anti-vacuity control: it proved, before Ultron's fix,
that `git-memory-doctor.py` genuinely had zero checks naming zones.json (so
the RED tests below it in `TestDoctorChecksZonesJson` weren't trivially
passing against a doctor that flags everything or nothing).

Ultron added `check_project_zones()` (check #13, `bin/git-memory-doctor.py:283`,
wired into `run_doctor()` at line 536). That made the control's premise false
on purpose — the doctor now DOES mention zones, always. Retired the class
entirely rather than inverting it into "doctor SI menciona zonas", because
`TestDoctorChecksZonesJson::test_a_zones_check_appears_in_the_report_for_every_state`
(parametrized absent/empty/populated) already proves presence for every
state, and `test_a_populated_zones_json_is_reported_ok_not_as_a_problem` is
that class's own anti-vacuity control (proves it isn't always "error"). An
inverse test would have been redundant, not additive.

**Why:** an anti-vacuity control's job is to prove a *pre-fix* gap was real.
Once the fix lands and a proper hardening class already covers the positive
case with its own anti-vacuity control, the pre-fix control has no further
job — keep it only if no equivalent post-fix coverage exists.

**How to apply:** when a "RED encargo" comment block precedes a class that
documents a gap in the present tense ("today X does not Y"), and the gap
closes, don't just delete silently — annotate the block itself
(`[cerrado <date>: ...]`, same style as the `[corregido 2026-08-05: ...]`
annotation already in this file for `EXPECTED_HOOKS`) so the historical
record of why the contract existed survives, then decide retire-vs-invert
by checking whether the surviving hardening class already exercises the
positive case. See [[test-file-self-drift-correction-notes]] for the
broader "stale prose inside test files, annotate don't silently delete"
pattern this follows.

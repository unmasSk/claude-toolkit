# PromQL Validator Best Practices

Rules for the validator scripts in `scripts/promql-validate-syntax.py` and `scripts/promql-check-best-practices.py`. Describes what they check, what findings mean, and how to test them.

---

## What the Validators Check

### Syntax Validator (`promql-validate-syntax.py`)

Checks whether a PromQL expression is parseable. Reports parse errors with position info.

**Run before:** presenting any query to the user.

```bash
python3 scripts/promql-validate-syntax.py "rate(http_requests_total{job='api'}[5m])"
```

Errors to handle:
- Missing range vector: `rate(metric)` → add `[5m]`
- Unmatched brackets: `rate(metric[5m)` → fix syntax
- Invalid label matchers: `{job=api}` → `{job="api"}`
- Unknown function name: `rateX(...)` → check spelling

### Best Practice Checker (`promql-check-best-practices.py`)

Checks for correctness and performance issues beyond syntax. Reports findings by severity.

**Run after syntax validation** on all generated queries.

```bash
python3 scripts/promql-check-best-practices.py "rate(http_requests_total[5m])"
```

**Categories of findings:**

| Category | What it checks |
|----------|---------------|
| Missing label filter | Bare metric name with no `{...}` selectors |
| Counter without rate | Metric ending in `_total`/`_count`/`_sum` queried raw |
| rate() on gauge | `rate()` applied to non-counter metric |
| Short rate range | Range less than `4 × scrape_interval` (assumes 15s default) |
| irate long range | `irate()` with range > 5 minutes |
| Missing aggregation | `histogram_quantile()` without `sum by (le)` |
| Missing rate in histogram | `histogram_quantile()` without `rate()` on buckets |
| Averaging quantiles | `avg()` applied to `{quantile="..."}` labels |
| Regex on exact value | `=~"literal"` where `=` would work |
| No by/without | Aggregation operators without explicit label grouping |
| High-cardinality label | Known high-cardinality label names used in `by()` |

---

## Writing Tests for the Validators

Test file: `scripts/promql-test-validators.py`

Each test case specifies: input query, expected validation result (pass/fail), and for best-practice checks, expected finding categories.

### Test structure

```python
# Syntax validator test
{
    "query": "rate(http_requests_total[5m])",
    "expect_valid": True
}

{
    "query": "rate(http_requests_total)",
    "expect_valid": False,
    "expected_error_contains": "range vector"
}

# Best practice test
{
    "query": "http_requests_total",
    "expect_findings": ["missing_label_filter", "counter_without_rate"]
}

{
    "query": "rate(http_requests_total{job='api'}[5m])",
    "expect_findings": []    # clean query, no findings
}
```

### Run all tests

```bash
python3 scripts/promql-test-validators.py
```

Expected output: pass/fail count, details on any failures.

---

## Severity Levels

Findings use three severity levels:

| Severity | Meaning | Action |
|----------|---------|--------|
| `ERROR` | Query is incorrect — will give wrong results | Must fix before using |
| `WARNING` | Query may be slow or misleading | Fix before production use |
| `INFO` | Style or best practice suggestion | Improve if possible |

**ERROR examples:**
- `histogram_quantile` without `le` label
- `rate()` without range vector
- Averaging pre-calculated quantiles

**WARNING examples:**
- Missing label filter (performance)
- Rate range shorter than `4 × scrape_interval`
- Regex where exact match would work

**INFO examples:**
- Aggregation without explicit `by()`/`without()`
- Recording rule recommended for complex query

---

## Validator Workflow

For every query generated:

1. Run `promql-validate-syntax.py` — if it fails, fix syntax first.
2. Run `promql-check-best-practices.py` — fix all ERRORs. Address WARNINGs.
3. Show validation output to the user alongside the query.
4. If the query is complex or used frequently, suggest a recording rule.

---

## Common Fixes by Finding

| Finding | Fix |
|---------|-----|
| `missing_label_filter` | Add `{job="<service_name>"}` at minimum |
| `counter_without_rate` | Wrap in `rate(...[5m])` or `increase(...[1h])` |
| `rate_on_gauge` | Remove `rate()`, use value directly or `avg_over_time()` |
| `short_rate_range` | Increase range to at least `[1m]`, prefer `[5m]` |
| `irate_long_range` | Reduce range to `[2m]`–`[5m]` |
| `histogram_missing_le` | Change `sum by (job)` to `sum by (job, le)` |
| `histogram_missing_rate` | Add `rate(...[5m])` inside the `sum by (le)` |
| `averaging_quantiles` | Use `histogram_quantile()` on buckets instead |
| `regex_exact_value` | Change `=~"value"` to `="value"` |
| `aggregation_no_by` | Add `by (job)` or `without (instance)` |

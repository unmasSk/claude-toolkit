# PromQL Anti-Patterns

Each pattern includes why it fails and the correct fix.

---

## Cardinality

### No label filters

```promql
# BAD: matches every time series for this metric
http_requests_total

# GOOD
http_requests_total{job="api", environment="production"}
```

Impact: query times jump from milliseconds to seconds or minutes. Risk of timeout.

### High-cardinality labels in selectors or aggregations

```promql
# BAD: user_id can have millions of unique values
sum by (user_id) (requests_total)

# GOOD: aggregate out high-cardinality labels
sum by (job, endpoint) (requests_total)
```

Labels to avoid as selectors or aggregation keys: `user_id`, `customer_id`, `request_id`, `trace_id`, `session_id`, `uuid`, `ip_address`, full URLs.

### Overly broad regex

```promql
# BAD: matches everything (useless filter)
http_requests_total{path=~".*"}

# GOOD: anchor the pattern and pair with other filters
http_requests_total{job="api", path=~"/api/v[0-9]+/.*"}
```

---

## Incorrect Function Usage

### Raw counter value

```promql
# BAD: always increasing, useless for monitoring
http_requests_total{job="api"}
sum(http_requests_total)

# GOOD
rate(http_requests_total{job="api"}[5m])
increase(http_requests_total{job="api"}[1h])
```

### rate() on a gauge

```promql
# BAD: gauges can decrease; rate() assumes monotonically increasing input
rate(memory_usage_bytes[5m])
irate(cpu_temperature_celsius[5m])

# GOOD
memory_usage_bytes                          # current value
avg_over_time(memory_usage_bytes[5m])       # smoothed
delta(cpu_temperature_celsius[5m])          # change over period
```

How to identify: counters end in `_total`, `_count`, `_sum`, `_bucket`. Gauges indicate current state: `_bytes`, `_usage`, `_percent`, `_celsius`.

### rate() without a range vector

```promql
# BAD: syntax error
rate(http_requests_total)

# GOOD
rate(http_requests_total[5m])
```

Error message: `expected type range vector in call to function, got instant vector`

### irate() with a long range

```promql
# BAD: irate only uses the last 2 samples regardless of range — the 1h is wasted
irate(http_requests_total[1h])

# GOOD
irate(http_requests_total[2m])    # short range appropriate for irate
rate(http_requests_total[1h])     # use rate for long ranges
```

### rate() range too short

```promql
# BAD: 30s range with 15s scrape interval = only 2 samples = noisy
rate(http_requests_total[30s])

# GOOD: minimum 4× scrape interval
rate(http_requests_total[2m])    # for 15s scrape interval
rate(http_requests_total[5m])    # typical choice
```

Rule: `rate_range >= 4 × scrape_interval`.

---

## Histogram Misuse

### histogram_quantile without rate()

```promql
# BAD: uses cumulative bucket counts instead of rate
histogram_quantile(0.95,
  sum by (le) (http_request_duration_seconds_bucket)
)

# GOOD
histogram_quantile(0.95,
  sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
)
```

### histogram_quantile without le label

```promql
# BAD: le is required for bucket boundaries
histogram_quantile(0.95,
  sum by (job) (rate(http_request_duration_seconds_bucket[5m]))
)

# GOOD
histogram_quantile(0.95,
  sum by (job, le) (rate(http_request_duration_seconds_bucket[5m]))
)
```

### Averaging pre-calculated quantiles

```promql
# BAD: mathematically invalid — average of P95s is not the overall P95
avg(http_request_duration_seconds{quantile="0.95"})
sum(response_time{quantile="0.99"})

# GOOD: use histogram buckets for aggregatable percentiles
histogram_quantile(0.95,
  sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
)

# Or calculate average from sum/count
sum(rate(http_request_duration_seconds_sum[5m]))
/
sum(rate(http_request_duration_seconds_count[5m]))
```

### Summary when you need aggregation

Summaries cannot be aggregated across instances. If you need multi-instance percentiles, instrument with histograms.

---

## Performance

### Excessive subquery range

```promql
# BAD: 95-day subquery processes millions of samples, will likely timeout
max_over_time(rate(http_requests_total[5m])[95d:1m])

# GOOD: reasonable range
max_over_time(rate(http_requests_total[5m])[7d:5m])

# BETTER: recording rule for long-term analysis
# record: job:http_requests:rate5m
# Then: max_over_time(job:http_requests:rate5m[30d:1h])
```

### Regex instead of exact match

```promql
# BAD: regex matching is 5–10x slower for exact values
http_requests_total{status=~"200"}
http_requests_total{job=~"api-service"}

# GOOD
http_requests_total{status="200"}
http_requests_total{job="api-service"}
```

Use regex only when needed:
```promql
http_requests_total{status=~"2.."}          # multiple patterns
http_requests_total{path!~"/health|/ready"} # exclusions
```

### Filter after aggregation

```promql
# BAD: aggregates all series, then filters
sum(rate(http_requests_total[5m])) and {job="api"}

# GOOD: filter before aggregation
sum(rate(http_requests_total{job="api"}[5m]))
```

Impact: 10–100x slower when filtering after aggregation.

### Expensive query without recording rule

```promql
# BAD: complex query running in 10 dashboards, evaluated every 30 seconds
sum by (job, instance) (
  rate(http_request_duration_seconds_sum[5m])
) /
sum by (job, instance) (
  rate(http_request_duration_seconds_count[5m])
)

# GOOD: recording rule evaluated once per cycle
# record: job_instance:http_request_duration_seconds:mean5m
# Then use: job_instance:http_request_duration_seconds:mean5m
```

When to use recording rules: query is used in multiple dashboards, query takes >1 second, query uses long subqueries.

---

## Mathematical Errors

### Division with mismatched label sets

```promql
# BAD: instance label on left but not right → no data (label mismatch)
rate(http_requests_total{job="api", instance="host1"}[5m])
/
rate(http_requests_total{job="api"}[5m])

# GOOD: both sides match on the same label set
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))
```

### Forgetting group_left/group_right in joins

```promql
# BAD: many-to-one join without group_left → error: "multiple matches"
rate(http_requests_total[5m])
* on (job, instance)
service_info

# GOOD
rate(http_requests_total[5m])
* on (job, instance) group_left (version, commit)
service_info
```

### Multiple OR instead of regex alternation

```promql
# BAD: 3–5x slower than single regex
http_requests_total{job="api"}
or
http_requests_total{job="web"}
or
http_requests_total{job="worker"}

# GOOD
http_requests_total{job=~"api|web|worker"}
```

### Aggregation without by() or without()

```promql
# BAD: unclear what labels remain in the result
sum(rate(http_requests_total[5m]))

# GOOD: explicit
sum by (job) (rate(http_requests_total[5m]))
sum without (instance, pod) (rate(http_requests_total[5m]))
```

---

## Quick Checklist

Before finalizing a query:

- [ ] Label filters present (at least `job`)
- [ ] `rate()` used on counters, not on gauges
- [ ] `rate()` range >= `4 × scrape_interval`
- [ ] `irate()` range is 2–5 minutes maximum
- [ ] `histogram_quantile()` has `rate()` and `le` in aggregation
- [ ] No averaging of pre-calculated quantiles
- [ ] No regex where exact match works
- [ ] Aggregation uses explicit `by()` or `without()`
- [ ] Subquery range is reasonable (< 7 days typically)
- [ ] Expensive/repeated queries use recording rules

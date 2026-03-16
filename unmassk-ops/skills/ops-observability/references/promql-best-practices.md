# PromQL Best Practices

Rules for writing correct, efficient, maintainable queries.

---

## Label Filtering

**Always use label filters.** Bare metric names scan all time series.

```promql
# BAD
rate(http_requests_total[5m])

# GOOD: minimum one label filter
rate(http_requests_total{job="api"}[5m])

# BETTER: specific enough to reduce cardinality
rate(http_requests_total{job="api", environment="production"}[5m])
```

**Use exact match over regex.** Exact match uses index lookup; regex uses pattern matching (5–10x slower).

```promql
# BAD: regex for an exact value
http_requests_total{status=~"200"}

# GOOD
http_requests_total{status="200"}

# Regex is appropriate for patterns and multiple values
http_requests_total{status=~"2.."}
http_requests_total{status=~"500|502|503"}
http_requests_total{path!~"/health|/ready|/metrics"}
```

**Avoid high-cardinality labels** in selectors and aggregation keys: `user_id`, `request_id`, `trace_id`, `session_id`, `uuid`, full URLs. Each unique value creates a separate time series.

---

## Metric Type Rules

**Counters:** always use `rate()` for per-second values, `increase()` for totals.

```promql
rate(http_requests_total{job="api"}[5m])
increase(http_requests_total{job="api"}[1h])
```

**Gauges:** use directly or with `*_over_time()` functions. Never use `rate()`.

```promql
memory_usage_bytes{instance="prod-1"}
avg_over_time(memory_usage_bytes{instance="prod-1"}[5m])
max_over_time(queue_length[1h])
deriv(disk_usage_bytes[1h])    # rate of change for gauges
```

**Histograms:** always `rate()` on buckets + `sum by (le)` + `histogram_quantile()`.

```promql
histogram_quantile(0.95,
  sum by (job, le) (rate(http_request_duration_seconds_bucket{job="api"}[5m]))
)

# Average from histogram
sum(rate(http_request_duration_seconds_sum[5m]))
/
sum(rate(http_request_duration_seconds_count[5m]))
```

**Summaries:** never aggregate quantile labels. Use `_sum`/`_count` for averages.

```promql
# BAD: invalid math
avg(http_request_duration_seconds{quantile="0.95"})

# GOOD
sum(rate(http_request_duration_seconds_sum[5m]))
/
sum(rate(http_request_duration_seconds_count[5m]))
```

---

## Aggregation

**Always use `by()` or `without()`.** Make output labels explicit.

```promql
# BAD: what labels are in the result?
sum(rate(http_requests_total[5m]))

# GOOD
sum by (job) (rate(http_requests_total[5m]))
sum without (instance, pod) (rate(http_requests_total[5m]))
```

**`by()` vs `without()`:**
- `by()`: keep only the listed labels
- `without()`: drop the listed labels, keep everything else

Use `without()` when you want to preserve most labels and drop only the high-cardinality ones.

**Aggregate before `histogram_quantile()`.** Never after.

```promql
# BAD: trying to aggregate after quantile calculation
sum(histogram_quantile(0.95, rate(latency_bucket[5m])))

# GOOD
histogram_quantile(0.95,
  sum by (le) (rate(latency_bucket[5m]))
)
```

---

## Time Range Selection

**Minimum `rate()` range:** `4 × scrape_interval`.

| Scrape interval | Minimum range | Typical choice |
|-----------------|---------------|----------------|
| 15s | 1m | 5m |
| 30s | 2m | 5m |
| 60s | 4m | 5m |

**`rate()` range guidelines:**
- Real-time monitoring: `[2m]`–`[5m]`
- Trend analysis: `[15m]`–`[1h]`
- `[5m]` is the safe default for most cases

**`irate()` range:** keep short (2–5 minutes). Only uses the last 2 samples regardless of range.

**Subqueries:** expensive. Use recording rules for subqueries over long ranges.

```promql
# Expensive
max_over_time(rate(metric[5m])[7d:1h])

# Better: recording rule pre-computes rate, then query over long range
max_over_time(job:metric:rate5m[7d])
```

---

## Recording Rules

Pre-compute expensive or frequently-used queries.

**Naming convention:** `level:metric:operations`

```yaml
groups:
  - name: http_request_rates
    interval: 30s
    rules:
      - record: job:http_requests:rate5m
        expr: sum by (job) (rate(http_requests_total[5m]))

      - record: job:http_request_duration:p95
        expr: |
          histogram_quantile(0.95,
            sum by (job, le) (rate(http_request_duration_seconds_bucket[5m]))
          )

      - record: job:http_request_duration:mean5m
        expr: |
          sum by (job) (rate(http_request_duration_seconds_sum[5m]))
          /
          sum by (job) (rate(http_request_duration_seconds_count[5m]))
```

**When to use:**
- Query appears in multiple dashboards
- Query takes more than 1 second
- Query uses long subqueries
- Alert expression is complex (alert on the recording rule instead)

**Layering:** build complex metrics in stages.

```yaml
# Layer 1: per-instance rate
- record: instance:http_requests:rate5m
  expr: rate(http_requests_total[5m])

# Layer 2: per-job aggregation
- record: job:http_requests:rate5m
  expr: sum by (job) (instance:http_requests:rate5m)

# Layer 3: error ratio
- record: job:http_errors:ratio5m
  expr: |
    sum by (job) (instance:http_requests:rate5m{status=~"5.."})
    /
    job:http_requests:rate5m
```

---

## Alerting

**Alert expressions should be boolean** (return a value when condition is true).

```promql
# Error rate above threshold
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))
> 0.05

# CPU above limit
(1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))) > 0.80
```

**Use `for:` to avoid alerting on transient spikes.**

```yaml
- alert: HighErrorRate
  expr: job:http_errors:ratio5m > 0.05
  for: 10m
  labels:
    severity: warning
```

**Use recording rules in alerts.** Complex alert expressions are hard to read and evaluated repeatedly.

```yaml
# BAD: complex inline expression
- alert: HighErrorRate
  expr: |
    sum by (job) (rate(http_requests_total{status=~"5.."}[5m]))
    /
    sum by (job) (rate(http_requests_total[5m]))
    > 0.05

# GOOD: alert on the recording rule
- alert: HighErrorRate
  expr: job:http_errors:ratio5m > 0.05
```

**Alert on absence specifically.**

```promql
absent(up{job="critical-service"})               # metric missing
absent_over_time(up{job="critical-service"}[10m]) # metric absent for 10 min
```

---

## Performance Checklist

- [ ] All metrics have at least one label filter
- [ ] Exact match (`=`) used instead of regex (`=~`) where possible
- [ ] `rate()` range is at least `4 × scrape_interval`
- [ ] `irate()` range is 2–5 minutes
- [ ] Aggregations use explicit `by()` or `without()`
- [ ] `histogram_quantile()` has `rate()` and `le` label in aggregation
- [ ] No averaging of pre-calculated quantiles
- [ ] Subquery ranges are reasonable (< 7 days)
- [ ] Complex or frequent queries use recording rules
- [ ] High-cardinality labels not used in `by()` clauses

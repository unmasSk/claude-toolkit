# Prometheus Metric Types

Four types. Each has strict query rules.

## Counter

A cumulative value that only increases (or resets to zero on process restart).

**Naming:** ends in `_total`, `_count`, `_sum`, `_bucket`.

**Rule:** never query raw value. Always use `rate()` or `increase()`.

```promql
# Per-second rate over 5 minutes
rate(http_requests_total{job="api"}[5m])

# Total increase over 1 hour
increase(http_requests_total{job="api"}[1h])
```

**Why raw value is useless:** the value monotonically increases from process start. It tells you nothing about current behavior.

**Counter resets:** `rate()` and `increase()` handle resets automatically.

---

## Gauge

A value that can go up or down. Represents current state.

**Naming:** describes the measured value with units: `memory_usage_bytes`, `queue_length`, `cpu_temperature_celsius`.

**Rule:** use directly or with `*_over_time()`. Never use `rate()`, `irate()`, or `increase()`.

```promql
# Current value
memory_usage_bytes{instance="prod-1"}

# Average over time (smooths noise)
avg_over_time(memory_usage_bytes{instance="prod-1"}[5m])

# Peak in last hour
max_over_time(memory_usage_bytes{instance="prod-1"}[1h])

# Rate of change (not rate — gauges can decrease)
deriv(disk_usage_bytes{instance="prod-1"}[1h])
```

---

## Histogram

Samples observations into configurable buckets. Three metric families generated:

- `<name>_bucket{le="..."}` — cumulative count per upper bound
- `<name>_sum` — sum of all observed values
- `<name>_count` — total observation count

**Naming:** `http_request_duration_seconds`, `response_size_bytes`.

**Rule:** `histogram_quantile()` requires `rate()` on buckets AND `sum by (le)`.

```promql
# P95 latency — correct form
histogram_quantile(0.95,
  sum by (le) (rate(http_request_duration_seconds_bucket{job="api"}[5m]))
)

# P95 by service
histogram_quantile(0.95,
  sum by (service, le) (rate(http_request_duration_seconds_bucket{job="api"}[5m]))
)

# Average from histogram
sum(rate(http_request_duration_seconds_sum{job="api"}[5m]))
/
sum(rate(http_request_duration_seconds_count{job="api"}[5m]))

# SLO: fraction of requests under 200ms
sum(rate(http_request_duration_seconds_bucket{le="0.2"}[5m]))
/
sum(rate(http_request_duration_seconds_count[5m]))
```

**Bucket configuration:** cover the expected distribution. For HTTP latency:
```
[.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10]
```

**Histogram vs Summary:** histograms are aggregatable across instances. Summaries are not. Use histograms for new instrumentation.

### Native Histograms (Prometheus 3.x)

Single time series instead of separate `_bucket`/`_sum`/`_count`. Simpler syntax:

```promql
# No _bucket suffix, no le label needed
histogram_quantile(0.95,
  sum by (job) (rate(http_request_duration_seconds{job="api"}[5m]))
)

# Native histogram functions
histogram_avg(rate(http_request_duration_seconds[5m]))
histogram_stddev(rate(http_request_duration_seconds[5m]))
histogram_fraction(0, 0.1, rate(http_request_duration_seconds[5m]))  # fraction under 100ms
```

Enable in Prometheus: `scrape_native_histograms: true`.

---

## Summary

Pre-calculates quantiles on the client. Emits `{quantile="0.5"}`, `{quantile="0.99"}`, `_sum`, `_count`.

**Rule:** never aggregate quantile labels across instances. Use `_sum/_count` for averages.

```promql
# Use quantile directly (per-instance only)
http_request_duration_seconds{job="api", quantile="0.95"}

# Average from summary
sum(rate(http_request_duration_seconds_sum[5m]))
/
sum(rate(http_request_duration_seconds_count[5m]))
```

**What not to do:**
```promql
# WRONG: mathematically invalid
avg(http_request_duration_seconds{quantile="0.95"})
```

**When to use:** per-instance percentiles where aggregation is not needed. Otherwise, use histograms.

---

## Decision Table

| What you're measuring | Type | Suffix pattern |
|-----------------------|------|----------------|
| Event count (requests, errors) | Counter | `_total` |
| Current state (memory, queue depth) | Gauge | `_bytes`, `_count`, `_celsius` |
| Latency distribution | Histogram | `_seconds`, `_bucket` |
| Pre-calculated percentiles (legacy) | Summary | `{quantile="..."}` |

---

## Naming Conventions

- Base units: `_seconds` not `_ms`, `_bytes` not `_kb`
- Include units: `http_request_duration_seconds`, `node_memory_usage_bytes`
- Counters end in `_total`: `http_requests_total`, `errors_total`
- Ratios (0-1): `_ratio`; percentages (0-100): `_percent`
- No stuttering: `http_requests_total` not `http_http_requests_total`

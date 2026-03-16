# PromQL Functions Reference

Functions organized by category. For usage patterns see `promql-patterns.md`. For what to avoid see `promql-anti-patterns.md`.

---

## Rate and Increase (Counters Only)

These functions assume monotonically increasing input. Use only on counters (`_total`, `_count`, `_sum`, `_bucket`).

### rate(v range-vector)

Per-second average rate of increase over the range. Handles counter resets. Extrapolates to range boundaries.

```promql
rate(http_requests_total{job="api"}[5m])    # requests/sec, smoothed
rate(bytes_sent_total[1m])                  # bytes/sec
```

**Range rule:** minimum `4 × scrape_interval`. For 15s scrape: `[1m]` minimum, `[5m]` typical.

**Use for:** graphing trends, sustained rate alerts, throughput calculations.

### irate(v range-vector)

Instant rate based on the last two data points in the range. More sensitive to spikes.

```promql
irate(http_requests_total[5m])    # range determines lookback only; uses last 2 points
```

**Use for:** spike detection, real-time dashboards. Range should be 2–5 minutes.

**rate vs irate:** `rate()` is smooth (average over range). `irate()` is volatile (last two samples). Default to `rate()`.

### increase(v range-vector)

Total increase over the range. Equivalent to `rate(v) × range_seconds`. Result can be fractional (extrapolation).

```promql
increase(http_requests_total[1h])    # total requests in the past hour
```

**Use for:** billing, capacity planning, SLO burn calculations.

---

## Aggregation Operators

Combine multiple time series into fewer.

**Syntax:** `<op> [by|without (<labels>)] (<vector>)`

Always use `by()` or `without()` explicitly.

| Operator | Purpose |
|----------|---------|
| `sum` | Total across series |
| `avg` | Average |
| `max` / `min` | Extremes |
| `count` | Number of series |
| `topk(N, v)` | Top N by value |
| `bottomk(N, v)` | Bottom N by value |
| `quantile(φ, v)` | φ-quantile across series (not histograms) |
| `stddev` / `stdvar` | Standard deviation / variance |
| `count_values("label", v)` | Count series with same value |
| `group(v)` | Returns 1 for each series (existence check) |

```promql
sum by (job) (rate(http_requests_total[5m]))
topk(10, sum by (endpoint) (rate(http_requests_total[5m])))
count(up{job="api"} == 1)    # number of healthy instances
```

---

## Range Vector Functions (*_over_time)

Operate on gauge metrics over a time window. Do not use on counters (use `rate()` instead).

| Function | Purpose |
|----------|---------|
| `avg_over_time(v[d])` | Average over time window |
| `max_over_time(v[d])` | Maximum in window |
| `min_over_time(v[d])` | Minimum in window |
| `sum_over_time(v[d])` | Sum of samples |
| `count_over_time(v[d])` | Number of samples |
| `stddev_over_time(v[d])` | Standard deviation |
| `quantile_over_time(φ, v[d])` | Percentile over time |
| `last_over_time(v[d])` | Most recent sample |
| `present_over_time(v[d])` | Returns 1 if any sample exists |
| `changes(v[d])` | Number of value changes |

```promql
avg_over_time(memory_usage_bytes{instance="prod-1"}[5m])
max_over_time(queue_depth[1h])
changes(config_reload_total[1h])    # how many reloads
```

---

## Histogram Functions

### histogram_quantile(φ, v)

Calculates φ-quantile from histogram buckets.

**Classic histograms (mandatory pattern):**
```promql
histogram_quantile(0.95,
  sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
)
```

Requirements:
1. `rate()` on `_bucket` metric
2. `sum by (le)` — `le` must be in the `by()` clause
3. Aggregate BEFORE calling `histogram_quantile()`

**Native histograms (Prometheus 3.x):**
```promql
histogram_quantile(0.95,
  sum by (job) (rate(http_request_duration_seconds[5m]))
)
```

No `_bucket` suffix. No `le` label needed.

### Native histogram functions (Prometheus 3.x)

```promql
histogram_avg(rate(http_request_duration_seconds[5m]))         # average
histogram_stddev(rate(http_request_duration_seconds[5m]))      # std deviation
histogram_stdvar(rate(http_request_duration_seconds[5m]))      # variance
histogram_count(rate(http_request_duration_seconds[5m]))       # observation count
histogram_sum(rate(http_request_duration_seconds[5m]))         # sum of values
histogram_fraction(0, 0.1, rate(http_request_duration_seconds[5m]))  # fraction under 100ms
```

---

## Prediction and Smoothing

### predict_linear(v range-vector, t scalar)

Predicts value `t` seconds into the future using linear regression.

```promql
# Predict disk usage in 4 hours
predict_linear(disk_usage_bytes[1h], 4*3600)

# Time to fill disk (seconds until avail reaches 0)
node_filesystem_avail_bytes / (-deriv(node_filesystem_avail_bytes[1h]))
```

### deriv(v range-vector)

Per-second derivative via linear regression.

```promql
deriv(queue_length[10m])    # is the queue growing or shrinking?
```

### double_exponential_smoothing(v range-vector, sf, tf)

Formerly `holt_winters`. Renamed in Prometheus 3.0. Requires `--enable-feature=promql-experimental-functions`.

Gauges only.

```promql
double_exponential_smoothing(metric[1h], 0.5, 0.5)
```

---

## Label Manipulation

### label_replace(v, dst_label, replacement, src_label, regex)

Adds or replaces a label using a regex capture.

```promql
# Extract hostname from "server:9090" → hostname="server"
label_replace(up, "hostname", "$1", "instance", "(.+):\\d+")

# Copy label
label_replace(metric, "service", "$1", "job", "(.*)")
```

### label_join(v, dst_label, separator, src_label, ...)

Concatenates multiple label values.

```promql
label_join(metric, "job_instance", ":", "job", "instance")
```

---

## Time Functions

```promql
time()                      # current Unix timestamp (seconds)
timestamp(v)                # timestamp of each sample
year()                      # current year
month()                     # current month (1–12)
day_of_month()              # 1–31
day_of_week()               # 0=Sunday
hour()                      # 0–23 (UTC)
minute()                    # 0–59
days_in_month()             # days in current month
```

Business hours example:
```promql
# Alert only during business hours (UTC)
expr and on() (hour() >= 9 and hour() < 17 and day_of_week() >= 1 and day_of_week() <= 5)
```

---

## Utility Functions

### absent(v instant-vector)

Returns `{} 1` if input is empty. Use for alerting on missing metrics.

```promql
absent(up{job="api"})           # fires if no series matching job="api"
absent_over_time(up{job="api"}[10m])    # fires if no data in 10 minutes
```

### scalar(v), vector(n)

```promql
scalar(sum(up{job="api"}))      # single-element vector → scalar (NaN if 0 or >1 elements)
vector(0)                       # fallback for alerting rules — ensures non-empty result
```

### clamp / clamp_min / clamp_max

```promql
clamp(metric, 0, 100)
clamp_min(metric, 0)
clamp_max(metric, 100)
```

### sort / sort_desc / topk / bottomk

```promql
sort_desc(sum by (endpoint) (rate(http_requests_total[5m])))
topk(5, sum by (endpoint) (rate(http_requests_total[5m])))
```

### resets(v range-vector)

Counts counter resets (process restarts, rollbacks).

```promql
resets(http_requests_total[1h])
```

---

## Experimental Functions (Prometheus 3.5+)

Require `--enable-feature=promql-experimental-functions`.

| Function | Available | Purpose |
|----------|-----------|---------|
| `ts_of_max_over_time(v[d])` | 3.5+ | Timestamp when maximum occurred |
| `ts_of_min_over_time(v[d])` | 3.5+ | Timestamp when minimum occurred |
| `ts_of_last_over_time(v[d])` | 3.5+ | Timestamp of last sample |
| `first_over_time(v[d])` | 3.7+ | First (oldest) value in range |
| `ts_of_first_over_time(v[d])` | 3.7+ | Timestamp of first sample |
| `mad_over_time(v[d])` | experimental | Median absolute deviation |
| `sort_by_label(v, labels...)` | experimental | Sort by label value |
| `info(v, [selector])` | experimental | Enrich metrics from info metrics |

---

## Prometheus 3.0 Breaking Changes

1. **Range selectors are now left-open**: sample at the exact lower boundary is excluded.
2. **`holt_winters` renamed** to `double_exponential_smoothing` (experimental flag required).
3. **Regex `.` matches newlines** now.
4. **Native histograms are stable** (no longer experimental).
5. **UTF-8 metric/label names** supported.

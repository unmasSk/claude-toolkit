# PromQL Query Patterns

Common patterns organized by use case. Adapt label selectors (`job`, `instance`, `environment`) to your setup.

---

## RED Method (Request-Driven Services)

Rate, Errors, Duration — the standard baseline for any HTTP/RPC service.

### Rate (throughput)

```promql
# Requests per second
sum(rate(http_requests_total{job="api"}[5m]))

# By endpoint
sum by (endpoint) (rate(http_requests_total{job="api"}[5m]))

# By status code
sum by (status_code) (rate(http_requests_total{job="api"}[5m]))

# Requests per minute
sum(rate(http_requests_total{job="api"}[5m])) * 60
```

### Errors

```promql
# Error ratio (0 to 1)
sum(rate(http_requests_total{job="api", status_code=~"5.."}[5m]))
/
sum(rate(http_requests_total{job="api"}[5m]))

# Error percentage
(
  sum(rate(http_requests_total{job="api", status_code=~"5.."}[5m]))
  /
  sum(rate(http_requests_total{job="api"}[5m]))
) * 100

# Error rate by endpoint
sum by (endpoint) (rate(http_requests_total{status_code=~"5.."}[5m]))
/
sum by (endpoint) (rate(http_requests_total[5m]))
```

### Duration (latency)

```promql
# P95 latency
histogram_quantile(0.95,
  sum by (le) (rate(http_request_duration_seconds_bucket{job="api"}[5m]))
)

# P50, P90, P95, P99
histogram_quantile(0.50, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))
histogram_quantile(0.90, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))
histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))

# Average latency
sum(rate(http_request_duration_seconds_sum[5m]))
/
sum(rate(http_request_duration_seconds_count[5m]))

# Latency by endpoint
histogram_quantile(0.95,
  sum by (endpoint, le) (rate(http_request_duration_seconds_bucket[5m]))
)
```

---

## USE Method (Resources)

Utilization, Saturation, Errors — for CPU, memory, disk, network.

### CPU

```promql
# CPU utilization % (per instance)
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Across all instances
(
  sum(rate(node_cpu_seconds_total{mode!="idle"}[5m]))
  /
  sum(rate(node_cpu_seconds_total[5m]))
) * 100
```

### Memory

```promql
# Usage percentage
(
  (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes)
  /
  node_memory_MemTotal_bytes
) * 100

# Available in GB
node_memory_MemAvailable_bytes / (1024 * 1024 * 1024)
```

### Disk

```promql
# Usage percentage
(
  (node_filesystem_size_bytes - node_filesystem_avail_bytes)
  /
  node_filesystem_size_bytes
) * 100

# Time until full (hours)
(
  node_filesystem_avail_bytes
  /
  (-deriv(node_filesystem_avail_bytes[1h]))
) / 3600

# I/O rate
rate(node_disk_reads_completed_total[5m]) + rate(node_disk_writes_completed_total[5m])
```

### Network

```promql
# Receive/transmit rate (MB/s)
rate(node_network_receive_bytes_total[5m]) / (1024 * 1024)
rate(node_network_transmit_bytes_total[5m]) / (1024 * 1024)

# Error rate
rate(node_network_receive_errs_total[5m]) + rate(node_network_transmit_errs_total[5m])
```

---

## Availability

```promql
# Percentage of instances that are up
(count(up{job="api"} == 1) / count(up{job="api"})) * 100

# Count up/down
count(up{job="api"} == 1)
count(up{job="api"} == 0)

# Uptime (hours since last restart)
(time() - process_start_time_seconds{job="api"}) / 3600
```

---

## Saturation

```promql
# Queue depth
queue_length{service="worker"}
avg_over_time(queue_length[5m])

# Time to drain queue (seconds)
queue_length / rate(queue_processed_total[5m])

# Queue fill rate (growing or shrinking?)
rate(queue_added_total[5m]) - rate(queue_processed_total[5m])

# Connection pool saturation
(active_connections / max_connections) * 100

# Thread pool saturation
(active_threads / max_threads) * 100

# Load average normalized by CPU count
node_load1
/
count without (cpu, mode) (node_cpu_seconds_total{mode="idle"})
```

---

## Ratio Calculations

```promql
# Cache hit ratio
rate(cache_hits_total[5m])
/
(rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))

# Success rate
1 - (
  sum(rate(errors_total[5m]))
  /
  sum(rate(requests_total[5m]))
)

# Write/read ratio
rate(writes_total[5m]) / rate(reads_total[5m])
```

---

## SLO Compliance

```promql
# Percentage of requests faster than 200ms
(
  sum(rate(http_request_duration_seconds_bucket{le="0.2"}[5m]))
  /
  sum(rate(http_request_duration_seconds_count[5m]))
) * 100

# SLO: 99.5% of requests must complete under 1s
(
  sum(rate(http_request_duration_seconds_bucket{le="1"}[5m]))
  /
  sum(rate(http_request_duration_seconds_count[5m]))
) >= 0.995
```

---

## Historical Comparison

```promql
# Current vs 1 hour ago
rate(http_requests_total[5m]) - rate(http_requests_total[5m] offset 1h)

# Percentage change from yesterday
(
  (rate(http_requests_total[5m]) - rate(http_requests_total[5m] offset 1d))
  /
  rate(http_requests_total[5m] offset 1d)
) * 100

# Week-over-week ratio
rate(http_requests_total[5m]) / rate(http_requests_total[5m] offset 1w)
```

---

## Alerting Patterns

### Threshold alerts

```promql
# High error rate
sum(rate(http_requests_total{status_code=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))
> 0.05

# High latency
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m]))) > 1

# Disk low
(node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100 < 10
```

### Absence alerts

```promql
absent(up{job="critical-service"})                         # metric missing
absent_over_time(up{job="critical-service"}[10m])          # no data for 10 min
```

### Rate-of-change alerts

```promql
# Error rate increasing rapidly
deriv(sum(errors_total)[10m]) > 10

# Sudden traffic spike (>50% increase in 5 minutes)
(
  (rate(requests_total[5m]) - rate(requests_total[5m] offset 5m))
  /
  rate(requests_total[5m] offset 5m)
) > 0.5
```

### Multi-condition alerts

```promql
# High error rate AND high latency
(
  sum(rate(errors_total[5m])) / sum(rate(requests_total[5m])) > 0.05
)
and
(
  histogram_quantile(0.95, sum by (le) (rate(latency_bucket[5m]))) > 1
)
```

---

## Vector Matching and Joins

### One-to-one with `on()`

```promql
# Match on specific labels
metric_a * on (job, instance) metric_b
```

### Many-to-one with `group_left`

```promql
# Enrich metrics with labels from info metric
rate(http_requests_total[5m])
* on (job, instance) group_left (version, environment)
  build_info

# Kubernetes: pod metrics with node info
sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{container!=""}[5m]))
* on (namespace, pod) group_left (node, owner_name)
  kube_pod_owner
```

### Conditional joins

```promql
# Only include series where both sides match
metric_a > 100
and on (job, instance)
metric_b > 50

# Exclude series present in right side
metric_a unless on (job) metric_b
```

### Label mismatch workaround

```promql
# Metric A uses "server", Metric B uses "host" — normalize first
label_replace(metric_a, "host", "$1", "server", "(.*)")
* on (host) group_left ()
  metric_b
```

### Vector matching operators

| Operator | Purpose |
|----------|---------|
| `on (labels)` | Match only on specified labels |
| `ignoring (labels)` | Match ignoring specified labels |
| `group_left (labels)` | Many-to-one, copy labels from right side |
| `group_right (labels)` | One-to-many, copy labels from left side |
| `and on ()` | Intersection |
| `or on ()` | Union |
| `unless on ()` | Exclusion |

---

## Pattern Selection

| Goal | Method |
|------|--------|
| Monitor request-driven service | RED (Rate, Errors, Duration) |
| Monitor infrastructure | USE (Utilization, Saturation, Errors) |
| Capacity planning | `predict_linear()`, `deriv()`, trend over long ranges |
| Dashboard visualization | `rate()`, `avg_over_time()` — smooth metrics |
| Spike detection | `irate()`, rate-of-change comparisons |
| SLO tracking | Bucket fraction, histogram quantile vs threshold |

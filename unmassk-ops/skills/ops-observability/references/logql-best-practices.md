# LogQL Best Practices

Rules for writing efficient and correct LogQL queries in Grafana Loki.

---

## Query Pipeline Order

Apply operations from cheapest to most expensive. Loki evaluates left to right.

**Correct order:**
```
stream selector → line filters → parser → label filters → aggregations
```

```logql
# GOOD: cheap operations first
{job="nginx"} |= "error" | json | status_code >= 500 | sum by (namespace) (count_over_time([5m]))

# BAD: parse before line filter — parses every line including non-errors
{job="nginx"} | json | status_code >= 500 |= "error"
```

---

## Stream Selectors

**Use specific selectors.** Loki indexes logs by label combination (stream). More specific = fewer streams = faster query.

```logql
# GOOD
{namespace="production", app="api-server", environment="prod"}

# BAD: too broad, searches too many streams
{namespace="production"}
```

**Never use high-cardinality values as stream labels.** `user_id`, `trace_id`, `request_id`, `session_id`, `ip_address` create one stream per unique value — this destroys performance.

```logql
# BAD: each user_id is a separate stream
{app="api", user_id="12345"}

# GOOD: low-cardinality stream selector, high-cardinality value as line filter
{app="api"} | json | user_id="12345"
```

**Low-cardinality labels safe for stream selectors:** `namespace`, `app`, `environment`, `cluster`, `job`, `host`, `level`.

---

## Line Filters

Line filters are extremely fast — they operate on raw log bytes before any parsing.

| Operator | Meaning |
|----------|---------|
| `\|= "string"` | Contains string |
| `!= "string"` | Does not contain string |
| `\|~ "regex"` | Matches regex |
| `!~ "regex"` | Does not match regex |

**Use `|=` over `|~` when possible.** String contains is significantly faster than regex.

```logql
# GOOD: fast string match
{job="app"} |= "ERROR:"

# BAD: regex for a simple string
{job="app"} |~ "ERROR:"
```

Place line filters before parsers:

```logql
# GOOD: filters out non-error lines before expensive JSON parsing
{app="api"} |= "error" | json | level="error"

# BAD: parses all lines, then filters
{app="api"} | json | level="error"
```

---

## Parsers

Choose the parser appropriate for your log format.

| Log format | Parser | Performance |
|------------|--------|-------------|
| Custom pattern with placeholders | `pattern` | Fastest |
| `key=value` pairs | `logfmt` | Fast |
| JSON | `json` | Moderate |
| Complex extraction | `regexp` | Slowest |

**Performance order: pattern > logfmt > json > regexp**

### json

```logql
# Parse all fields (slower)
{app="api"} | json

# Extract only needed fields (faster)
{app="api"} | json status="response.code", method="request.method"

# Access nested fields
{app="api"} | json item="data.items[0].name"
{app="api"} | json ua="headers[\"User-Agent\"]"
```

### logfmt

```logql
{app="api"} | logfmt

# Strict mode: fail on malformed key=value
{app="api"} | logfmt --strict

# Keep standalone keys as empty labels
{app="api"} | logfmt --keep-empty
```

### pattern

```logql
# Faster than regex for structured formats
{job="nginx"} | pattern "<ip> - - [<timestamp>] \"<method> <path> <_>\" <status>"
```

### regexp

```logql
# Use only when pattern/logfmt/json don't fit
{app="api"} | regexp "(?P<level>\\w+) (?P<message>.*)"
```

**Parse once.** Multiple parsers on the same line are inefficient:

```logql
# BAD
{app="api"} | json | json

# GOOD
{app="api"} | json
```

---

## Label Filters and Dropping

After parsing, filter on extracted fields:

```logql
{app="api"} | json | level="error" | status_code >= 500
```

Drop unnecessary labels to reduce series cardinality in metric queries:

```logql
{app="api"} | json | drop instance, pod | sum by (namespace, app) (rate([5m]))
```

---

## Aggregation Functions

| Goal | Function |
|------|----------|
| Count log lines | `count_over_time({...}[5m])` |
| Rate of log lines | `rate({...}[5m])` |
| Rate in bytes | `bytes_rate({...}[5m])` |
| Sum extracted numeric value | `unwrap field \| sum_over_time([5m])` |
| Percentile of extracted value | `unwrap field \| quantile_over_time(0.95, [5m])` |
| Average of extracted value | `unwrap field \| avg_over_time([5m])` |

**Use `by()` for explicit grouping:**

```logql
sum by (namespace, app) (
  count_over_time({app="api"} | json | level="error" [5m])
)
```

---

## Metric Queries vs Log Queries

**For dashboards and alerts, always use metric queries.**

```logql
# GOOD: returns time series for graphing
rate({app="api"}[5m])

# BAD for a time series panel: returns log lines, not metrics
{app="api"}
```

**Alerts require metric queries:**

```logql
# GOOD: alert when error rate exceeds threshold
sum(rate({app="api"} | json | level="error" [5m])) > 10

# BAD: can't alert on this
{app="api"} | json | level="error"
```

---

## Alerting

**Use `or vector(0)` to prevent "no data" alert states:**

```logql
sum(count_over_time({app="api"} | json | level="error" [5m])) or vector(0)
```

Without this, sparse logs cause the query to return no result, leaving the alert in an indeterminate state.

**Error rate alert:**

```logql
(
  sum(rate({app="api"} | json | level="error" [5m]))
  /
  sum(rate({app="api"}[5m]))
) > 0.05
```

**Absence alert:**

```logql
absent_over_time({app="critical-service"}[5m])    # fires when no logs for 5 min
```

---

## Parse Errors

When parsing fails, Loki sets `__error__` label.

```logql
# See only lines that failed to parse
{app="api"} | json | __error__ != ""

# Production queries: filter out parse errors
{app="api"} | json | __error__="" | level="error"

# Debug: count errors by type
sum by (__error__) (count_over_time({app="api"} | json | __error__ != "" [5m]))
```

Common `__error__` values: `JSONParserErr`, `LogfmtParserErr`, `PatternParserErr`, `RegexpParserErr`.

Always add `| __error__=""` to production dashboard queries.

---

## Structured Metadata (Loki 3.x)

Structured metadata is attached to logs without indexing. Use for high-cardinality values.

```yaml
# In your log shipper config
structured_metadata:
  trace_id: ${TRACE_ID}
  user_id: ${USER_ID}
```

Query syntax (NOT inside stream selector):

```logql
# GOOD: structured metadata filter after stream selector
{app="api"} | trace_id="abc123"

# BAD: structured metadata is not a stream label
{app="api", trace_id="abc123"}
```

Enable in Loki config:

```yaml
limits_config:
  allow_structured_metadata: true
```

### Bloom filter acceleration (Loki 3.3+)

Structured metadata filters placed **before parsers** enable bloom filter acceleration:

```logql
# GOOD: bloom filters can skip irrelevant chunks
{cluster="prod"} | trace_id="abc123" | json

# BAD: parser runs before filter, blooms can't help
{cluster="prod"} | json | trace_id="abc123"
```

---

## Limiting Results

`limit` is an API parameter, not a pipeline operator. There is no `| limit 100` syntax in LogQL.

Set limits via:
- API: `&limit=100`
- Grafana UI: "Line limit" field
- logcli: `--limit=100`

---

## Features That Don't Exist

- `| dedup` — not available. Use metric aggregations instead.
- `| distinct` — proposed but reverted before release.
- `| limit N` — not a pipeline operator.

---

## Recording Rules

Pre-compute expensive LogQL queries as metrics:

```yaml
groups:
  - name: error_rates
    interval: 1m
    rules:
      - record: app:error_rate:1m
        expr: |
          sum by (app) (
            rate({job="kubernetes-pods"} | json | level="error" [1m])
          )
```

Use for: frequently-queried dashboards, complex aggregations, per-tenant alerting.

---

## Quick Checklist

- [ ] Stream selectors are specific (multiple labels)
- [ ] No high-cardinality values in stream selectors
- [ ] Line filters (`|=`) before parsers (`| json`)
- [ ] Exact string matching (`|=`) instead of regex (`|~`) where possible
- [ ] Parser chosen for log format (pattern > logfmt > json > regexp)
- [ ] Only necessary fields extracted from JSON
- [ ] Metric query used for dashboards and alerts
- [ ] `| __error__=""` present in production queries
- [ ] `or vector(0)` in alerting expressions
- [ ] Structured metadata queried with `| key="value"`, not `{key="value"}`
- [ ] Structured metadata filters placed before parsers (for bloom acceleration)

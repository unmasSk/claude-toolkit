# Loki Configuration Best Practices

Production deployment rules for Grafana Loki.

---

## Schema (CRITICAL — Irreversible)

Always use TSDB + v13 for new deployments. Schema cannot be changed after deployment without migration.

```yaml
schema_config:
  configs:
    - from: "2025-01-01"    # Set to your deployment date, not a past date
      store: tsdb
      object_store: s3
      schema: v13
      index:
        prefix: loki_index_
        period: 24h
```

**Why TSDB + v13:** best query performance, supports structured metadata, enables bloom filters. Daily period (`24h`) is the standard for most deployments.

**Deprecated stores:** `boltdb-shipper`, `bigtable`, `dynamodb`, `cassandra`. Migrate to TSDB.

---

## Deployment Modes

| Mode | Ingestion | Complexity | Use case |
|------|-----------|------------|----------|
| Monolithic | < 100 GB/day | Low | Development, testing |
| Simple Scalable | 100 GB – 1 TB/day | Medium | Production (recommended) |
| Microservices | > 1 TB/day | High | Large scale, multi-tenancy |

**Simple Scalable** separates read, write, and backend components. Horizontal scaling per tier. This is the default recommendation for production.

---

## Storage

**Object storage in production.** Filesystem is for development only.

```yaml
common:
  storage:
    s3:
      s3: s3://us-east-1/my-loki-bucket
      s3forcepathstyle: false
      # Use IAM role — do not hardcode access keys
  replication_factor: 3
```

Use IAM roles (AWS), service accounts (GCP), or managed identities (Azure). Never hardcode credentials.

---

## Replication

Always use `replication_factor: 3` in production. Tolerates 2 simultaneous node failures.

```yaml
common:
  replication_factor: 3
```

Enable zone-aware replication for multi-AZ deployments:

```yaml
ingester:
  lifecycler:
    ring:
      zone_awareness_enabled: true
```

---

## Cardinality Control

High cardinality is the most common cause of Loki performance problems. Each unique label combination creates a stream. Too many streams cause memory exhaustion and slow ingest.

**Set hard limits:**

```yaml
limits_config:
  max_streams_per_user: 10000
  max_global_streams_per_user: 100000
  max_label_names_per_series: 15
```

**Rules for labels:**
- Low-cardinality data → use as stream label: `namespace`, `app`, `environment`, `job`, `cluster`
- High-cardinality data → use line filters or structured metadata: `user_id`, `trace_id`, `request_id`, `pod_uid`

---

## Limits Configuration

```yaml
limits_config:
  ingestion_rate_mb: 50
  ingestion_burst_size_mb: 100    # 2× rate for bursts
  max_line_size: 256KB
  max_line_size_truncate: true    # truncate instead of reject

  retention_period: 30d           # requires compactor.retention_enabled: true
```

---

## Retention

```yaml
compactor:
  retention_enabled: true
  retention_delete_delay: 2h

limits_config:
  retention_period: 30d

# Per-stream retention (optional)
limits_config:
  retention_stream:
    - selector: '{namespace="prod"}'
      priority: 1
      period: 720h    # 30 days for prod
    - selector: '{namespace="dev"}'
      priority: 2
      period: 168h    # 7 days for dev
```

---

## Chunk Configuration

```yaml
ingester:
  chunk_encoding: snappy          # best speed/compression balance
  chunk_target_size: 1572864      # 1.5 MB — requires 5–10× raw log volume
  chunk_idle_period: 30m          # flush inactive chunks
  max_chunk_age: 2h               # flush old chunks regardless of activity
```

More streams = more chunks in memory. Keep stream cardinality low.

---

## Caching (Production)

TSDB does NOT need an index cache. Use chunk cache and results cache only.

```yaml
chunk_store_config:
  chunk_cache_config:
    memcached:
      batch_size: 256
      parallelism: 10
    memcached_client:
      host: memcached-chunks.loki.svc.cluster.local
      timeout: 500ms

query_range:
  cache_results: true
  results_cache:
    cache:
      memcached_client:
        host: memcached-results.loki.svc.cluster.local
        timeout: 500ms
```

Use separate Memcached instances for chunks and results.

---

## Security

```yaml
# Always enable in multi-tenant deployments
auth_enabled: true
```

Deploy an authenticating reverse proxy to enforce `X-Scope-OrgID` header. Never disable auth in shared environments.

```yaml
server:
  http_tls_config:
    cert_file: /path/to/cert.pem
    key_file: /path/to/key.pem
```

---

## OTLP Ingestion (Loki 3.0+)

```yaml
limits_config:
  allow_structured_metadata: true
  otlp_config:
    resource_attributes:
      attributes_config:
        - action: index_label      # Low cardinality → index label
          attributes:
            - service.name
            - service.namespace
            - deployment.environment
        - action: structured_metadata    # High cardinality → structured metadata
          attributes:
            - k8s.pod.name
            - service.instance.id
```

Do NOT add `k8s.pod.name` or `service.instance.id` as index labels — they are high-cardinality and will cause stream explosion.

Use `otlphttp` exporter in OpenTelemetry Collector. The `lokiexporter` is deprecated.

---

## Pattern Ingester (Loki 3.0+)

Enable for automatic log pattern detection (powers Explore Logs / Grafana Drilldown):

```yaml
pattern_ingester:
  enabled: true
```

Minimal resource overhead. Enable in all deployments on Loki 3.0+.

---

## Query Performance

```yaml
querier:
  max_concurrent: 4       # start here, increase with CPU/memory
  query_timeout: 5m

query_range:
  parallelise_shardable_queries: true
  split_queries_by_interval: 15m    # for large time ranges
```

---

## Bloom Filters (Experimental, Loki 3.3+)

For large-scale deployments (> 75 TB/month). Accelerates "needle in haystack" queries on structured metadata.

Breaking change in Loki 3.3: bloom filters use structured metadata only (not free-text). Delete existing bloom blocks before upgrading.

```yaml
bloom_build:
  enabled: true
  planner:
    planning_interval: 6h

bloom_gateway:
  enabled: true
  worker_concurrency: 4

limits_config:
  bloom_creation_enabled: true
  bloom_gateway_enable_filtering: true
  tsdb_sharding_strategy: bounded
```

**Query pattern for bloom acceleration:** structured metadata filter BEFORE parsers.

```logql
# GOOD: bloom filters can skip irrelevant chunks
{cluster="prod"} | trace_id="abc123" | json

# BAD: parser runs first
{cluster="prod"} | json | trace_id="abc123"
```

---

## Thanos Storage Client (Loki 3.4+)

Opt-in in 3.4, will be default in future. Mutually exclusive with legacy storage config.

```yaml
storage_config:
  use_thanos_objstore: true
  object_store:
    s3:
      bucket_name: my-loki-bucket
      endpoint: s3.us-east-1.amazonaws.com
      region: us-east-1
```

Migration notes:
- `disable_dualstack` → `dualstack_enabled` (inverted)
- `signature_version` removed (always V4)
- `http_config` → `http` nested block
- Storage prefix cannot contain dashes — use underscores

---

## Deprecated Tools

| Tool | Status | Replacement |
|------|--------|-------------|
| Promtail | Deprecated in Loki 3.4, support ends 2026-02-28 | Grafana Alloy |
| Grafana Agent | Long-term support ended 2025-10-31 | Grafana Alloy |
| lokiexporter (OTel) | Deprecated | `otlphttp` exporter |
| boltdb-shipper | Deprecated index store | TSDB |

Migrate Promtail configs: `alloy convert --source-format=promtail`

---

## Resource Planning

**Ingester memory:** ~1 GB base + 1–2 KB per active stream.

| Active streams | Minimum memory |
|----------------|---------------|
| 10,000 | ~1.2 GB |
| 50,000 | ~2 GB |
| 100,000 | ~3 GB |

**Storage estimate:**
```
daily_storage = (ingestion_MB_per_sec × 86400) / compression_ratio
```

Compression ratios with snappy: text logs ~5–10×, JSON ~3–7×, structured ~2–5×.

**Kubernetes resource recommendations:**

```yaml
# Ingester
resources:
  requests: { memory: "4Gi", cpu: "1" }
  limits: { memory: "8Gi", cpu: "2" }

# Querier
resources:
  requests: { memory: "2Gi", cpu: "1" }
  limits: { memory: "4Gi", cpu: "2" }
```

---

## Health Check Probes

```yaml
livenessProbe:
  httpGet:
    path: /ready
    port: 3100
  initialDelaySeconds: 45

readinessProbe:
  httpGet:
    path: /ready
    port: 3100
  initialDelaySeconds: 45
```

---

## Validation Before Deployment

```bash
# Validate config syntax
loki -config.file=loki.yaml -verify-config

# Print effective config
loki -config.file=loki.yaml -print-config-stderr

# Check health after deploy
curl http://loki:3100/ready
```

---

## Key Metrics to Monitor

| Metric | Alert when |
|--------|-----------|
| `loki_ingester_memory_streams` | Growing unexpectedly (cardinality explosion) |
| `loki_distributor_ingester_append_failures_total` | Non-zero sustained rate |
| `loki_request_duration_seconds` | P99 > configured query_timeout |
| `loki_ingester_chunks_flushed_total` | Flush rate drops to zero |

---

## Common Problems

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| OOMKilled pods | Too many streams | Lower `max_streams_per_user`, audit label cardinality |
| Query timeouts | Slow queries | Enable parallelization, add caching, optimize LogQL |
| Ingestion failures | Rate limit hit | Increase `ingestion_rate_mb` or add ingesters |
| Storage growing fast | No retention | Enable `compactor.retention_enabled` |

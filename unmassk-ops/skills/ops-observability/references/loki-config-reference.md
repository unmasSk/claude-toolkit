# Loki Configuration Reference

Current stable release: **Loki 3.6.2** (November 2025).

Configuration file passed via `-config.file=loki.yaml`. CLI flags override file values.

---

## server

HTTP and gRPC server settings.

```yaml
server:
  http_listen_port: 3100           # default: 3100
  grpc_listen_port: 9095           # default: 9095
  log_level: info                  # debug | info | warn | error
  log_format: logfmt               # logfmt | json
  graceful_shutdown_timeout: 30s
  http_server_read_timeout: 30s
  http_server_write_timeout: 30s
  http_server_idle_timeout: 120s
  grpc_server_max_concurrent_streams: 100

  http_tls_config:
    cert_file: /path/to/cert.pem
    key_file: /path/to/key.pem
    client_ca_file: /path/to/ca.pem

  grpc_tls_config:
    cert_file: /path/to/cert.pem
    key_file: /path/to/key.pem
```

---

## common

Shared settings across components.

```yaml
common:
  path_prefix: /loki
  instance_addr: ""                # for ring registration
  replication_factor: 3            # always 3 in production

  storage:
    s3:
      s3: s3://region/bucket-name
      s3forcepathstyle: false
      # Use IAM role — avoid access_key_id / secret_access_key
    gcs:
      bucket_name: my-loki-bucket
    azure:
      container_name: loki
      use_managed_identity: true
    filesystem:
      chunks_directory: /loki/chunks    # dev/test only

  ring:
    kvstore:
      store: memberlist    # memberlist | consul | etcd | inmemory
```

---

## schema_config

Critical — cannot be changed after deployment without data migration.

```yaml
schema_config:
  configs:
    - from: "2025-01-01"     # deployment date (YYYY-MM-DD)
      store: tsdb             # tsdb recommended; boltdb-shipper deprecated
      object_store: s3        # s3 | gcs | azure | filesystem
      schema: v13             # v13 is current; v11/v12 are legacy
      index:
        prefix: loki_index_
        period: 24h           # 24h recommended
```

For migrations from boltdb to TSDB, add a new entry with a future start date:

```yaml
schema_config:
  configs:
    - from: 2020-01-01
      store: boltdb-shipper
      schema: v11
    - from: 2025-01-01       # new entries pick up from here
      store: tsdb
      schema: v13
```

---

## storage_config

### Legacy storage

```yaml
storage_config:
  tsdb_shipper:
    active_index_directory: /loki/tsdb-index
    cache_location: /loki/tsdb-cache
    cache_ttl: 24h
    index_gateway_client:
      server_address: dns+loki-backend.loki.svc.cluster.local:9095

  aws:
    s3: s3://region/bucket
    s3forcepathstyle: false
```

### Thanos object storage client (Loki 3.4+)

Mutually exclusive with legacy storage config.

```yaml
storage_config:
  use_thanos_objstore: true
  object_store:
    storage_prefix: loki_chunks    # no dashes allowed
    s3:
      bucket_name: my-loki-bucket
      endpoint: s3.us-east-1.amazonaws.com
      region: us-east-1
      native_aws_auth_enabled: true     # use IAM role
      dualstack_enabled: false          # note: inverted from old disable_dualstack
      storage_class: STANDARD
      http:
        idle_conn_timeout: 1m30s
        response_header_timeout: 2m
      sse:
        type: SSE-S3
```

---

## ingester

```yaml
ingester:
  chunk_encoding: snappy            # snappy | gzip | lz4 | none
  chunk_idle_period: 30m
  chunk_retain_period: 15m
  max_chunk_age: 2h
  chunk_target_size: 1572864        # 1.5 MB
  concurrent_flushes: 16
  flush_check_period: 30s

  wal:
    enabled: true
    dir: /loki/wal
    flush_on_shutdown: true

  lifecycler:
    ring:
      kvstore:
        store: memberlist
      replication_factor: 3
    num_tokens: 128
    heartbeat_period: 5s
    final_sleep: 30s
```

---

## distributor

```yaml
distributor:
  ring:
    kvstore:
      store: memberlist

  # OTLP: configure which resource attributes become index labels
  otlp_config:
    default_resource_attributes_as_index_labels:
      - service.name
      - service.namespace
      - deployment.environment
      - cloud.region
      - k8s.cluster.name
      - k8s.namespace.name
      - k8s.container.name
      - k8s.deployment.name
      - k8s.statefulset.name
      # DO NOT include: k8s.pod.name, service.instance.id (high cardinality)

  ingest_limits_enabled: false      # Loki 3.5+
```

---

## querier

```yaml
querier:
  max_concurrent: 4                 # per querier instance; tune up with resources
  query_timeout: 5m
  tail_max_duration: 1h
  extra_query_delay: 0s
  multi_tenant_queries_enabled: false

  engine:
    timeout: 5m
    max_look_back_period: 30s
```

---

## frontend

```yaml
frontend:
  max_outstanding_per_tenant: 2048
  compress_responses: true
  encoding: protobuf                # protobuf | json
  log_queries_longer_than: 0s       # set to 5s to log slow queries
  downstream_url: ""
```

---

## query_range

```yaml
query_range:
  align_queries_with_step: false
  max_retries: 5
  parallelise_shardable_queries: true
  cache_results: true

  results_cache:
    cache:
      memcached_client:
        host: memcached-results.loki.svc.cluster.local
        timeout: 500ms
        max_idle_conns: 16
        consistent_hash: true
```

---

## compactor

```yaml
compactor:
  working_directory: /loki/compactor
  compaction_interval: 10m
  retention_enabled: false          # set true to enable retention
  retention_delete_delay: 2h
  retention_delete_worker_count: 150
  delete_request_store: sqlite      # Loki 3.5+: sqlite preferred over boltdb

  # Horizontal scaling (Loki 3.6+)
  horizontal_scaling_mode: disabled    # disabled | main | worker
```

---

## limits_config

```yaml
limits_config:
  # Ingestion
  ingestion_rate_mb: 4              # default 4 MB/s — increase for production
  ingestion_burst_size_mb: 6        # default 6 MB
  max_line_size: 262144             # 256 KB
  max_line_size_truncate: false

  # Streams
  max_streams_per_user: 10000
  max_global_streams_per_user: 5000
  max_label_names_per_series: 15    # reduced from 30 in Loki 3.0
  max_label_name_length: 1024
  max_label_value_length: 2048

  # Queries
  max_entries_limit_per_query: 5000
  max_query_length: 721h            # ~30 days
  max_query_parallelism: 32
  max_query_series: 500
  max_chunks_per_query: 2000000
  split_queries_by_interval: 30m

  # Retention (requires compactor.retention_enabled: true)
  retention_period: 0               # 0 = no retention; e.g. 720h for 30 days
  retention_stream:
    - selector: '{namespace="prod"}'
      priority: 1
      period: 720h

  # Structured metadata (Loki 2.9+)
  allow_structured_metadata: true
  max_structured_metadata_size: 65536       # 64 KB
  max_structured_metadata_entries_count: 128

  # Volume API (Explore Logs)
  volume_enabled: true

  # OTLP (Loki 3.0+)
  otlp_config:
    resource_attributes:
      ignore_defaults: false
      attributes_config:
        - action: index_label
          attributes:
            - service.name
            - service.namespace
            - deployment.environment
        - action: structured_metadata
          attributes:
            - k8s.pod.name
            - service.instance.id
      log_attributes:
        - action: structured_metadata
          attributes:
            - trace_id
            - span_id

  # Time sharding for out-of-order ingestion (Loki 3.4+)
  shard_streams:
    enabled: false
    time_sharding_enabled: false

  # Bloom filters (Loki 3.0+, experimental)
  bloom_creation_enabled: false
  bloom_gateway_enable_filtering: false
  tsdb_sharding_strategy: ""        # set "bounded" when using blooms

  # Ruler
  ruler_max_rules_per_rule_group: 100
  ruler_max_rule_groups_per_tenant: 50

  # Metric aggregation
  metric_aggregation_enabled: false
```

---

## ruler

```yaml
ruler:
  evaluation_interval: 1m
  poll_interval: 1m
  enable_api: false
  enable_sharding: false
  enable_alertmanager_v2: true     # default since Loki 3.2.0

  storage:
    type: local
    local:
      directory: /rules

  rule_path: /tmp/rules
  alertmanager_url: http://alertmanager:9093

  for_outage_tolerance: 1h
  for_grace_period: 10m
  resend_delay: 1m

  remote_write:
    enabled: false
    client:
      url: http://prometheus:9090/api/v1/write
      remote_timeout: 30s
```

Rule files must be at: `/rules/<tenant-id>/rules.yaml`

---

## pattern_ingester

```yaml
pattern_ingester:
  enabled: false                   # enable in Loki 3.0+ deployments

  metric_aggregation:
    enabled: false
    loki_address: ""
```

---

## bloom_build / bloom_gateway

Experimental. Only for deployments > 75 TB/month. Delete existing bloom blocks before upgrading to Loki 3.3+.

```yaml
bloom_build:
  enabled: false
  planner:
    planning_interval: 6h
    bloom_split_series_keyspace_by: 1024

bloom_gateway:
  enabled: false
  worker_concurrency: 4
  block_query_concurrency: 8
```

---

## memberlist

```yaml
memberlist:
  join_members:
    - loki-memberlist               # Kubernetes headless service name
  bind_port: 7946
  gossip_interval: 200ms
  gossip_nodes: 3
```

---

## Caching

```yaml
chunk_store_config:
  chunk_cache_config:
    memcached:
      batch_size: 256
      parallelism: 10
    memcached_client:
      host: memcached-chunks.loki.svc.cluster.local
      timeout: 500ms
      max_idle_conns: 100

# Results cache — see query_range.results_cache above
```

TSDB does not need an index cache. Only chunk cache and results cache are needed.

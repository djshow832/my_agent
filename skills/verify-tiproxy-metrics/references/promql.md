# PromQL And Threshold Reference

## Source-of-Truth Metric Definitions

- TiProxy migration metrics:
  - `tiproxy_balance_b_conn`
  - `tiproxy_balance_migrate_total`
  - `tiproxy_balance_pending_migrate`
  - `tiproxy_balance_migrate_duration_seconds`
  - code: `pkg/metrics/balance.go`
- TiProxy migration reason source:
  - reason comes from factor name (`status`, `health`, `memory`, `cpu`, `location`, `conn`, `test`)
  - code: `pkg/balance/factor/*.go`, `pkg/balance/router/router_score.go`
- TiDB connection/cpu metrics:
  - `tidb_server_connections`
  - `tidb_server_maxprocs`
  - `process_cpu_seconds_total`
  - code: `/Users/zhangming/gopath/src/github.com/pingcap/tidb/pkg/metrics/server.go`

## Base Filter Placeholders

Use these placeholders in all queries:

- `<CLUSTER_FILTER>`: cluster labels, for example `k8s_cluster="...",tidb_cluster="..."`
- `<TP_FILTER>`: `<CLUSTER_FILTER>,instance=~"<tiproxy_instance_regex>"`
- `<TIDB_FILTER>`: `<CLUSTER_FILTER>,instance=~"<tidb_instance_regex>"`

## TiProxy Migration Queries

### 1) Backend connection distribution

```promql
tiproxy_balance_b_conn{<TP_FILTER>}
```

### 2) Success/fail migration by direction and reason (10m)

```promql
sum by (from, to, reason, migrate_res) (
  increase(tiproxy_balance_migrate_total{<TP_FILTER>}[10m])
)
```

### 3) Migration fail ratio (10m)

```promql
sum(increase(tiproxy_balance_migrate_total{<TP_FILTER>,migrate_res="fail"}[10m]))
/
clamp_min(sum(increase(tiproxy_balance_migrate_total{<TP_FILTER>}[10m])), 1)
```

### 4) Pending migration

```promql
tiproxy_balance_pending_migrate{<TP_FILTER>}
```

### 5) Migration reason distribution (10m)

```promql
sum by (reason) (
  increase(tiproxy_balance_migrate_total{<TP_FILTER>,migrate_res="succeed"}[10m])
)
```

### 6) Migration pressure (10m)

```promql
sum(increase(tiproxy_balance_migrate_total{<TP_FILTER>,migrate_res="succeed"}[10m]))
/
clamp_min(avg(sum(tiproxy_balance_b_conn{<TP_FILTER>})), 1)
```

## TiDB CPU And Connection Queries

### 7) TiDB connections

```promql
tidb_server_connections{<TIDB_FILTER>}
```

### 8) TiDB normalized CPU (TiUP labels)

```promql
irate(process_cpu_seconds_total{<TIDB_FILTER>,job="tidb"}[30s])
/
tidb_server_maxprocs{<TIDB_FILTER>}
```

### 9) TiDB normalized CPU (TiOperator labels)

```promql
irate(process_cpu_seconds_total{<TIDB_FILTER>,component="tidb"}[30s])
/
tidb_server_maxprocs{<TIDB_FILTER>}
```

Use the non-empty result between query 8 and query 9.

## Address Mapping Queries

Use these only to align TiProxy SQL-address labels and TiDB `instance` labels.

### 10) Host view from TiProxy backend labels (TiUP-style)

```promql
sum by (host) (
  label_replace(
    tiproxy_balance_b_conn{<TP_FILTER>},
    "host", "$1", "backend", "([^:]+):.*"
  )
)
```

### 11) Host view from TiDB instance labels (TiUP-style)

```promql
sum by (host) (
  label_replace(
    tidb_server_connections{<TIDB_FILTER>},
    "host", "$1", "instance", "([^:]+):.*"
  )
)
```

### 12) Pod view for TiOperator

```promql
sum by (pod) (
  label_replace(
    tiproxy_balance_b_conn{<TP_FILTER>},
    "pod", "$1", "backend", "(.+-tidb-[0-9]+).*"
  )
)
```

```promql
sum by (pod) (
  label_replace(
    tidb_server_connections{<TIDB_FILTER>},
    "pod", "$1", "instance", "(.+-tidb-[0-9]+).*"
  )
)
```

## Ping-Pong Pair Queries

Given pair `A`, `B`:

```promql
sum(increase(tiproxy_balance_migrate_total{<TP_FILTER>,from="A",to="B",migrate_res="succeed"}[10m]))
```

```promql
sum(increase(tiproxy_balance_migrate_total{<TP_FILTER>,from="B",to="A",migrate_res="succeed"}[10m]))
```

Compute:

```text
pair_balance = abs(AB - BA) / max(AB + BA, 1)
```

Treat as ping-pong candidate when:

- `AB >= 20`
- `BA >= 20`
- `pair_balance < 0.3`

## Practical Threshold Rubric

Use these defaults unless the user provides SLO-specific thresholds:

- Offline drain fail ratio:
  - `<= 0.1`: good
  - `(0.1, 0.3]`: warn
  - `> 0.3`: fail
- Steady-state CPU ratio `max/min`:
  - `<= 1.5`: good
  - `(1.5, 2.0]`: warn
  - `> 2.0`: fail
- Connection ratio `max/min`:
  - `<= 1.2`: aligned with TiProxy conn-balance threshold
- Migration pressure per 10m:
  - `<= 0.1`: low
  - `(0.1, 0.3]`: medium
  - `> 0.3`: high, inspect thrash


---
name: verify_tiproxy_metrics
description: Determine whether TiProxy migrates backend connections correctly using TiProxy and TiDB metrics. Use when validating TiDB scale-in or shutdown drain behavior, checking steady-state CPU/load balance with no topology change, diagnosing migration thrash (A->B->A ping-pong), or producing a PASS/WARN/FAIL migration health verdict with PromQL evidence.
---

# Verify TiProxy Metrics

## Overview

Use this skill to judge whether TiProxy connection migration is normal with metrics-only evidence and return a clear `PASS` / `WARN` / `FAIL`.

## Execute Workflow

1. Define scenario and observation windows.
2. Load [references/promql.md](references/promql.md) and collect required metrics.
3. Evaluate check 1 (offline drain), check 2 (steady-state CPU/load balance), and check 3 (anti-thrash).
4. Return a structured verdict with evidence, caveats, and tuning suggestions.

## Define Inputs

- `cluster_filter`: metric labels for target cluster (for example `k8s_cluster` and `tidb_cluster`)
- `event_window`: offline event window, default `t0-5m` to `t1+10m`
- `steady_window`: stable window without topology change, default `30m`
- `target_backend`: TiDB SQL address from TiProxy labels (`ip:4000` or pod service address)

Map addresses before comparing TiProxy and TiDB metrics:
- TiProxy `from`/`to`/`backend` labels use TiDB SQL address.
- TiDB `instance` label usually uses status address (`ip:10080`, TiUP) or pod name (TiOperator).
- Use mapping queries in [references/promql.md](references/promql.md).

## Evaluate Check 1: Offline Drain Correctness

Judge a downscaled TiDB backend as normal only if all items hold:

- `increase(tiproxy_balance_migrate_total{from=target_backend,migrate_res="succeed"}[event_window]) > 0`
- `tiproxy_balance_b_conn{backend=target_backend}` drops close to `0` and keeps near `0`
- `tiproxy_balance_pending_migrate{from=target_backend,...}` returns to `0`
- The increase on other backends' `tiproxy_balance_b_conn` roughly matches the source decrease (allow 10%-20% noise)
- `tidb_server_connections` trend after address mapping matches TiProxy-side trend

Mark `WARN` or `FAIL` if any condition appears:

- source backend is not drained after grace period
- migrate fail ratio `fail/(succeed+fail)` > `0.1` (`WARN`) or > `0.3` (`FAIL`)
- pending migrate stays non-zero for more than 3 scrape points
- reason stays dominated by `conn` during offline drain (expect `status`/`health` first)

## Evaluate Check 2: Steady-State CPU/Load Balance

Require no topology change in `steady_window`.

Use normalized TiDB CPU:
- `irate(process_cpu_seconds_total[30s]) / tidb_server_maxprocs` by backend

Judge with this rubric:

- `PASS`: `max(cpu_norm)/max(min(cpu_norm),0.01) <= 1.5`
- `WARN`: ratio in `(1.5, 2.0]`
- `FAIL`: ratio `> 2.0`

Cross-check connection distribution:
- `max(tiproxy_balance_b_conn)/max(min(...),1) <= 1.2` is aligned with TiProxy conn-balance threshold.

If CPU divergence is large but migration reasons are mostly `conn`, report possible policy/config mismatch.

## Evaluate Check 3: Anti-Thrash / Ping-Pong

Use rolling 10-minute windows.

Detect thrash when one or more rules are true:

- Same pair has high bidirectional migration:
  `A->B >= 20`, `B->A >= 20`, and `abs(A->B-B->A)/(A->B+B->A) < 0.3`
- The pattern above repeats in at least 3 consecutive windows
- Migration pressure is high without topology/health event:
  `increase(success_migrate_total[10m]) / avg(total_backend_connections)` > `0.3`
- `reason="conn"` dominates while CPU gap is small (`< 10%`)

## Produce Output

Return exactly this structure:

```text
Verdict: PASS|WARN|FAIL
1) Drain correctness:
- ...
2) Steady-state CPU and connection balance:
- ...
3) Thrash risk:
- ...
Key evidence:
- <query> -> <value>/<timestamp>
Action:
- keep config | tune balance.conn-count.count-ratio-threshold | tune balance.*.migrations-per-second
```

Always include:

- concrete values and timestamps
- top migration pairs and reasons
- mapping method used (TiUP `ip:10080` or TiOperator pod name)
- missing-metrics caveats

## Tune Configuration Carefully

When check 3 fails first:
- reduce `balance.conn-count.migrations-per-second`
- increase `balance.conn-count.count-ratio-threshold` moderately (above 1.2)
- avoid forcing high `balance.cpu.migrations-per-second` unless CPU hotspot is sustained

When check 1 fails because offline drain is slow:
- increase `balance.status.migrations-per-second`
- inspect health-check latency and TiDB graceful shutdown timing

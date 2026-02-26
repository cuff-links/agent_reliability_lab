# Airflow Warehouse Timeout Runbook

When `load_warehouse` fails with a timeout:

1. Check the warehouse cluster status in Grafana dashboard `warehouse-latency`.
2. If queue depth > 100 and latency > 5s, scale the cluster via `kubectl scale deployment warehouse-writer`.
3. Re-run the failing task from the Airflow UI.
4. If timeouts persist, page the Data Infra on-call.

Indicators:

- Repeated `Timeout while waiting for warehouse cluster` in logs
- Cluster `warehouse-cluster-3` CPU > 85%
- Dag owner: data-platform

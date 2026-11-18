# PulseIQ API Example Responses

## Health Check

GET /health

Healthy response: `{"status":"healthy","database":"connected"}`

## KPI Endpoints

The following endpoints were tested successfully:

- `GET /metrics/M01` - Headcount
- `GET /metrics/M04` - Monthly Attrition Rate
- `GET /metrics/M07` - Gross Pay
- `GET /metrics/M22` - Task Completion Rate
- `GET /metrics/M27` - High-Risk Share

Each response contains metric metadata, record_count, and a data array of aggregate records.

## Lineage Endpoints

- `GET /lineage/M01`
- `GET /lineage/M04`
- `GET /lineage/M07`
- `GET /lineage/M22`
- `GET /lineage/M27`

Each returns the metric name, source table, published view, and lineage steps.

## Freshness

`GET /freshness` returns the latest source date for each KPI, last successful ETL validation, hosted refresh log timestamp, and database file modification timestamp.

## Dashboard Consumption

Another dashboard can consume PulseIQ through HTTP requests without connecting directly to DuckDB.

Example Python integration:

```python
import requests

API_BASE = "http://127.0.0.1:8000"

response = requests.get(f"{API_BASE}/metrics/M01", params={"limit": 100}, timeout=30)
response.raise_for_status()
result = response.json()

print(result["name"])
print(result["data"])
```

## Deployment Instructions

1. Activate the project virtual environment.
2. Ensure the DuckDB database path is configured correctly.
3. Start the API using:

```bash
uvicorn src.metrics_api:app --host 0.0.0.0 --port 8000
```

4. Make the API accessible to the dashboard through a secured network.
5. Configure HTTPS, authentication, database permissions and monitoring before public deployment.

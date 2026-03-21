# Change: AI session dataset sync via Redis and exportable JSON dumps

## Why

- Gmail summarization and Google ADK paths need a **consistent, inspectable dataset** of requests and responses for evaluation and debugging.
- The **redis-log** stack (Caddy warn/error → [redis-log-sink](../../../redis-log-sink/main.py)) exists but **ai-service** and **ai-service-adk** do not emit structured session data into it today.
- Operators need a **single JSON artifact** per run or shutdown that merges relevant streams for offline analysis.

## What Changes

- Add OpenSpec capability **ai-session-dataset**: normative requirements for Redis stream ingestion, per-event annotations, dump file shape, reusable export script, and static-hosting safety for `frontend/public/datasets/`.
- Add machine-readable **JSON Schema** for the dump root object and event records under this change.
- **Implementation** (follows approval; tracked in [tasks.md](./tasks.md)): wire both AI services to `redis-log`, extend redis-log-sink or equivalent for graceful shutdown export, add `scripts/dump-ai-data-session.py`, docker-compose/k8s volume mounts, `.gitignore`, optional nginx/Vite exclusion for `/datasets/`.

## Impact

- Affected specs: new capability `ai-session-dataset` (delta only until archived).
- Affected code (later): [ai-service](../../../ai-service/), [ai-service-adk](../../../ai-service-adk/), [redis-log-sink](../../../redis-log-sink/), [docker-compose.yml](../../../docker-compose.yml), [k8s/manifests/redis.yaml](../../../k8s/manifests/redis.yaml), [frontend](../../../frontend/) static config, [scripts](../../../scripts/).

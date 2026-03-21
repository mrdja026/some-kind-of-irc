## Context

Ephemeral **redis-log** holds Redis streams; **redis-log-sink** ingests Caddy TCP JSON for warn/error into `caddy:warn_error_logs`. AI traffic does not use that path. This change specifies a **second stream** for annotated AI session events and a **merged export** to `frontend/public/datasets/{timestamp}-data-session.json`.

Stakeholders: developers evaluating CrewAI vs ADK Gmail behavior; operators capturing incident context alongside Caddy errors.

## Goals / Non-Goals

**Goals**

- One **documented JSON shape** (spec + JSON Schema) for session dumps.
- **Annotated** AI events: `source`, `kind`, `backend`, `recorded_at` at minimum.
- **Graceful shutdown** export from the component that owns the dump (see Decisions).
- **Reusable script** that produces the same JSON without relying on shutdown alone.

**Non-Goals**

- Cloud upload, encryption at rest, or long-term retention policy (beyond stream maxlen).
- Cross-pod ordering guarantees in multi-replica k8s (MVP assumes single redis-log + single sink or coordinated export).

## Decisions

1. **Stream layout:** Use a dedicated key on **redis-log**, e.g. `ai:session_events`, separate from `caddy:warn_error_logs`. **ai-service** and **ai-service-adk** **XADD** directly (decode at export); Caddy traffic stays on the existing TCP → sink path for warn/error only.

2. **Dump owner:** Prefer extending **redis-log-sink** with signal handlers (**SIGTERM** / **SIGINT**) that **XRANGE** configured stream key(s), normalize entries into the dump `events` array, and write the file. Alternative documented in spec: run the same logic via the **reusable script** in a preStop hook or manually.

3. **Timestamp in filename:** UTC, filename-safe ISO-like string, e.g. `2026-03-21T14-30-00Z` (colons replaced) → `{timestamp}-data-session.json`.

4. **Payload policy:** Internal/trusted deployments may store **full** request/response bodies (including email content) in `payload`; spec calls out that this is inappropriate for untrusted production without additional controls.

5. **`frontend/public/datasets/` trade-off:** Satisfies “dump in public folder” for local path stability and gitignored artifacts. **Risk:** default static hosting may expose `/datasets/`. Mitigation: `.gitignore` for `*.json` under that tree and **block or relocate** `/datasets/` in production static config (tasks).

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Sensitive data in web-accessible tree | Gitignore dumps; document; optional nginx deny for `/datasets/` |
| Stream memory growth | **MAXLEN** on `XADD` (~ approximate cap); tune in implementation |
| Sink restart loses ephemeral redis-log data | Expected; operators use script before teardown or accept loss |

## Migration Plan

1. Land OpenSpec change; validate `--strict`.
2. Implement streams + emission + dump + script; mount host path for dumps in compose/k8s.
3. Verify `deploy_local.sh --build` and `pixi run python-lint`.

## Open Questions

- Exact **MAXLEN** for `ai:session_events` (implementation task).
- Whether to include **non-Gmail** `/ai/*` routes in v1 (spec allows `generic_ai` kind).

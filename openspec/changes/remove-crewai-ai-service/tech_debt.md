# Technical Debt: Remove CrewAI ai-service

## Implementation Summary

**Completed**: 2026-03-23  
**Lines removed**: ~3,200  
**Files deleted**: 15  
**Files modified**: 15  

## Tradeoffs Accepted

### 1. Loss of Local Q&A Feature

**What was lost**: Users could ask art/photography questions to a local vLLM (phi3-mini) without API costs.

**Why accepted**: 
- Low feature adoption
- vLLM infrastructure added operational complexity
- CrewAI-specific patterns didn't translate to ADK

**Future consideration**: If local inference demand grows, implement via ADK with Ollama backend.

### 2. Loss of A/B Testing Infrastructure

**What was lost**: Ability to switch between CrewAI and ADK backends for comparison.

**Why accepted**:
- A/B testing completed; ADK selected as winner
- Maintaining dead toggle code adds confusion

**Future consideration**: If new AI backend options emerge, rebuild toggle from scratch (simpler than maintaining dormant code).

### 3. localStorage Orphan Data

**What was lost**: Nothing - existing `ai-backend-preference` keys remain but are ignored.

**Why accepted**:
- Deleting localStorage from code is complex and has side effects
- Orphan data has zero functional impact
- Users can clear manually if desired

**Future consideration**: If localStorage keys accumulate, add a "clear preferences" settings option.

### 4. Single Point of Failure

**What was lost**: Redundancy of two AI inference backends.

**Why accepted**:
- ADK service is production-tested
- Maintaining two services for redundancy is expensive
- ADK has its own resilience (LiteLLM retry logic)

**Future consideration**: Add health monitoring and alerting for ADK service.

### 5. Route Path Consolidation

**What changed**: All AI routes now use `/adk/ai/*` prefix instead of direct `/ai/*`.

**Why accepted**:
- Consistent routing pattern through Caddy reverse proxy
- ADK strips `/adk` prefix, so internal paths remain `/ai/*`
- Simplifies Caddyfile configuration

**Future consideration**: If route proliferation occurs, consider API versioning (`/v1/ai/*`).

### 6. Loss of Separate Rate Limiting

**What was lost**: CrewAI had separate `LOCAL_QA_RATE_LIMIT_PER_HOUR` config.

**Why accepted**:
- Single `AI_RATE_LIMIT_PER_HOUR` is simpler to manage
- No operational need for differentiated limits without local Q&A

**Future consideration**: If different AI features need different limits, implement per-endpoint rate limiting in ADK.

## Code Debt to Address Later

| Item | Priority | Notes |
|------|----------|-------|
| Remove unused types (LocalAI*) from frontend | ✅ Done | Removed during implementation |
| Update API docs to reflect /adk/* only | Medium | External integrations may break |
| Remove LOCAL_QA references from K8s configmap comments | ✅ Done | Cleaned during implementation |
| Bare `except` in channels.py:143 | Low | Pre-existing lint issue, not from this change |

## Pre-existing Lint Issues (Not Addressed)

The following lint issues existed before this change and remain:

```
ai-service-adk/calendar_agent.py:253:9: F841 unused variable `session`
ai-service-adk/gmail_agent.py:12:20: F401 unused import `config.settings`
ai-service-adk/gmail_agent.py:165:9: F841 unused variable `session`
backend/src/api/endpoints/channels.py:143:9: E722 bare `except`
```

These are outside the scope of this change but should be addressed in a separate cleanup PR.

## Dependencies Removed

| Package | Size Impact | Notes |
|---------|-------------|-------|
| `crewai[tools]==0.203.2` | ~150MB | Large ML framework |
| `anthropic>=0.18.0` | ~10MB | Direct SDK (ADK uses LiteLLM instead) |
| vLLM container | ~2GB+ | External runtime dependency |

## Architecture Simplification

### Before
```
Frontend → Caddy → ai-service (CrewAI, port 8001)
                 → ai-service-adk (Google ADK, port 8004)
                 → backend
```

### After
```
Frontend → Caddy → ai-service-adk (Google ADK, port 8004)
                 → backend
```

**Benefits**:
- Reduced container count (1 fewer service)
- Simplified Caddyfile routing
- Lower memory footprint (~200MB less)
- Faster deployment times
- Single AI backend to monitor and maintain

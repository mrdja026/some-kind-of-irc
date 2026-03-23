## Context

The project currently runs two parallel AI inference services:
1. **ai-service (CrewAI)** - Port 8001, uses CrewAI framework with Anthropic SDK
2. **ai-service-adk (Google ADK)** - Port 8004, uses Google ADK with LiteLLM

Both services implement identical Gmail and Calendar agent functionality. The ADK service was introduced for A/B testing. Now that testing is complete, we consolidate to a single backend.

### Stakeholders
- Frontend team (API routing changes)
- DevOps (infrastructure simplification)
- Users (feature removal: Local Q&A, A/B toggle)

## Goals / Non-Goals

### Goals
- Remove ai-service (CrewAI) entirely
- Remove Local Q&A feature (`#qa-local` channel)
- Remove A/B testing toggle from frontend
- Consolidate all AI inference to ai-service-adk
- Reduce container footprint and operational complexity

### Non-Goals
- Migrating Local Q&A to ADK (explicitly rejected)
- Preserving A/B testing infrastructure for future use
- Changing ADK service implementation
- Modifying Gmail/Calendar agent prompts or behavior

## Decisions

### Decision 1: Use `/adk/*` prefix exclusively
**Choice**: Frontend will call `/adk/ai/*` endpoints (not `/ai/*`)

**Rationale**: 
- Cleaner separation - ADK service already handles `/adk/*` via Caddy
- No need to maintain backwards compatibility with `/ai/*`
- Simpler Caddyfile configuration

**Alternatives considered**:
- Route `/ai/*` to ADK (rejected: requires Caddyfile rewrite, confusing naming)
- Keep both routes (rejected: unnecessary complexity)

### Decision 2: Remove Local Q&A entirely (no migration)
**Choice**: Delete all Local Q&A functionality without migrating to ADK

**Rationale**:
- Low feature adoption
- vLLM infrastructure complexity (external dependency)
- CrewAI-specific implementation patterns don't translate to ADK
- Reduces scope of this change

**Alternatives considered**:
- Migrate to ADK with vLLM (rejected: complexity, low value)
- Migrate to ADK with LiteLLM local (rejected: scope creep)

### Decision 3: Remove A/B toggle entirely
**Choice**: Delete all A/B testing infrastructure (context, toggle, localStorage)

**Rationale**:
- Only one backend remains after change
- No plan to reintroduce A/B testing
- Cleaner user experience

**Alternatives considered**:
- Hide toggle, keep code (rejected: dead code, maintenance burden)

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Breaking frontend changes** | All AI API calls must update | Single deployment window; thorough testing |
| **Loss of Local Q&A** | Users lose art/photo assistant | Feature was experimental; low adoption |
| **Single point of failure** | One AI backend | ADK service already production-tested |
| **localStorage stale data** | Users may have old backend preference | Preference ignored; no functional impact |

## Migration Plan

### Phase 1: Frontend changes (atomic)
All frontend changes must deploy together:
- API routing to `/adk/*`
- Remove A/B toggle and context
- Remove Local Q&A component

### Phase 2: Backend changes
- Remove Local Q&A config from backend
- These can deploy independently

### Phase 3: Infrastructure changes
- Update docker-compose, Caddyfile, deploy-local.sh
- Delete ai-service directory
- Delete K8s manifest

### Rollback
If issues discovered:
1. Revert frontend to use `/ai/*` with ADK backend (Caddyfile has `/ai/*` → ADK)
2. Re-add ai-service container if needed (git restore)

## Open Questions

None - all decisions made during planning.

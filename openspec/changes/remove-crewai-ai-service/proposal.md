# Change: Remove CrewAI ai-service and Local Q&A Feature

## Why

The ai-service-adk (Google ADK) has achieved feature parity with ai-service (CrewAI) for Gmail and Calendar agent functionality. Maintaining two parallel AI inference services creates:

1. **Operational overhead**: Two services to monitor, deploy, and maintain
2. **Dependency complexity**: CrewAI has heavy dependencies (~200MB+ container overhead)
3. **A/B testing completed**: User preference data collected; ADK selected as production backend
4. **Local Q&A underutilized**: The vLLM-backed Local Q&A feature has low adoption and adds infrastructure complexity

This change consolidates AI inference to a single backend (ADK) and removes the experimental Local Q&A feature entirely.

## What Changes

### Removed Services
- **DELETE** `ai-service/` directory (entire CrewAI-based service)
- **DELETE** `k8s/manifests/ai-service.yaml` (K8s deployment)
- **BREAKING**: `/ai/*` routes previously served by ai-service now require `/adk/*` prefix

### Removed Features
- **DELETE** Local Q&A channel (`#qa-local`) and all related functionality
- **DELETE** A/B backend toggle in frontend header
- **DELETE** `AIBackendContext` and `AIBackendProvider` React context
- **DELETE** `LocalQAChannel` component

### Infrastructure Changes
- **MODIFY** `docker-compose.yml`: Remove ai-service, update dependencies
- **MODIFY** `Caddyfile`: Route `/ai/*` to ai-service-adk (with prefix strip), update healthz
- **MODIFY** `deploy-local.sh`: Remove ai-service build/health checks, remove LOCAL_QA env vars
- **MODIFY** `k8s/manifests/ingress.yaml`: Update routing to ai-service-adk

### Backend Changes
- **MODIFY** `backend/src/core/config.py`: Remove `FEATURE_LOCAL_QA`, `LOCAL_QA_CHANNEL_NAME`
- **MODIFY** `backend/src/main.py`: Remove local_qa_enabled channel creation
- **MODIFY** `backend/src/api/endpoints/channels.py`: Remove all `_local_qa_*` functions

### Frontend Changes
- **MODIFY** `frontend/src/api/index.ts`: Use `/adk/*` prefix only, remove Local Q&A functions
- **MODIFY** `frontend/src/routes/chat.tsx`: Remove `#qa-local` handling
- **MODIFY** `frontend/src/components/Header.tsx`: Remove AIBackendToggle
- **MODIFY** `frontend/src/components/AIChannel.tsx`: Remove backend selection logic
- **DELETE** `frontend/src/components/LocalQAChannel.tsx`
- **DELETE** `frontend/src/components/AIBackendToggle.tsx`
- **DELETE** `frontend/src/context/AIBackendContext.tsx`

## Impact

- **Affected specs**: `ai-channel` (remove Local Q&A, remove A/B testing)
- **Breaking changes**: 
  - Frontend must use `/adk/ai/*` instead of `/ai/*` for AI endpoints
  - `#qa-local` channel no longer exists
  - A/B backend preference in localStorage ignored
- **Dependencies removed**:
  - `crewai[tools]==0.203.2`
  - `anthropic>=0.18.0` (from ai-service; ADK uses LiteLLM)
- **Container reduction**: ~1 fewer container in deployment (~200MB+ saved)

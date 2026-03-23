## 1. Frontend: Remove A/B Testing and Local Q&A

- [x] 1.1 Delete `frontend/src/context/AIBackendContext.tsx`
- [x] 1.2 Delete `frontend/src/components/AIBackendToggle.tsx`
- [x] 1.3 Delete `frontend/src/components/LocalQAChannel.tsx`
- [x] 1.4 Update `frontend/src/routes/__root.tsx` - Remove AIBackendProvider
- [x] 1.5 Update `frontend/src/components/Header.tsx` - Remove AIBackendToggle
- [x] 1.6 Update `frontend/src/api/index.ts`:
  - Remove `AI_API_BASE_URL` constant
  - Remove `getStoredAIBackend()`, `getAIBaseUrl()`, `getAIEndpointPath()` functions
  - Update Gmail/Calendar functions to use `/adk/ai/*` directly via `ADK_API_BASE_URL`
  - Remove `getLocalAIStatus()`, `queryLocalAI()`, `queryLocalAIStream()` functions
  - Update `getAIStatus()`, `getAIHealth()` to use ADK endpoint
- [x] 1.7 Update `frontend/src/types/index.ts` - Remove LocalAI types (if present)
- [x] 1.8 Update `frontend/src/components/AIChannel.tsx` - Remove useAIBackend, use ADK directly
- [x] 1.9 Update `frontend/src/routes/chat.tsx` - Remove `#qa-local` handling
- [x] 1.10 Update `frontend/src/components/ChannelsSidebar.tsx` - Remove `#qa-local` special display

## 2. Backend: Remove Local Q&A Configuration

- [x] 2.1 Update `backend/src/core/config.py`:
  - Remove `FEATURE_LOCAL_QA` setting
  - Remove `LOCAL_QA_CHANNEL_NAME` setting
  - Remove `local_qa_enabled` property
- [x] 2.2 Update `backend/src/main.py` - Remove local_qa_enabled channel creation
- [x] 2.3 Update `backend/src/api/endpoints/channels.py`:
  - Remove `_local_qa_channel_name()` function
  - Remove `_user_has_local_qa_access()` function
  - Remove `_is_local_qa_channel()` function
  - Remove `_is_local_qa_channel_name()` function
  - Remove `_enforce_local_qa_access()` function
  - Remove all calls to these functions throughout the file

## 3. Infrastructure: Update Docker Compose

- [x] 3.1 Update `docker-compose.yml`:
  - Remove `ai-service` service definition (lines 86-114)
  - Update `frontend.depends_on` to remove `ai-service`
  - Update `caddy.depends_on` to remove `ai-service`
  - Remove `VITE_AI_API_URL` build args and environment variables

## 4. Infrastructure: Update Caddy

- [x] 4.1 Update `Caddyfile`:
  - Remove `@ai_stream` path matcher for `/ai/local/query/stream`
  - Remove `/ai/*` routing to ai-service
  - Update `@ai_health` to point to `ai-service-adk:8004`

## 5. Infrastructure: Update deploy-local.sh

- [x] 5.1 Update `deploy-local.sh`:
  - Remove `ai-service` from build list (line 173)
  - Remove `ai-service` from `up -d` command (line 209)
  - Remove ai-service health check wait loop (lines 216-223)
  - Remove `LOCAL_QA_*` environment variables (lines 130-142)
  - Update deploy summary to remove "AI Service (CrewAI)" line

## 6. Infrastructure: Update K8s Manifests

- [x] 6.1 Delete `k8s/manifests/ai-service.yaml`
- [x] 6.2 Update `k8s/manifests/ingress.yaml`:
  - Update `/healthz` route to `ai-service-adk:8004`
  - Remove `/ai` route (no longer needed)
- [x] 6.3 Update `k8s/manifests/configmap.yaml`:
  - Remove `FEATURE_LOCAL_QA` variable
  - Remove `LOCAL_QA_*` variables
  - Remove `CLAUDE_MODEL` (ADK uses ADK_MODEL instead)

## 7. Delete ai-service Directory

- [x] 7.1 Delete `ai-service/` directory (all files):
  - `main.py`
  - `config.py`
  - `auth.py`
  - `rate_limiter.py`
  - `ai_session_events.py`
  - `gmail_agent.py`
  - `calendar_agent.py`
  - `local_qa_orchestrator.py`
  - `Dockerfile`
  - `requirements.txt`
  - `__pycache__/`

## 8. Validation and Testing

- [x] 8.1 Run `pixi run python-lint` for static analysis
- [x] 8.2 Run `./deploy-local.sh --build` to verify deployment
- [ ] 8.3 Test Gmail flow works via `/adk/ai/gmail/*`
- [ ] 8.4 Test Calendar flow works via `/adk/ai/calendar/*`
- [x] 8.5 Verify `#qa-local` channel is no longer created
- [x] 8.6 Verify A/B toggle is removed from header
- [ ] 8.7 Document tradeoffs in tech_debt.md

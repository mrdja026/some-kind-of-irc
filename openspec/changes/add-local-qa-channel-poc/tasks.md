## 1. Spec + config
- [x] 1.1 Add local QA feature/config envs to backend and ai-service (`FEATURE_LOCAL_QA`, channel name, local vLLM URL/model)
- [x] 1.2 Reuse `AI_ALLOWLIST` for local QA access checks in ai-service

## 2. Backend restricted channel behavior
- [x] 2.1 Ensure `#qa-local` channel bootstrap when local QA feature is enabled
- [x] 2.2 Restrict `#qa-local` visibility in channel listing for unauthorized users
- [x] 2.3 Enforce admin-or-allowlist access for join/read/send/member endpoints on `#qa-local`

## 3. AI service local inference endpoints
- [x] 3.1 Add `GET /ai/local/status` with local vLLM availability check
- [x] 3.2 Add `POST /ai/local/query` non-streaming endpoint with CrewAI sequential process
- [x] 3.3 Implement hard prompt-domain rejection with HTTP 200 structured payload
- [x] 3.4 Implement deterministic fallback payload when local model is unavailable

## 4. Frontend reuse-first UX
- [x] 4.1 Add `/qa-local` command handling and channel navigation
- [x] 4.2 Hide `#qa-local` unless user is admin or in allowlist response context
- [x] 4.3 Add once-per-browser-session greeting trigger for `#qa-local` using session storage
- [x] 4.4 Keep greeting ephemeral in UI and do not persist it to backend messages

## 5. Local runtime cleanup
- [x] 5.1 Remove Streamlit dependency from `vllm_katanemo-Arch-Function-3B/requirements-app.txt`
- [x] 5.2 Remove Streamlit execution from `vllm_katanemo-Arch-Function-3B/run_local.sh`
- [x] 5.3 Remove Streamlit startup from `vllm_katanemo-Arch-Function-3B/Dockerfile`

## 6. Deploy + validation
- [x] 6.1 Update `deploy-local.sh` with local QA health checks
- [x] 6.2 Validate admin+allowlist access matrix for channel and `/ai/local/*`
- [x] 6.3 Validate non-streaming response flow, hard reject payload, and fallback payload

## 7. Technical debt tracking
- [x] 7.1 Record deferred backend-persisted targeted greeting (`target_user_id`) as post-POC technical debt

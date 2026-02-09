# Tasks: Integrate Anthropic SDK and Quiz Logic

- [ ] **Phase 1: Foundation**
    - [ ] 1.1 Add `anthropic` to `ai-service/requirements.txt`
    - [ ] 1.2 Update `ai-service/config.py` to include any new necessary settings (e.g., Search API key placeholder)
    - [ ] 1.3 Refactor `ai-service/orchestrator.py` to use `AsyncAnthropic` SDK instead of `httpx`

- [ ] **Phase 2: Quiz Logic & Tools**
    - [ ] 2.1 Implement `web_search` tool in `ai-service/tools/search.py` (or similar)
    - [ ] 2.2 Create `QuizAgent` class in `ai-service/orchestrator.py` or a new file
    - [ ] 2.3 Implement the 3-question + sub-questions logic in `QuizAgent`
    - [ ] 2.4 Update `AIQueryRequest` and `AIIntent` in `ai-service/main.py` to include `quiz`

- [ ] **Phase 3: Frontend Integration**
    - [ ] 3.1 Update `frontend/src/types/index.ts` to include `quiz` intent
    - [ ] 3.2 Update `frontend/src/components/AIChannel.tsx` to include the "Quiz" intent option and UI icons
    - [ ] 3.3 Ensure the frontend can handle multi-turn interactions for the quiz

- [ ] **Phase 4: Verification**
    - [ ] 4.1 Write unit tests for `QuizAgent`
    - [ ] 4.2 Perform end-to-end manual testing in the `#ai` channel

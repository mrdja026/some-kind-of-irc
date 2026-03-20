## 1. Gmail Agent Implementation

- [ ] 1.1 Create `ai-service-adk/gmail_agent.py` with `GmailAgentADK` class
- [ ] 1.2 Add MODEL_NAME constant: `claude-3-haiku-20240307`
- [ ] 1.3 Implement `_format_email_context()` helper (identical to CrewAI lines 71-85)
- [ ] 1.4 Implement `_email_selection_payload()` helper (identical to CrewAI lines 87-97)
- [ ] 1.5 Implement `_clean_and_parse_json()` helper (reuse pattern from calendar_agent.py)
- [ ] 1.6 Implement `_run_agent()` helper using ADK Runner pattern (similar to calendar_agent.py:215-277)
- [ ] 1.7 Implement `generate_followup_questions()` using ADK Agent
  - Prompt: identical to CrewAI lines 123-129
  - Role: "Gmail Follow-up Interviewer"
  - Goal: "Ask concise follow-up questions to refine Gmail summaries."
  - Backstory: "You are an expert inbox assistant who asks precise questions."
  - Fallback: identical to CrewAI lines 152-156
- [ ] 1.8 Implement `generate_summaries()` using two sequential ADK Agent runs
  - Action Agent: Role="Action Summary Analyst", Goal="Extract actionable items, deadlines, and required responses.", Backstory="You prioritize tasks and obligations in email."
  - Action Prompt: identical to CrewAI lines 196-201
  - Insight Agent: Role="Insight Summary Analyst", Goal="Summarize key updates, trends, and information.", Backstory="You extract meaningful insights from updates and newsletters."
  - Insight Prompt: identical to CrewAI lines 202-207
- [ ] 1.9 Implement `judge_and_rank()` using two sequential ADK Agent runs
  - Triage Agent: Role="Inbox Triage Specialist", Goal="Classify emails by relevance and urgency for the user.", Backstory="You quickly triage inboxes to highlight what matters."
  - Triage Prompt: identical to CrewAI lines 268-277
  - Judge Agent: Role="Gmail Summary Judge", Goal="Select the best summary and rank the most relevant emails.", Backstory="You combine summaries and classifications into a final report."
  - Judge Prompt: identical to CrewAI lines 285-294

## 2. FastAPI Endpoints

- [ ] 2.1 Add Pydantic models to `main.py`:
  - `GmailSummaryRequest` (emails, interest, answers)
  - `GmailQuestionsRequest` (emails, interest, previous_answers, question_count)
  - `GmailSummaryResponse` (final_summary, top_email_ids, reasoning)
  - `GmailQuestionsResponse` (questions)
- [ ] 2.2 Initialize `GmailAgentADK` instance in main.py
- [ ] 2.3 Add `/ai/gmail/questions` endpoint with rate limiting and auth
- [ ] 2.4 Add `/ai/gmail/summary` endpoint with rate limiting and auth

## 3. Frontend: Header Toggle Component

- [ ] 3.1 Create `AIBackendToggle` component for header
  - Display current selection: "CrewAI" or "Google ADK"
  - Toggle switch or dropdown to change selection
  - Visual indicator of active backend
- [ ] 3.2 Implement localStorage persistence
  - Key: `ai-backend-preference`
  - Values: `"crewai"` | `"googleAdk"`
- [ ] 3.3 Implement initial load behavior
  - Check localStorage for existing preference
  - If exists: use that backend silently
  - If not exists: show selection prompt/modal
- [ ] 3.4 Add toggle to application header (next to user menu or similar)
- [ ] 3.5 Create React context or state for backend preference
  - Export hook: `useAIBackend()` returning `{ backend, setBackend }`

## 4. Frontend: API Routing

- [ ] 4.1 Update `frontend/src/api.ts` to read backend preference
- [ ] 4.2 Route all AI requests based on preference:
  - `crewai` -> existing ai-service endpoints (port 8003)
  - `googleAdk` -> ai-service-adk endpoints (port 8004)
- [ ] 4.3 Update calendar API calls to use backend preference
- [ ] 4.4 Update Gmail API calls to use backend preference

## 5. Testing & Validation

- [ ] 5.1 Manual test: `generate_followup_questions()` returns array of 2 questions
- [ ] 5.2 Manual test: `generate_summaries()` returns summary_a and summary_b
- [ ] 5.3 Manual test: `judge_and_rank()` returns final_summary, top_email_ids, reasoning
- [ ] 5.4 Compare ADK Gmail responses with CrewAI responses for identical inputs
- [ ] 5.5 Verify rate limiting works for Gmail endpoints
- [ ] 5.6 Verify authentication (require_ai_access) works for Gmail endpoints
- [ ] 5.7 Verify fallback behavior matches CrewAI when LLM fails
- [ ] 5.8 Test header toggle persists selection to localStorage
- [ ] 5.9 Test page reload uses persisted preference without prompting
- [ ] 5.10 Test first-time user sees selection prompt
- [ ] 5.11 Test API routes correctly based on toggle selection

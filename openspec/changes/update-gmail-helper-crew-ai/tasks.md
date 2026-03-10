## 1. Gmail fetch filtering
- [x] 1.1 Update Gmail list query to filter `label:discovery` + unread.
- [x] 1.2 Handle empty result sets gracefully.

## 2. Gmail helper command behavior
- [x] 2.1 Trigger Gmail summary intent when `/gmail-helper` or `/gmail-agent` is issued.
- [x] 2.2 Ensure the Gmail flow uses `/auth/gmail/messages` to fetch emails.

## 3. CrewAI summarization pipeline
- [x] 3.1 Replace the Gmail agent with CrewAI agents (triage/action/insight/judge).
- [x] 3.2 Enforce strict JSON outputs for each CrewAI task.
- [x] 3.3 Use Anthropic Claude 3 Haiku for Gmail summarization agents.

## 4. Local deployment configuration
- [x] 4.1 Require `ANTHROPIC_API_KEY` in `deploy-local.sh` for Gmail summaries.
- [x] 4.2 Remove `AI_SERVICE_API_KEY` usage and document the required key in deployment output/logs.

## Notes
- Tech debt: UI/UX ambiguity about how to start the Gmail journey.

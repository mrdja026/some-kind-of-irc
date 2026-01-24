## 1. Implementation

- [x] 1.1 Remove Agent Framework dependency and use the OpenAI SDK via API key
- [x] 1.2 Keep specialist + judge orchestration using direct chat completions
- [x] 1.3 Update SQLite migration for `users.updated_at` to avoid non-constant defaults
- [x] 1.4 Verify backend startup and AI endpoint response
- [x] 1.5 Add AI/Chat mode toggle per channel and support `/ai` command
- [x] 1.6 Switch AI provider to Anthropic Claude and wire env config
- [x] 1.7 Add AI streaming endpoint and client streaming handler
- [x] 1.8 Reject AI requests that include media inputs
- [x] 1.9 Scale down to 2 AI agents (Finance & Learning) and remove Travel agent

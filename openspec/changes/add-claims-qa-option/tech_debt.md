# Trade-offs

## Random selection can repeat
Claims are selected randomly on each request with no session-level rotation, so users can see the same claim multiple times.

## Extra proxy hop
The backend retrieves claims through the media-storage proxy, which adds one network hop but keeps MinIO access centralized.

## Claim schema is not validated
Claim JSON is passed through as-is and rendered verbatim; malformed claim schemas will surface as display errors instead of being normalized.

## Multi-step judge increases cost and latency
Generating two candidate answers and a judge decision increases token usage and response time compared to a single-pass answer.

## Logging volume grows quickly
Emitting events for every step (truth-check, candidates, judge, follow-up) increases Redis stream volume and dataset size.

## Full JSON payload per turn
Sending the full claim JSON on every question simplifies statelessness but increases request payload size.

## Token costs are estimated
LLM token costs are estimated from prompt/response length rather than model-reported usage.

## ADK output_schema enforces structure but not semantics
The `output_schema` parameter passed to Google ADK `Agent()` guarantees the LLM response matches the Pydantic schema (field names, types), but it cannot enforce semantic correctness (e.g. `winner` being 1 or 2, not 99). Business-logic validation still happens in the calling code.

## Model upgraded from Haiku to Sonnet 4.5
Switching from `claude-3-haiku-20240307` to `claude-sonnet-4-5-20241022` enables native constrained decoding for structured outputs but increases per-token cost (~10x). This is acceptable for the low-volume claims review workflow.

## Legacy _clean_and_parse_json kept as fallback
The regex-based JSON parser is retained as a fallback in `_parse_structured()` for edge cases where ADK's structured output layer returns text that doesn't directly validate. This adds code surface but improves resilience during the transition.

## Gmail agent not yet migrated to output_schema
The Gmail agent still uses the legacy `_clean_and_parse_json()` parser. It was excluded from this change to limit scope; a follow-up migration is recommended.

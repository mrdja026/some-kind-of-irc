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

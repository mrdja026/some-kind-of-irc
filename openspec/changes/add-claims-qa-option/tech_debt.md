# Trade-offs

## Random selection can repeat
Claims are selected randomly on each request with no session-level rotation, so users can see the same claim multiple times.

## Extra proxy hop
The backend retrieves claims through the media-storage proxy, which adds one network hop but keeps MinIO access centralized.

## Claim schema is not validated
Claim JSON is passed through as-is and rendered verbatim; malformed claim schemas will surface as display errors instead of being normalized.

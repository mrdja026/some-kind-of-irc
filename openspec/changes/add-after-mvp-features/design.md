## Context
Post-MVP features add cross-cutting behavior (notifications, receipts, invites) that affect backend data modeling, WebSocket events, and UI state.

## Goals / Non-Goals
- Goals: Define consistent events and data for receipts, reactions, invites, and notifications.
- Non-Goals: Implementing vendor-specific push notification setup in this change.

## Decisions
- Decision: Persist receipts and reactions server-side and broadcast over WebSocket.
- Decision: Use a unified notification preferences model (mute channel, disable DM, disable mentions).
- Decision: Channel-wide mentions are explicit (for example @here/@channel) and respect mute settings.

## Risks / Trade-offs
- Push notifications add external dependencies and should be feature-flagged.
- Receipts can create higher event volume; batching may be required.

## Migration Plan
- Add new tables/columns behind feature flags.
- Roll out UI updates after backend events are stable.

## Open Questions
- Which push provider is preferred (FCM/APNS only, or a multi-platform service)?
- What is the minimum receipt granularity (per message or per channel)?

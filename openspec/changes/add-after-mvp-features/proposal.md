# Change: After MVP Features

## Why

Define the post-MVP feature set for a modern IRC-style chat app so we can plan sequencing and avoid scope creep while keeping the MVP stable.

## What Changes

- Add message delivery and read receipts
- Add unread and mention counts
- Add emoji reactions on messages
- Add channel-wide mentions (for example @here and @channel)
- Add private channel invite flow
- Add push notifications and notification preferences

## Impact

- Affected specs: message-receipts, unread-counts, reactions, channel-mentions, channel-invites, notifications
- Affected code:
  - Backend: message/event models, WebSocket events, notification dispatch, preferences endpoints
  - Frontend: message UI (receipts/reactions), channel list badges, mention handling, invite UI

# Change: Add Channel Member Mentions with Autocomplete

## Why

Users need a way to mention other users in channels when typing messages. When a user types "@" in a channel, they should see an autocomplete dropdown listing all members in that channel, searchable by id, username, or display name. This improves communication and makes it easier to direct messages to specific users.

## What Changes

- Add backend endpoint `GET /channels/{channel_id}/members` with optional search filtering
- Implement React Query hook for fetching channel members
- Create mention autocomplete component with dropdown and keyboard navigation
- Integrate autocomplete into chat message input
- Update WebSocket handler to invalidate member queries on join/leave events
- Members sorted by display_name ascending (nulls last), then by username

## Impact

- Affected specs: channel-mentions (new capability)
- Affected code:
  - Backend: `backend/src/api/endpoints/channels.py` - new endpoint
  - Frontend: `frontend/src/api/index.ts` - new API function
  - Frontend: `frontend/src/hooks/useChannelMembers.ts` - new hook
  - Frontend: `frontend/src/components/MentionAutocomplete.tsx` - new component
  - Frontend: `frontend/src/routes/chat.tsx` - integration
  - Frontend: `frontend/src/hooks/useChatSocket.ts` - WebSocket invalidation

## Status

**Note: This feature has been implemented but is not yet tested.**

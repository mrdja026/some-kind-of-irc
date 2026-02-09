## 1. Backend
- [ ] 1.1 Add message receipt tracking (delivered/read) in persistence
- [ ] 1.2 Emit receipt updates over WebSocket
- [ ] 1.3 Add reactions storage and API (add/remove)
- [ ] 1.4 Add unread and mention counters per channel
- [ ] 1.5 Add invite endpoints for private channels (create, accept, decline)
- [ ] 1.6 Add notification preferences endpoints (mute channel, disable DM)
- [ ] 1.7 Add push notification dispatch for DM/mention events

## 2. Frontend
- [ ] 2.1 Render delivery/read receipts in message UI
- [ ] 2.2 Render emoji reactions with add/remove interactions
- [ ] 2.3 Show unread and mention badges in sidebar
- [ ] 2.4 Implement channel-wide mentions in composer (for example @here/@channel)
- [ ] 2.5 Add invite UI and accept/decline flow
- [ ] 2.6 Add notification preferences UI

## 3. Realtime
- [ ] 3.1 Add WebSocket events for receipts, reactions, and invites
- [ ] 3.2 Ensure unread/mention counts update on relevant events

## 4. Testing
- [ ] 4.1 Backend tests for receipts, reactions, invites, and preferences
- [ ] 4.2 Frontend integration tests for badges and reactions
- [ ] 4.3 End-to-end tests for mention notifications and invite flow

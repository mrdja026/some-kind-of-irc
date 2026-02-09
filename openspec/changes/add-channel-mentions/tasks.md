## 1. Backend Implementation
- [x] 1.1 Create GET /channels/{channel_id}/members endpoint with search filtering
- [x] 1.2 Implement sorting by display_name ascending (nulls last), then username
- [x] 1.3 Add membership verification (403 if user not in channel)

## 2. Frontend API
- [x] 2.1 Add getChannelMembers function to frontend API

## 3. React Query Hook
- [x] 3.1 Create useChannelMembers hook with proper query key structure
- [x] 3.2 Ensure automatic refetching on channel/search changes

## 4. Autocomplete Component
- [x] 4.1 Build MentionAutocomplete component with "@" detection
- [x] 4.2 Implement dropdown with filtered/sorted member list
- [x] 4.3 Add keyboard navigation (Arrow Up/Down, Enter, Tab, Escape)
- [x] 4.4 Add mouse click selection
- [x] 4.5 Insert selected user's display_name (or username) into input
- [x] 4.6 Reset state when channel changes

## 5. Integration
- [x] 5.1 Integrate MentionAutocomplete into chat.tsx message input
- [x] 5.2 Add input ref for cursor position tracking
- [x] 5.3 Wrap input in relative container for dropdown positioning

## 6. WebSocket Updates
- [x] 6.1 Update useChatSocket to invalidate channel members on join/leave events

## 7. Testing
- [ ] 7.1 Test with channels that have many members
- [ ] 7.2 Test with users who have no display_name
- [ ] 7.3 Test rapid channel switching
- [ ] 7.4 Test search functionality with various queries
- [ ] 7.5 Test keyboard navigation
- [ ] 7.6 Test WebSocket join/leave events updating the list
- [ ] 7.7 Test edge cases (user not in channel, multiple "@" in message, etc.)

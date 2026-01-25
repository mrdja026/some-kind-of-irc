import { useState, useEffect, useRef, useMemo } from 'react';
import { useChannelMembers } from '../hooks/useChannelMembers';
import type { User } from '../types';

interface MentionAutocompleteProps {
  channelId: number | null;
  inputValue: string;
  onInputChange: (value: string) => void;
  inputRef: React.RefObject<HTMLInputElement>;
}

export function MentionAutocomplete({
  channelId,
  inputValue,
  onInputChange,
  inputRef,
}: MentionAutocompleteProps) {
  const [mentionStartIndex, setMentionStartIndex] = useState<number | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Extract search query from input after "@"
  const searchQuery = useMemo(() => {
    if (mentionStartIndex === null) return undefined;
    const textAfterAt = inputValue.slice(mentionStartIndex + 1);
    const spaceIndex = textAfterAt.indexOf(' ');
    if (spaceIndex === -1) {
      return textAfterAt;
    }
    return textAfterAt.slice(0, spaceIndex);
  }, [inputValue, mentionStartIndex]);

  // Fetch channel members with search query
  const { data: members = [], isLoading } = useChannelMembers(
    channelId,
    searchQuery,
  );

  // Filter and sort members (backend already sorts, but we do client-side filtering for exact matches)
  const filteredMembers = useMemo(() => {
    if (!searchQuery) return members;
    const queryLower = searchQuery.toLowerCase();
    return members.filter((member) => {
      const idMatch = member.id.toString() === searchQuery;
      const usernameMatch = member.username.toLowerCase().includes(queryLower);
      const displayNameMatch = member.display_name?.toLowerCase().includes(queryLower);
      return idMatch || usernameMatch || displayNameMatch;
    });
  }, [members, searchQuery]);

  // Reset mention state when channel changes
  useEffect(() => {
    setMentionStartIndex(null);
    setSelectedIndex(0);
  }, [channelId]);

  // Detect "@" character in input
  useEffect(() => {
    if (!inputRef.current) return;

    const cursorPosition = inputRef.current.selectionStart || 0;
    const textBeforeCursor = inputValue.slice(0, cursorPosition);
    
    // Find the last "@" before cursor
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');
    
    if (lastAtIndex !== -1) {
      // Check if there's a space after the "@" (meaning mention is complete)
      const textAfterAt = textBeforeCursor.slice(lastAtIndex + 1);
      const hasSpaceAfter = textAfterAt.includes(' ');
      
      if (!hasSpaceAfter && channelId !== null) {
        setMentionStartIndex(lastAtIndex);
        setSelectedIndex(0);
      } else {
        setMentionStartIndex(null);
      }
    } else {
      setMentionStartIndex(null);
    }
  }, [inputValue, channelId, inputRef]);

  // Reset selected index when filtered members change
  useEffect(() => {
    setSelectedIndex(0);
  }, [filteredMembers.length]);

  // Handle keyboard navigation
  useEffect(() => {
    if (mentionStartIndex === null || filteredMembers.length === 0) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (mentionStartIndex === null) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex((prev) => (prev + 1) % filteredMembers.length);
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex((prev) => (prev - 1 + filteredMembers.length) % filteredMembers.length);
          break;
        case 'Enter':
        case 'Tab':
          e.preventDefault();
          if (filteredMembers[selectedIndex]) {
            selectMember(filteredMembers[selectedIndex]);
          }
          break;
        case 'Escape':
          e.preventDefault();
          setMentionStartIndex(null);
          break;
      }
    };

    const input = inputRef.current;
    if (input) {
      input.addEventListener('keydown', handleKeyDown);
      return () => input.removeEventListener('keydown', handleKeyDown);
    }
  }, [mentionStartIndex, filteredMembers, selectedIndex, inputRef]);

  // Select a member and insert into input
  const selectMember = (member: User) => {
    if (mentionStartIndex === null || !inputRef.current) return;

    const displayName = member.display_name || member.username;
    const textBefore = inputValue.slice(0, mentionStartIndex);
    const textAfter = inputValue.slice(inputRef.current.selectionStart || inputValue.length);
    
    // Insert "@displayName " (with space after)
    const newValue = `${textBefore}@${displayName} ${textAfter}`;
    onInputChange(newValue);
    setMentionStartIndex(null);

    // Focus input and set cursor position after the inserted mention
    setTimeout(() => {
      if (inputRef.current) {
        const newCursorPos = textBefore.length + displayName.length + 2; // +2 for "@" and " "
        inputRef.current.focus();
        inputRef.current.setSelectionRange(newCursorPos, newCursorPos);
      }
    }, 0);
  };

  // Show dropdown if we have a mention start and members
  const showDropdown = mentionStartIndex !== null && channelId !== null;

  if (!showDropdown) return null;

  return (
    <div
      ref={dropdownRef}
      className="absolute bottom-full left-0 mb-1 w-full max-h-64 overflow-y-auto bg-chat-shell border border-chat-divider rounded-lg shadow-lg z-50"
    >
      {isLoading ? (
        <div className="p-3 text-sm chat-meta">Loading members...</div>
      ) : filteredMembers.length === 0 ? (
        <div className="p-3 text-sm chat-meta">No members found</div>
      ) : (
        <div className="py-1">
          {filteredMembers.map((member, index) => {
            const displayName = member.display_name || member.username;
            const isSelected = index === selectedIndex;
            
            return (
              <div
                key={member.id}
                onClick={() => selectMember(member)}
                className={`px-3 py-2 cursor-pointer transition-colors ${
                  isSelected
                    ? 'bg-chat-channel-item--active'
                    : 'hover:bg-chat-channel-item'
                }`}
                onMouseEnter={() => setSelectedIndex(index)}
              >
                <div className="flex items-center gap-2">
                  {member.profile_picture_url ? (
                    <img
                      src={member.profile_picture_url}
                      alt={displayName}
                      className="w-6 h-6 rounded-full object-cover"
                    />
                  ) : (
                    <div className="w-6 h-6 rounded-full flex items-center justify-center chat-avatar">
                      <span className="text-xs font-semibold">
                        {displayName[0].toUpperCase()}
                      </span>
                    </div>
                  )}
                  <div className="flex-1">
                    <div className="text-sm font-semibold">{displayName}</div>
                    {member.display_name && (
                      <div className="text-xs chat-meta">{member.username}</div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

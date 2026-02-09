import { useQuery } from '@tanstack/react-query';
import { getChannelMembers } from '../api';
import type { User } from '../types';

/**
 * Hook to fetch channel members with optional search filtering.
 * Automatically refetches when channelId or search changes.
 * 
 * @param channelId - The ID of the channel, or null to disable the query
 * @param search - Optional search query to filter members by id, username, or display_name
 * @returns Query result with data, isLoading, and error
 */
export function useChannelMembers(
  channelId: number | null,
  search?: string,
) {
  return useQuery<User[]>({
    queryKey: ['channelMembers', channelId, search],
    queryFn: () => {
      if (!channelId) {
        throw new Error('Channel ID is required');
      }
      return getChannelMembers(channelId, search);
    },
    enabled: channelId !== null,
    staleTime: 30000, // Consider data stale after 30 seconds
  });
}

import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useQuery } from '@tanstack/react-query';
import { getCurrentUser } from '../api';
import type { User } from '../types';

/**
 * Hook that watches for changes in user profile (specifically updated_at)
 * and invalidates relevant queries when the profile is updated.
 * 
 * This ensures that profile picture changes are reflected across the app
 * without requiring manual cache invalidation.
 */
export function useUserProfileInvalidation() {
  const queryClient = useQueryClient();
  const lastUpdatedAtRef = useRef<string | null>(null);

  // Poll current user to detect changes
  const { data: currentUser } = useQuery<User>({
    queryKey: ['currentUser'],
    queryFn: getCurrentUser,
    refetchInterval: 2000, // Check every 2 seconds
    staleTime: 1000, // Consider stale after 1 second
  });

  useEffect(() => {
    if (!currentUser?.updated_at) {
      return;
    }

    // If updated_at has changed, invalidate user-related queries //TODO if this is necesery? 
    if (lastUpdatedAtRef.current !== null && lastUpdatedAtRef.current !== currentUser.updated_at) {
      // Invalidate current user query
      queryClient.invalidateQueries({ queryKey: ['currentUser'] });
      
      // Invalidate all user queries (for user lookups by ID)
      queryClient.invalidateQueries({ queryKey: ['user'] });
      
      // Invalidate channels query (user info might be displayed there)
      queryClient.invalidateQueries({ queryKey: ['channels'] });
      
      // Invalidate direct messages query
      queryClient.invalidateQueries({ queryKey: ['directMessages'] });
      
      // Invalidate messages queries (user avatars in messages)
      queryClient.invalidateQueries({ queryKey: ['messages'] });
    }

    // Update the ref with the current updated_at
    lastUpdatedAtRef.current = currentUser.updated_at;
  }, [currentUser?.updated_at, queryClient]);
}

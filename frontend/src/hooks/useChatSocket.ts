import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { Message, WebSocketMessage } from '../types';

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8002';

export const useChatSocket = (clientId: number, token: string, onTyping?: (channelId: number, userId: number) => void) => {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const queryClientRef = useRef(queryClient);
  const onTypingRef = useRef<typeof onTyping>(onTyping);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    queryClientRef.current = queryClient;
    onTypingRef.current = onTyping;
  }, [onTyping, queryClient]);

  useEffect(() => {
    if (!clientId) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setIsConnected(false);
      return;
    }

    const socket = new WebSocket(`${WS_BASE_URL}/ws/${clientId}`);
    wsRef.current = socket;

    socket.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    };

    socket.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
    };

    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    socket.onmessage = (event) => {
      try {
        const data: WebSocketMessage = JSON.parse(event.data);
        handleWebSocketMessage(data);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    const handleWebSocketMessage = (message: WebSocketMessage) => {
      switch (message.type) {
        case 'message':
          if (message.channel_id) {
            // Update TanStack Query cache for messages
            queryClientRef.current.setQueryData(
              ['messages', message.channel_id],
              (oldData: Message[] = []) => {
                if (message.id && oldData.some((item) => item.id === message.id)) {
                  return oldData;
                }
                return [...oldData, message];
              }
            );
          }
          break;
        case 'join':
        case 'leave':
          if (message.channel_id) {
            // Invalidate channel data to update user list
            queryClientRef.current.invalidateQueries({ queryKey: ['channels'] });
            // Invalidate channel members to update mention autocomplete
            queryClientRef.current.invalidateQueries({ queryKey: ['channelMembers', message.channel_id] });
          }
          break;
        case 'typing':
          // Handle typing indicator
          if (
            onTypingRef.current &&
            message.channel_id !== undefined &&
            message.user_id !== undefined &&
            message.user_id !== clientId
          ) {
            onTypingRef.current(message.channel_id, message.user_id);
          }
          break;
        default:
          console.warn('Unknown message type:', message.type);
      }
    };

    return () => {
      socket.close();
    };
  }, [clientId]);

  const sendMessage = (message: WebSocketMessage) => {
    if (wsRef.current && isConnected) {
      wsRef.current.send(JSON.stringify(message));
    }
  };

  const sendTyping = (channelId: number) => {
    sendMessage({
      type: 'typing',
      channel_id: channelId,
      user_id: clientId,
    });
  };

  return {
    isConnected,
    sendMessage,
    sendTyping,
  };
};

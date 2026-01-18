import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { WebSocketMessage } from '../types';

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

export const useChatSocket = (clientId: number, token: string, onTyping?: (channelId: number, userId: number) => void) => {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
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
            queryClient.setQueryData(
              ['messages', message.channel_id],
              (oldData: any[] = []) => [...oldData, message]
            );
          }
          break;
        case 'join':
        case 'leave':
          if (message.channel_id) {
            // Invalidate channel data to update user list
            queryClient.invalidateQueries({ queryKey: ['channels'] });
          }
          break;
        case 'typing':
          // Handle typing indicator
          if (onTyping && message.channel_id !== undefined && message.user_id !== undefined && message.user_id !== clientId) {
            onTyping(message.channel_id, message.user_id);
          }
          break;
        default:
          console.warn('Unknown message type:', message.type);
      }
    };

    return () => {
      socket.close();
    };
  }, [clientId, queryClient, onTyping]);

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

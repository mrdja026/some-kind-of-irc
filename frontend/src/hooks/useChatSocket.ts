import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { Message, WebSocketMessage, GameAction, GameStateUpdate } from '../types';

const WS_BASE_URL =
  typeof window === 'undefined'
    ? import.meta.env.VITE_WS_URL || 'ws://backend:8002'
    : import.meta.env.VITE_PUBLIC_WS_URL ||
      (() => {
        const isSecure = window.location.protocol === 'https:'
        const proto = isSecure ? 'wss:' : 'ws:'
        const host = window.location.host
        const origin = `${proto}//${host}`
        const explicit = import.meta.env.VITE_PUBLIC_WS_URL?.trim()
        if (explicit) {
          if (explicit.includes('localhost') && window.location.hostname !== 'localhost') {
            return origin
          }
          return explicit
        }
        return origin
      })();

export const useChatSocket = (clientId: number, token: string, onTyping?: (channelId: number, userId: number) => void) => {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const queryClientRef = useRef(queryClient);
  const onTypingRef = useRef<typeof onTyping>(onTyping);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<number | null>(null);

  useEffect(() => {
    queryClientRef.current = queryClient;
    onTypingRef.current = onTyping;
  }, [onTyping, queryClient]);

  useEffect(() => {
    if (!clientId) {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setIsConnected(false);
      return;
    }
    let isCancelled = false;

    const logWsInfo = (event: string, payload: Record<string, unknown>) => {
      if (!import.meta.env.DEV) {
        return;
      }
      console.info(`[WebSocket] ${event}`, payload);
    };

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const scheduleReconnect = (wsUrl: string) => {
      if (isCancelled) {
        return;
      }

      clearReconnectTimer();
      const attempt = reconnectAttemptRef.current;
      const delay = Math.min(2000, 500 * Math.pow(2, attempt));
      reconnectAttemptRef.current = Math.min(attempt + 1, 5);
      logWsInfo('reconnect-scheduled', { clientId, wsUrl, delay, attempt });

      reconnectTimerRef.current = window.setTimeout(() => {
        if (isCancelled) {
          return;
        }
        connect();
      }, delay);
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
        case 'game_action':
        case 'game_state_update':
          // Handle game-related WebSocket messages
          // Invalidate game state queries to trigger refetch
          {
            const gameMessage = message as unknown as (GameAction | GameStateUpdate);
            if (gameMessage.channel_id) {
              // Invalidate channel game states to get latest positions
              queryClientRef.current.invalidateQueries({
                queryKey: ['channelGameStates', gameMessage.channel_id]
              });
              // Also invalidate personal game state
              queryClientRef.current.invalidateQueries({
                queryKey: ['myGameState']
              });
            }
          }
          break;
        default:
          console.warn('Unknown message type:', message.type);
      }
    };

    const connect = () => {
      if (isCancelled) {
        return;
      }

      const wsUrl = `${WS_BASE_URL}/ws/${clientId}`;
      const socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        reconnectAttemptRef.current = 0;
        logWsInfo('connected', { clientId, wsUrl });
        setIsConnected(true);
      };

      socket.onclose = (event) => {
        logWsInfo('disconnected', {
          clientId,
          wsUrl,
          code: event.code,
          reason: event.reason || 'no-reason',
          wasClean: event.wasClean,
        });
        wsRef.current = null;
        setIsConnected(false);
        scheduleReconnect(wsUrl);
      };

      socket.onerror = () => {
        logWsInfo('error', { clientId, wsUrl });
      };

      socket.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          handleWebSocketMessage(data);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
    };

    reconnectAttemptRef.current = 0;
    clearReconnectTimer();
    connect();

    return () => {
      isCancelled = true;
      clearReconnectTimer();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
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

import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { Message, WebSocketMessage } from '../types';

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

export const useChatSocket = (
  clientId: number,
  onTyping?: (channelId: number, userId: number) => void,
) => {
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
            queryClientRef.current.setQueryData(
              ['messages', message.channel_id],
              (oldData: Array<Message> = []) => {
                if (message.id && oldData.some((item) => item.id === message.id)) {
                  return oldData;
                }
                return [...oldData, message];
              },
            );
          }
          break;
        case 'join':
        case 'leave':
          if (message.channel_id) {
            queryClientRef.current.invalidateQueries({ queryKey: ['channels'] });
            queryClientRef.current.invalidateQueries({
              queryKey: ['channelMembers', message.channel_id],
            });
          }
          break;
        case 'typing':
          if (
            onTypingRef.current &&
            message.channel_id !== undefined &&
            message.user_id !== undefined &&
            message.user_id !== clientId
          ) {
            onTypingRef.current(message.channel_id, message.user_id);
          }
          break;
        case 'error':
          break;
        default:
          console.warn('Unknown message type:', message.type);
      }
    };

    const connect = () => {
      if (isCancelled) {
        return;
      }

      if (wsRef.current) {
        const state = wsRef.current.readyState;
        if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) {
          return;
        }
      }

      const wsUrl = `${WS_BASE_URL}/ws/${clientId}`;
      const socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        if (wsRef.current !== socket) {
          return;
        }
        reconnectAttemptRef.current = 0;
        logWsInfo('connected', { clientId, wsUrl });
        setIsConnected(true);
      };

      socket.onclose = (event) => {
        if (wsRef.current !== socket) {
          return;
        }
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
        if (wsRef.current !== socket) {
          return;
        }
        logWsInfo('error', { clientId, wsUrl });
      };

      socket.onmessage = (event) => {
        if (wsRef.current !== socket) {
          return;
        }
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

    const ensureConnected = () => {
      if (isCancelled || !clientId) {
        return;
      }

      if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
        connect();
      }
    };

    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        ensureConnected();
      }
    };

    window.addEventListener('focus', ensureConnected);
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      isCancelled = true;
      window.removeEventListener('focus', ensureConnected);
      document.removeEventListener('visibilitychange', handleVisibility);
      clearReconnectTimer();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [clientId]);

  const sendMessage = (message: unknown) => {
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

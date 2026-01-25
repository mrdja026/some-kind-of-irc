import type {
  User,
  Channel,
  Message,
  AuthResponse,
  AIIntent,
  AIQueryResponse,
  AIStatus,
  AIStreamEvent,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002';

// Auth APIs
export const login = async (username: string, password: string): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    credentials: 'include',
    body: new URLSearchParams({
      username,
      password,
    }),
  });
  if (!response.ok) {
    throw new Error('Login failed');
  }
};

export const register = async (username: string, password: string): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    throw new Error('Registration failed');
  }
};

export const getCurrentUser = async (): Promise<User> => {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Failed to get current user');
  }
  return response.json();
};

export const getUserById = async (userId: number): Promise<User> => {
  const response = await fetch(`${API_BASE_URL}/auth/users/${userId}`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Failed to get user');
  }
  return response.json();
};

// Channel APIs
export const getChannels = async (): Promise<Channel[]> => {
  const response = await fetch(`${API_BASE_URL}/channels`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Failed to get channels');
  }
  return response.json();
};

export const getDirectMessages = async (): Promise<Channel[]> => {
  const response = await fetch(`${API_BASE_URL}/channels/dms`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Failed to get direct messages');
  }
  return response.json();
};

export const createDirectMessageChannel = async (userId: number): Promise<Channel> => {
  const response = await fetch(`${API_BASE_URL}/channels/dm/${userId}`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Failed to create direct message channel');
  }
  return response.json();
};

export const createChannel = async (name: string, type: 'public' | 'private' = 'public'): Promise<Channel> => {
  const response = await fetch(`${API_BASE_URL}/channels`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ name, type }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create channel' }));
    throw new Error(error.detail || 'Failed to create channel');
  }
  return response.json();
};

export const joinChannel = async (channelId: number): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/channels/${channelId}/join`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Failed to join channel');
  }
};

export const searchChannels = async (name: string): Promise<Channel[]> => {
  const response = await fetch(`${API_BASE_URL}/channels/search?name=${encodeURIComponent(name)}`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Failed to search channels');
  }
  return response.json();
};

export const leaveChannel = async (channelId: number): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/channels/${channelId}/leave`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Failed to leave channel');
  }
};

// Message APIs
export const getMessages = async (channelId: number): Promise<Message[]> => {
  const response = await fetch(`${API_BASE_URL}/channels/${channelId}/messages`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Failed to get messages');
  }
  return response.json();
};

export const sendMessage = async (
  channelId: number,
  content: string,
  imageUrl?: string | null,
): Promise<Message> => {
  const response = await fetch(`${API_BASE_URL}/channels/${channelId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ content, image_url: imageUrl ?? null }),
  });
  if (!response.ok) {
    throw new Error('Failed to send message');
  }
  return response.json();
};

export const uploadImage = async (file: File): Promise<{ url: string }> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/media/upload`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  });

  if (!response.ok) {
    throw new Error('Failed to upload image');
  }

  const data = await response.json();
  return { url: data.url };
};

// User profile APIs
export const updateUserProfile = async (
  displayName?: string,
  profilePictureUrl?: string | null,
): Promise<User> => {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({
      ...(displayName !== undefined && { display_name: displayName }),
      ...(profilePictureUrl !== undefined && { profile_picture_url: profilePictureUrl }),
    }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update profile' }));
    throw new Error(error.detail || 'Failed to update profile');
  }
  return response.json();
};

export const searchUsers = async (username: string): Promise<User[]> => {
  const response = await fetch(
    `${API_BASE_URL}/auth/users/search?username=${encodeURIComponent(username)}`,
    {
      credentials: 'include',
    },
  );
  if (!response.ok) {
    throw new Error('Failed to search users');
  }
  return response.json();
};

// Channel member APIs
export const getChannelMembers = async (
  channelId: number,
  search?: string,
): Promise<User[]> => {
  const url = new URL(`${API_BASE_URL}/channels/${channelId}/members`);
  if (search) {
    url.searchParams.set('search', search);
  }
  const response = await fetch(url.toString(), {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to get channel members' }));
    throw new Error(error.detail || 'Failed to get channel members');
  }
  return response.json();
};

export const addUserToChannel = async (
  channelId: number,
  username: string,
): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/channels/${channelId}/members`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ username }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to add user to channel' }));
    throw new Error(error.detail || 'Failed to add user to channel');
  }
};

// AI Agent APIs
export const queryAI = async (intent: AIIntent, query: string): Promise<AIQueryResponse> => {
  const response = await fetch(`${API_BASE_URL}/ai/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ intent, query }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'AI query failed' }));
    throw new Error(error.detail || 'AI query failed');
  }
  return response.json();
};

export const queryAIStream = async (
  intent: AIIntent,
  query: string,
  handlers: {
    onEvent?: (event: AIStreamEvent) => void;
    onError?: (message: string) => void;
    signal?: AbortSignal;
  } = {},
): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/ai/query/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ intent, query }),
    signal: handlers.signal,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'AI stream failed' }));
    throw new Error(error.detail || 'AI stream failed');
  }

  if (!response.body) {
    throw new Error('Streaming not supported by the browser');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const emit = (event: AIStreamEvent) => {
    handlers.onEvent?.(event);
    if (event.type === 'error') {
      handlers.onError?.(event.message);
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex = buffer.indexOf('\n\n');
    while (separatorIndex !== -1) {
      const chunk = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      const lines = chunk.split(/\r?\n/);
      for (const line of lines) {
        if (!line.startsWith('data:')) continue;
        const payload = line.slice(5).trim();
        if (!payload) continue;
        try {
          const event = JSON.parse(payload) as AIStreamEvent;
          emit(event);
        } catch {
          // Ignore malformed chunks
        }
      }
      separatorIndex = buffer.indexOf('\n\n');
    }
  }
};

export const getAIStatus = async (): Promise<AIStatus> => {
  const response = await fetch(`${API_BASE_URL}/ai/status`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Failed to get AI status');
  }
  return response.json();
};

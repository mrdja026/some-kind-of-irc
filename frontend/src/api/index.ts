import type { User, Channel, Message, AuthResponse } from '../types';

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
    throw new Error('Failed to create channel');
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

  return response.json();
};

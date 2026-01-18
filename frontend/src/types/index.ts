export type User = {
  id: number;
  username: string;
  status: 'online' | 'idle' | 'offline';
};

export type Channel = {
  id: number;
  name: string;
  type: 'public' | 'private';
};

export type Message = {
  id: number;
  content: string;
  sender_id: number;
  channel_id: number;
  timestamp: string;
};

export type Membership = {
  user_id: number;
  channel_id: number;
  joined_at: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
};

export type WebSocketMessage = {
  type: 'message' | 'join' | 'leave' | 'typing';
  id?: number;
  content?: string;
  sender_id?: number;
  channel_id?: number;
  timestamp?: string;
  user_id?: number;
  username?: string;
  channel_name?: string;
};

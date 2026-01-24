export type User = {
  id: number;
  username: string;
  display_name?: string | null;
  status: 'online' | 'idle' | 'offline';
  profile_picture_url?: string | null;
  updated_at?: string | null;
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
  client_temp_id?: number;
  image_url?: string | null;
  username?: string;
  display_name?: string | null;
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
  image_url?: string | null;
  sender_id?: number;
  channel_id?: number;
  timestamp?: string;
  user_id?: number;
  username?: string;
  display_name?: string | null;
  channel_name?: string;
};

// AI Agent types
export type AIIntent = 'afford' | 'learn';

export type AIQueryRequest = {
  intent: AIIntent;
  query: string;
};

export type AIQueryResponse = {
  intent: string;
  query: string;
  response: string;
  agent: string;
  disclaimer: string;
};

export type AIStreamEvent =
  | {
      type: 'meta';
      intent: string;
      query: string;
      agent: string;
      disclaimer: string;
    }
  | {
      type: 'delta';
      text: string;
    }
  | {
      type: 'done';
    }
  | {
      type: 'error';
      message: string;
    };

export type AIStatus = {
  available: boolean;
  remaining_requests: number;
  max_requests_per_hour: number;
};

import type {
  User,
  Channel,
  Message,
  AIStatus,
  CalendarEventPayload,
  InferenceLogEvent,
  ClaimResponse,
  ClaimFilesResponse,
  ClaimQaHistoryEntry,
  ClaimQaResponse,
  ClaimToolCall,
  AISSEEvent,
  AISSEDoneEvent,
} from '../types';

export const API_BASE_URL =
  typeof window === 'undefined'
    ? import.meta.env.VITE_API_URL || 'http://backend:8002'
    : (() => {
        const origin = window.location.origin;
        const isLocalHost =
          window.location.hostname === 'localhost' ||
          window.location.hostname === '127.0.0.1';
        const normalizeLocalApiUrl = (value: string): string => {
          if (!isLocalHost) {
            return value;
          }
          if (
            value.includes(':8002') ||
            value.includes(':8001') ||
            value.includes(':8004') ||
            value.includes(':4269')
          ) {
            return 'http://localhost:8080';
          }
          return value;
        };
        const explicit = import.meta.env.VITE_PUBLIC_API_URL?.trim();
        if (explicit) {
          if ((explicit.includes('localhost') || explicit.includes('127.0.0.1')) && !isLocalHost) {
            return origin;
          }
          return normalizeLocalApiUrl(explicit);
        }
        if (isLocalHost) {
          return 'http://localhost:8080';
        }
        return origin;
      })();

// ---------------------------------------------------------------------------
// SSE (Server-Sent Events) utilities for AI streaming
// ---------------------------------------------------------------------------

type SSEProgressCallback = (stage: string, message: string) => void;

/**
 * Consume an SSE stream and return the final result from the 'done' event.
 * Calls onProgress for each 'progress' and 'meta' event received.
 */
async function consumeSSEStream<T>(
  url: string,
  options: RequestInit,
  onProgress?: SSEProgressCallback,
): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Accept': 'text/event-stream',
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  const decoder = new TextDecoder();
  let buffer = '';
  let result: T | null = null;
  let errorMessage: string | null = null;
  let currentEventType: string | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Parse SSE events from buffer
    const lines = buffer.split('\n');
    buffer = lines.pop() || ''; // Keep incomplete line in buffer


    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEventType = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        const data = line.slice(6);
        try {
          const parsed = JSON.parse(data);

          if (currentEventType === 'meta' && onProgress) {
            // Show agent/model info as the first progress step
            const agent = parsed.agent || 'AI';
            const model = parsed.model || '';
            const metaMessage = model ? `${agent} (${model})` : agent;
            onProgress('meta', `Starting ${metaMessage}...`);
          } else if (currentEventType === 'progress' && onProgress) {
            onProgress(parsed.stage, parsed.message);
          } else if (currentEventType === 'done') {
            result = parsed.result as T;
          } else if (currentEventType === 'error') {
            errorMessage = parsed.message || 'Unknown error';
          }
        } catch {
          // Skip malformed JSON
        }
        currentEventType = null;
      }
    }
  }

  if (errorMessage) {
    throw new Error(errorMessage);
  }

  if (result === null) {
    throw new Error('No result received from SSE stream');
  }

  return result;
}

const parseAIError = async (response: Response, fallback: string): Promise<string> => {
  const payload = await response.json().catch(() => null);
  if (payload && typeof payload.detail === 'string' && payload.detail.trim()) {
    return payload.detail;
  }
  if (response.status === 404) {
    return 'AI is not enabled for this user';
  }
  return fallback;
};

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

export class AuthError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'AuthError';
    this.status = status;
  }
}

export const getCurrentUser = async (): Promise<User> => {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    credentials: 'include',
  });
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      throw new AuthError('Session expired', response.status);
    }
    throw new Error('Failed to get current user');
  }
  return response.json();
};

export const refreshSession = async (): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      throw new AuthError('Session expired', response.status);
    }
    throw new Error('Failed to refresh session');
  }
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

export const generateGmailQuestions = async (
  emails: any[],
  interest: string,
  previousAnswers: string[] = [],
  questionCount = 2,
  onProgress?: SSEProgressCallback,
): Promise<{ questions: string[] }> => {
  return consumeSSEStream<{ questions: string[] }>(
    `${API_BASE_URL}/ai/gmail/questions`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        emails,
        interest,
        previous_answers: previousAnswers,
        question_count: questionCount,
      }),
    },
    onProgress,
  );
};

export const generateGmailSummary = async (
  emails: any[],
  interest: string,
  answers: string[],
  onProgress?: SSEProgressCallback,
): Promise<{ final_summary: string; top_email_ids: string[]; reasoning: string }> => {
  return consumeSSEStream<{ final_summary: string; top_email_ids: string[]; reasoning: string }>(
    `${API_BASE_URL}/ai/gmail/summary`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ emails, interest, answers }),
    },
    onProgress,
  );
};

export const generateCalendarQuestion = async (
  request: string,
  previousAnswers: string[] = [],
  onProgress?: SSEProgressCallback,
): Promise<{ status: 'clarify' | 'confirm'; question: string; event: CalendarEventPayload }> => {
  return consumeSSEStream<{ status: 'clarify' | 'confirm'; question: string; event: CalendarEventPayload }>(
    `${API_BASE_URL}/ai/calendar/questions`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ request, previous_answers: previousAnswers }),
    },
    onProgress,
  );
};

export const createCalendarEvent = async (
  event: CalendarEventPayload,
  onProgress?: SSEProgressCallback,
): Promise<{ event_id: string | null; html_link: string | null; summary: string | null }> => {
  return consumeSSEStream<{ event_id: string | null; html_link: string | null; summary: string | null }>(
    `${API_BASE_URL}/ai/calendar/create`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ event }),
    },
    onProgress,
  );
};

export const fetchGmailMessages = async (): Promise<{ emails: any[] }> => {
  const response = await fetch(`${API_BASE_URL}/auth/gmail/messages`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Failed to fetch Gmail messages');
  }
  return response.json();
};

export const generatePdf = async (
  title: string,
  sections: { heading: string; content: string }[],
  links: string[] = []
): Promise<{ url: string }> => {
  const response = await fetch(`${API_BASE_URL}/media/pdf/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ title, sections, links }),
  });
  if (!response.ok) {
    throw new Error('Failed to generate PDF');
  }
  return response.json();
};

export const fetchRandomClaim = async (): Promise<ClaimResponse> => {
  const response = await fetch(`${API_BASE_URL}/media/claims/random`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch claim' }));
    throw new Error(error.detail || 'Failed to fetch claim');
  }
  return response.json();
};

export const fetchDeepReviewClaim = async (): Promise<ClaimResponse> => {
  const response = await fetch(`${API_BASE_URL}/media/claims/deep-review/random`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch deep review claim' }));
    throw new Error(error.detail || 'Failed to fetch deep review claim');
  }
  return response.json();
};

export const fetchClaimFiles = async (claimId: string): Promise<ClaimFilesResponse> => {
  const response = await fetch(`${API_BASE_URL}/media/claims/${claimId}/files`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch claim files' }));
    throw new Error(error.detail || 'Failed to fetch claim files');
  }
  return response.json();
};

const encodeClaimFilename = (filename: string): string =>
  filename.split('/').map(encodeURIComponent).join('/');

export const fetchClaimFileContent = async (claimId: string, filename: string): Promise<unknown> => {
  const encodedFilename = encodeClaimFilename(filename);
  const response = await fetch(`${API_BASE_URL}/media/claims/${claimId}/files/${encodedFilename}`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.text().catch(() => 'Failed to fetch file');
    throw new Error(error || 'Failed to fetch file');
  }
  // For JSON files, parse and return the JSON object
  // For other files, return as text (or could return blob for binary)
  const lowerFilename = filename.toLowerCase();
  if (lowerFilename.endsWith('.json')) {
    return response.json();
  }
  // Return text for other text-based files
  return response.text();
};

export const getClaimFileUrl = (claimId: string, filename: string): string =>
  `${API_BASE_URL}/media/claims/${claimId}/files/${encodeClaimFilename(filename)}`;

export const generateClaimAnswer = async (
  claim: unknown,
  question: string,
  history: ClaimQaHistoryEntry[] = [],
  questionCount = 0,
  askedQuestions: string[] = [],
  toolHistory: ClaimToolCall[] = [],
  sessionId?: string | null,
  onProgress?: SSEProgressCallback,
): Promise<ClaimQaResponse> => {
  return consumeSSEStream<ClaimQaResponse>(
    `${API_BASE_URL}/ai/claims/qa`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        claim,
        question,
        history,
        question_count: questionCount,
        asked_questions: askedQuestions,
        tool_history: toolHistory,
        session_id: sessionId ?? undefined,
      }),
    },
    onProgress,
  );
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

export const createChannel = async (
  name: string,
  type: 'public' | 'private' = 'public',
  isDataProcessor: boolean = false,
): Promise<Channel> => {
  const response = await fetch(`${API_BASE_URL}/channels`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ name, type, is_data_processor: isDataProcessor }),
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

export const uploadMedia = async (file: File): Promise<{ url: string }> => {
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

export const uploadImage = uploadMedia;

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
    const error = await response
      .json()
      .catch(() => ({ detail: 'Failed to get channel members' }));
    if (response.status === 403) {
      console.warn('Channel members unavailable:', error.detail || response.statusText);
      return [];
    }
    throw new Error(error.detail || 'Failed to get channel members');
  }
  const data = await response.json();
  return Array.isArray(data) ? data : [];
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

// AI Agent APIs (status/health checks still go through Caddy to ADK directly)
export const getAIStatus = async (): Promise<AIStatus> => {
  const response = await fetch(`${API_BASE_URL}/adk/ai/status`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error(await parseAIError(response, 'Failed to get AI status'));
  }
  return response.json();
};

export const getAIHealth = async (): Promise<{ service: string; status: string }> => {
  const response = await fetch(`${API_BASE_URL}/adk/healthz`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('AI service health check failed');
  }
  return response.json();
};

export const getGmailAuthUrl = async (): Promise<{ authorization_url: string }> => {
  const response = await fetch(`${API_BASE_URL}/auth/gmail/start`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to get Gmail auth URL' }));
    throw new Error(error.detail || 'Failed to get Gmail auth URL');
  }
  return response.json();
};

export const getInferenceLogs = async (
  limit: number = 100,
): Promise<{ events: InferenceLogEvent[]; total: number }> => {
  const response = await fetch(`${API_BASE_URL}/api/inference/logs?limit=${limit}`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to get inference logs' }));
    throw new Error(error.detail || 'Failed to get inference logs');
  }
  return response.json();
};

// ---------------------------------------------------------------------------
// Claim damage-annotation API (proxied through backend)
// ---------------------------------------------------------------------------

export type CreateClaimDocRequest = {
  image_url: string;
  source_key: string;
  source_parent_key?: string;
  original_filename?: string;
};

export type CreateClaimAnnotationRequest = {
  document_id: string;
  label_type: string;
  label_name?: string;
  color?: string;
  bounding_box: { x: number; y: number; width: number; height: number; rotation?: number };
  verification_status?: string;
  certainty?: number;
  review_value?: string | null;
};

export type DamageAnnotationEntry = {
  id: string;
  document_id: string;
  label_type: string;
  label_name: string;
  color: string;
  bounding_box: { x: number; y: number; width: number; height: number; rotation?: number };
  verification_status: string;
  certainty: number | null;
  review_value: string | null;
  original_filename: string | null;
  image_url: string | null;
};

export const createClaimDocument = async (
  claimId: string,
  body: CreateClaimDocRequest,
): Promise<Record<string, unknown>> => {
  const response = await fetch(`${API_BASE_URL}/media/claims/${claimId}/documents/from-minio`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create document' }));
    throw new Error(error.detail || 'Failed to create document');
  }
  return response.json();
};

export const createClaimAnnotation = async (
  claimId: string,
  body: CreateClaimAnnotationRequest,
): Promise<Record<string, unknown>> => {
  const response = await fetch(`${API_BASE_URL}/media/claims/${claimId}/damage-annotations`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create annotation' }));
    throw new Error(error.detail || 'Failed to create annotation');
  }
  return response.json();
};

export const fetchClaimAnnotations = async (
  claimId: string,
): Promise<{ claim_id: string; annotations: DamageAnnotationEntry[]; count: number }> => {
  const response = await fetch(`${API_BASE_URL}/media/claims/${claimId}/damage-annotations`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch annotations' }));
    throw new Error(error.detail || 'Failed to fetch annotations');
  }
  return response.json();
};

// ---------------------------------------------------------------------------
// Annotation session & export persistence
// ---------------------------------------------------------------------------

export const createAnnotationSession = async (
  claimId: string,
): Promise<{ session_id: string; created: boolean }> => {
  const response = await fetch(`${API_BASE_URL}/media/claims/${claimId}/annotation-session`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create annotation session' }));
    throw new Error(error.detail || 'Failed to create annotation session');
  }
  return response.json();
};

export const persistAnnotationExport = async (
  claimId: string,
  sessionId: string,
  documentId: string,
  findings: unknown,
  sourceFilename?: string,
): Promise<{
  status: string
  debug_event_id: string
  annotation_result_id: string
  damage_labels: string[]
  stream_msg_id: string
  ai_message_id: number | null
}> => {
  const response = await fetch(`${API_BASE_URL}/media/claims/${claimId}/annotation-export`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      document_id: documentId,
      findings,
      source_filename: sourceFilename ?? null,
    }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to persist annotation export' }));
    throw new Error(error.detail || 'Failed to persist annotation export');
  }
  return response.json();
};

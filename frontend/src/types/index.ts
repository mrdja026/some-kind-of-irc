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
  is_data_processor?: boolean;
};

export type Message = {
  id: number;
  content: string;
  sender_id: number | null;
  channel_id: number;
  timestamp: string;
  client_temp_id?: number;
  image_url?: string | null;
  username?: string;
  display_name?: string | null;
  target_user_id?: number | null;
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

// Game types matching external_schemas
export type Position = {
  x: number;
  y: number;
};

export type Player = {
  user_id: number;
  username: string;
  display_name?: string;
  position: Position;
  health: number;
  max_health: number;
  is_active: boolean;
  is_npc: boolean;
};

export type Obstacle = {
  id: string;
  type: string;
  position: Position;
};

export type BattlefieldProp = {
  id: string;
  type: 'tree' | 'rock';
  position: Position;
  is_blocking: boolean;
  zone: 'play' | 'buffer';
};

export type BufferZone = {
  thickness: number;
  tiles: Position[];
};

export type Battlefield = {
  seed: number;
  props: BattlefieldProp[];
  buffer: BufferZone;
};

export type GameSnapshotPayload = {
  map: { width: number; height: number };
  players: Player[];
  obstacles: Obstacle[];
  battlefield: Battlefield;
  active_turn_user_id: number | null;
};

export type GameStateUpdatePayload = {
  active_turn_user_id: number | null;
  players: Player[];
};

export type ActionResultPayload = {
  success: boolean;
  action_type: string;
  executor_id: number;
  target_id: number | null;
  message: string;
  error: { code: string; message: string; details: any } | null;
};

// WebSocket Events
export type GameSnapshotEvent = {
  type: 'game_snapshot';
  timestamp: string;
  payload: GameSnapshotPayload;
  channel_id: number; // Injected by WS handler for routing
};

export type GameStateUpdateEvent = {
  type: 'game_state_update';
  timestamp: string;
  payload: GameStateUpdatePayload;
  channel_id: number;
};

export type ActionResultEvent = {
  type: 'action_result';
  timestamp: string;
  payload: ActionResultPayload;
  channel_id: number;
};

export type WebSocketMessage = {
  type: 'message' | 'join' | 'leave' | 'typing' | 'game_snapshot' | 'game_state_update' | 'action_result' | 'error';
  id?: number;
  content?: string;
  image_url?: string | null;
  sender_id?: number | null;
  channel_id?: number;
  timestamp?: string;
  user_id?: number;
  username?: string;
  display_name?: string | null;
  channel_name?: string;
  target_user_id?: number | null;
  payload?: any; // For game events
};


// AI Agent types
export type AIIntent = 'afford' | 'learn';

export type AIQueryRequest = {
  intent: AIIntent;
  query: string;
  conversation_stage?: 'initial' | 'clarification';
  clarification_state?: AIClarificationState | null;
};

export type AIClarificationState = {
  original_query: string;
  questions: string[];
  answers: string[];
  fallback_flags?: boolean[];
  max_rounds?: number;
};

export type AIAgentCandidates = {
  [agentName: string]: string[];
};

export type AIAgentReasoning = {
  [agentName: string]: string;
};

export type AIQueryResponse =
  | {
      mode: 'clarify';
      intent: string;
      query: string;
      question: string;
      questions: string[];
      candidate_questions?: string[];
      other_suggested_questions?: string[];
      agent_candidates?: AIAgentCandidates;
      agent_reasoning?: AIAgentReasoning;
      judge_reasoning?: string;
      chosen_from_agent?: string;
      current_round?: number;
      total_rounds?: number;
      is_fallback_question?: boolean;
      clarification_state?: AIClarificationState;
      agent: string;
      disclaimer: string;
    }
  | {
      mode: 'final';
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
      type: 'progress';
      stage: 'collect_candidates' | 'rank_questions' | 'prepare_final';
      message: string;
    }
  | {
      type: 'clarify_question';
      intent: string;
      query: string;
      question: string;
      questions: string[];
      candidate_questions?: string[];
      other_suggested_questions?: string[];
      agent_candidates?: AIAgentCandidates;
      agent_reasoning?: AIAgentReasoning;
      judge_reasoning?: string;
      chosen_from_agent?: string;
      current_round?: number;
      total_rounds?: number;
      is_fallback_question?: boolean;
      clarification_state?: AIClarificationState;
      agent: string;
      disclaimer: string;
    }
  | {
      type: 'delta';
      text: string;
    }
  | {
      type: 'done';
      mode?: 'clarify' | 'final';
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

// Game types
export type GameState = {
  user_id: number;
  username?: string;
  display_name?: string;
  position_x: number;
  position_y: number;
  health: number;
  max_health: number;
  is_active: boolean;
  is_npc: boolean;
};

export type GameCommandRequest = {
  command: string;
  target_username?: string;
  channel_id?: number;
};

export type GameCommandResponse = {
  success: boolean;
  command?: string;
  message?: string;
  error?: string;
  game_state?: GameState;
};

export type GameAction = {
  type: 'game_action';
  channel_id: number;
  executor_id: number;
  action: {
    success: boolean;
    command: string;
    message: string;
    game_state?: GameState;
  };
};

export type GameStateUpdate = {
  type: 'game_state_update';
  channel_id: number;
  game_state: GameState;
};

export type GameCommands = string[];

// Data Processor types
export type LabelType = 'header' | 'table' | 'signature' | 'date' | 'amount' | 'custom';

export type BoundingBox = {
  x: number;
  y: number;
  width: number;
  height: number;
  rotation?: number;
};

export type Annotation = {
  id: string;
  document_id: string;
  label_type: LabelType;
  label_name: string;
  color: string;
  bounding_box: BoundingBox;
  extracted_text?: string | null;
  confidence?: number | null;
  created_at: string;
};

export type OcrStatus = 'pending' | 'processing' | 'completed' | 'failed';

export type Document = {
  id: string;
  channel_id: string;
  uploaded_by: string;
  original_filename: string;
  image_url?: string;
  width?: number;
  height?: number;
  ocr_status: OcrStatus;
  ocr_result?: OcrResult | null;
  annotations: Annotation[];
  created_at: string;
};

export type DetectedRegion = {
  id: string;
  type: string;
  x: number;
  y: number;
  width: number;
  height: number;
  text: string;
  confidence: number;
};

export type OcrResult = {
  detected_regions: DetectedRegion[];
  extracted_text: string;
};

export type TemplateLabel = {
  id: string;
  label_type: LabelType;
  label_name: string;
  color: string;
  relative_x: number;
  relative_y: number;
  relative_width: number;
  relative_height: number;
  expected_format?: string | null;
  is_required: boolean;
};

export type Template = {
  id: string;
  channel_id: string;
  created_by: string;
  name: string;
  description: string;
  thumbnail_url?: string | null;
  version: number;
  is_active: boolean;
  labels: TemplateLabel[];
  created_at: string;
};

export type MatchedRegion = {
  label_id: string;
  label_name: string;
  label_type: LabelType;
  x: number;
  y: number;
  width: number;
  height: number;
  matched_text?: string | null;
  confidence: number;
};

// Data Processor WebSocket events
export type DocumentUploadedEvent = {
  type: 'document_uploaded';
  document_id: string;
  channel_id: number;
  uploaded_by: string;
  filename: string;
  thumbnail_url?: string | null;
};

export type OcrProgressEvent = {
  type: 'ocr_progress';
  document_id: string;
  channel_id: number;
  stage: 'preprocessing' | 'detection' | 'extraction' | 'mapping';
  progress: number;
  message: string;
};

export type OcrCompleteEvent = {
  type: 'ocr_complete';
  document_id: string;
  channel_id: number;
  detected_regions: DetectedRegion[];
  extracted_text: string;
};

export type TemplateAppliedEvent = {
  type: 'template_applied';
  document_id: string;
  channel_id: number;
  template_id: string;
  matched_regions: MatchedRegion[];
  confidence: number;
};

export type DataProcessorEvent =
  | DocumentUploadedEvent
  | OcrProgressEvent
  | OcrCompleteEvent
  | TemplateAppliedEvent;

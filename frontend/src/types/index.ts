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

export type WebSocketMessage = {
  type: 'message' | 'join' | 'leave' | 'typing' | 'game_action' | 'game_state_update';
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

// Game types
export type GameState = {
  user_id: number;
  username?: string;
  display_name?: string;
  position_x: number;
  position_y: number;
  health: number;
  max_health: number;
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

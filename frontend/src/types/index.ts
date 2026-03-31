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
  type: 'message' | 'join' | 'leave' | 'typing' | 'error';
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
  payload?: unknown;
};

// AI Agent types
export type AIIntent = 'gmail';

export type CalendarEventPayload = {
  title: string;
  start_datetime: string;
  end_datetime: string;
  timezone: string;
  attendees: string[];
};

export type AIStatus = {
  available: boolean;
  remaining_requests: number;
  max_requests_per_hour: number;
};

export type ClaimResponse = {
  filename: string;
  claim: unknown;
};

export type ClaimFileEntry = {
  key: string;
  filename: string;
  size: number;
  last_modified: string | null;
};

export type ClaimFilesResponse = {
  claim_id: string;
  files: ClaimFileEntry[];
};

export type ClaimQaHistoryEntry = {
  question: string;
  answer: string;
};

export type ClaimQaFlags = {
  summary_ok?: boolean;
  timeline_ok?: boolean;
  status_ok?: boolean;
  status?: string | null;
  is_off?: boolean;
  issues?: unknown[];
  claim_valid?: boolean;
};

export type ClaimToolCall = {
  name: string;
  result: unknown;
  stage?: string;
  attempt?: number;
};

export type ClaimQaResponse = {
  answer: string;
  reasoning: string;
  done?: boolean;
  next_question?: string | null;
  followup_reasoning?: string | null;
  tool_calls?: ClaimToolCall[] | null;
  tool_history?: ClaimToolCall[] | null;
  flags?: ClaimQaFlags;
  session_id?: string | null;
};

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
  file_type?: 'image' | 'pdf';
  page_count?: number;
  pdf_text_layer?: unknown;
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

// Inference Timeline types
export type GmailStepStage =
  | 'questions'
  | 'summary_action'
  | 'summary_insight'
  | 'classification'
  | 'judge';

export type GmailStepPayload = {
  stage: GmailStepStage;
  input_preview: string;
  output: Record<string, unknown>;
  model: string;
};

export type InferenceLogEvent = {
  event_id: string;
  recorded_at: string;
  source: 'ai_service' | 'ai_service_adk' | 'caddy';
  kind: string;
  backend: 'crewai' | 'google_adk' | 'local_vllm' | 'n/a';
  username?: string;
  request_id?: string;
  correlation_id?: string;
  payload: GmailStepPayload | Record<string, unknown>;
};

export type SessionDump = {
  schema_version: string;
  exported_at: string;
  sources: string[];
  session_id?: string;
  annotations?: {
    git_sha?: string;
    image_tag?: string;
  };
  events: InferenceLogEvent[];
};

export type StageColorMap = {
  [key in GmailStepStage]: {
    bg: string;
    border: string;
    text: string;
    label: string;
  };
};

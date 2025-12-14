export interface Utterance {
  id: number;
  text: string;
}

export interface TranscriptionState {
  interim_text: string;
  finalized_text: string;
}

export interface StatusUpdate {
  type: "status_update";
  mode: "test" | "speech" | "idle";
  is_running: boolean;
  transcription?: TranscriptionState | null;
  utterances: Utterance[];
  document: Record<string, any>;
  formatted_document: string;
  metrics?: {
    total_utterances?: number;
    successful?: number;
    failed?: number;
    avg_latency_seconds?: number;
    total_cost_usd?: number;
    total_tokens?: number;
    estimated_hourly_cost_usd?: number;
  } | null;
}

export interface Command {
  type: "start" | "stop" | "speech_chunk";
  mode?: "test" | "speech";
  config?: {
    utterances?: string[] | string;
    model?: string;
    temperature?: number;
    chunk_delay_ms?: number;
    finalize_pause_ms?: number;
    input_source?: string;
  };
  chunk?: {
    text: string;
    is_final: boolean;
    result_index?: number;
  };
}

export interface ErrorMessage {
  type: "error";
  message: string;
}

export type WebSocketMessage = StatusUpdate | ErrorMessage;


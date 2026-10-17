/** Shared REST contract. Browser requests use the Next.js backend proxy. */
import type { SessionScore } from "./websocket";

export type Language = "en" | "vi" | "bilingual";
export type DebateStance = "pro" | "con";
export type Difficulty = "beginner" | "advanced" | "expert";
export type SessionStatus = "pending" | "active" | "ended" | "graded";
export interface DebateConfig {
  topic: string;
  topic_description: string;
  language: Language;
  difficulty: Difficulty;
  user_position: DebateStance;
  ai_position: DebateStance;
}
export interface CreateSessionRequest {
  topic: string;
  topic_description?: string;
  language?: Language;
  difficulty?: Difficulty;
  user_position?: DebateStance;
  max_turns?: number;
}
export interface SessionMetadata {
  session_id: string;
  config: DebateConfig;
  status: SessionStatus;
  turn_count: number;
  max_turns: number;
  created_at: string;
  ended_at: string | null;
  grade: SessionScore | null;
}
export interface SessionHistoryEntry {
  session_id: string;
  topic: string;
  user_position: DebateStance;
  status: SessionStatus;
  turn_count: number;
  created_at: string;
  ended_at: string | null;
  grade: SessionScore | null;
}
export interface SessionHistoryResponse {
  sessions: SessionHistoryEntry[];
  missing_session_ids: string[];
}
export interface EndSessionResponse {
  session_id: string;
  status: SessionStatus;
  message: string;
}
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
const BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "/api";
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    cache: "no-store",
    signal: options.signal ?? AbortSignal.timeout(150_000),
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...options.headers,
    },
  });
  const text = await res.text();
  let body: unknown;
  try {
    body = text ? JSON.parse(text) : undefined;
  } catch {
    body = text;
  }
  if (!res.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body ? body.detail : null;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail
              .map((item: { msg?: string }) => item.msg || "Invalid input")
              .join("; ")
          : `Yêu cầu thất bại (${res.status}). Vui lòng thử lại.`;
    throw new ApiError(res.status, message);
  }
  return body as T;
}
export const createSession = (body: CreateSessionRequest) =>
  request<SessionMetadata>("/session/create", {
    method: "POST",
    body: JSON.stringify(body),
  });
export const getSession = (id: string) =>
  request<SessionMetadata>(`/session/${encodeURIComponent(id)}`);
export const getSessionHistory = (sessionIds: string[]) =>
  request<SessionHistoryResponse>("/session/history", {
    method: "POST",
    body: JSON.stringify({ session_ids: sessionIds }),
  });
export const endSession = (id: string, body: { reason?: string } = {}) =>
  request<EndSessionResponse>(`/session/${encodeURIComponent(id)}/end`, {
    method: "POST",
    body: JSON.stringify(body),
  });
export const checkHealth = () =>
  request<{ status: "ok" | "degraded"; service: string }>("/health");

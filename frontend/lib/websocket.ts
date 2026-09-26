// frontend/lib/websocket.ts
/**
 * WebSocket client + React hook for the SocraticAI real-time debate stream.
 *
 * Backend frame protocol (server → client):
 *   { "type": "token",         "data": "..." }           — streamed AI token
 *   { "type": "fallacy",       "data": FallacyResult }   — detected fallacy
 *   { "type": "score",         "data": SessionScore }    — post-session grade
 *   { "type": "contradiction", "data": "..." }           — contradiction alert
 *   { "type": "error",         "data": "..." }           — error message
 *
 * Client → server:
 *   { "type": "user_message",  "data": { "content": "...", "language": "en" } }
 *   { "type": "end_session",   "data": { "reason": "..." } }
 *   { "type": "ping",          "data": {} }
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { DebateConfig, SessionStatus } from "./api";

// ─── Types ──────────────────────────────────────────────────────────────────

export type ConnectionStatus =
  "connecting" | "connected" | "reconnecting" | "disconnected";

export type FallacySeverity = "minor" | "moderate" | "major";

export interface FallacyResult {
  fallacy_type: string;
  fallacy_name_vi: string;
  severity: FallacySeverity;
  offending_excerpt: string;
  explanation: string;
  suggestion: string;
  confidence: number;
}

export interface Claim {
  claim_id: string;
  session_id: string;
  turn_number: number;
  speaker: "user" | "ai";
  claim_text: string;
  claim_type:
    "assertion" | "concession" | "retraction" | "commitment" | "question";
  key_entities: string[];
}

export interface SessionScore {
  argument_depth: number;
  logical_consistency: number;
  evidence_quality: number;
  rebuttal_effectiveness: number;
  total: number;
  grade: "A" | "B" | "C" | "D" | "F";
  fallacies_committed: number;
  contradictions_caught: number;
  strengths_en: string[];
  strengths_vi: string[];
  improvements_en: string[];
  improvements_vi: string[];
  verdict_en: string;
  verdict_vi: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "ai";
  content: string;
  timestamp: number;
  isStreaming?: boolean;
  hasContradiction?: boolean;
}

export interface SessionSnapshot {
  turns: {
    turn_number: number;
    speaker: "user" | "ai";
    content: string;
    timestamp: string;
  }[];
  extracted_claims: Claim[];
  fallacy_analysis: FallacyResult[];
  contradiction_alerts: string[];
  session_score: SessionScore | null;
  status: SessionStatus;
  turn_count: number;
  max_turns: number;
  config: DebateConfig;
}
export interface WSFrame {
  type:
    | "token"
    | "fallacy"
    | "score"
    | "contradiction"
    | "error"
    | "pong"
    | "sync"
    | "turn_done"
    | "session_ended"
    | "grading";
  data: unknown;
}
export function debateSocketUrl(sessionId: string): string {
  const configured =
    process.env.NEXT_PUBLIC_WS_URL || process.env.NEXT_PUBLIC_API_URL;
  const url = new URL(
    configured || window.location.origin,
    window.location.origin,
  );
  url.protocol =
    url.protocol === "https:" || url.protocol === "wss:" ? "wss:" : "ws:";
  url.pathname = `${url.pathname.replace(/\/$/, "")}/ws/debate/${encodeURIComponent(sessionId)}`;
  return url.toString();
}

export function useDebateSession(sessionId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isGrading, setIsGrading] = useState(false);
  const [fallacies, setFallacies] = useState<FallacyResult[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [score, setScore] = useState<SessionScore | null>(null);
  const [contradictionAlerts, setContradictionAlerts] = useState<string[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [session, setSession] = useState<SessionSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [failedMessage, setFailedMessage] = useState<string | null>(null);
  const pendingMessageRef = useRef<string | null>(null);
  const [retry, setRetry] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const busyRef = useRef(false);
  const readyRef = useRef(false);
  const streamIdRef = useRef<string | null>(null);

  const finishStream = useCallback(() => {
    streamIdRef.current = null;
    busyRef.current = false;
    setIsStreaming(false);
    setMessages((previous) =>
      previous.map((message) =>
        message.isStreaming ? { ...message, isStreaming: false } : message,
      ),
    );
  }, []);

  useEffect(() => {
    let disposed = false;
    let attempts = 0;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let heartbeat: ReturnType<typeof setInterval>;
    setMessages([]);
    setFallacies([]);
    setClaims([]);
    setScore(null);
    setSession(null);
    setError(null);
    setContradictionAlerts([]);
    setIsGrading(false);
    finishStream();
    readyRef.current = false;

    const connect = () => {
      if (disposed) return;
      setStatus(attempts ? "reconnecting" : "connecting");
      const ws = new WebSocket(debateSocketUrl(sessionId));
      wsRef.current = ws;
      const isCurrent = () => !disposed && wsRef.current === ws;
      ws.onopen = () => {
        if (!isCurrent()) return;
        heartbeat = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN)
            ws.send(JSON.stringify({ type: "ping", data: {} }));
        }, 25_000);
      };
      ws.onmessage = (event) => {
        if (!isCurrent()) return;
        try {
          const frame = JSON.parse(event.data) as WSFrame;
          switch (frame.type) {
            case "token": {
              const token = frame.data;
              if (typeof token !== "string") return;
              busyRef.current = true;
              setIsStreaming(true);
              // Allocate outside state updaters: React Strict Mode may replay them.
              const id = streamIdRef.current ?? crypto.randomUUID();
              streamIdRef.current = id;
              setMessages((previous) =>
                previous.some((m) => m.id === id)
                  ? previous.map((m) =>
                      m.id === id ? { ...m, content: m.content + token } : m,
                    )
                  : [
                      ...previous,
                      {
                        id,
                        role: "ai",
                        content: token,
                        timestamp: Date.now(),
                        isStreaming: true,
                      },
                    ],
              );
              break;
            }
            case "sync":
            case "turn_done": {
              const snapshot = frame.data as SessionSnapshot;
              finishStream();
              pendingMessageRef.current = null;
              setSession(snapshot);
              setMessages(
                snapshot.turns.map((turn) => ({
                  id: `${turn.turn_number}-${turn.speaker}`,
                  role: turn.speaker,
                  content: turn.content,
                  timestamp: Date.parse(turn.timestamp),
                })),
              );
              setClaims(snapshot.extracted_claims);
              setFallacies(snapshot.fallacy_analysis);
              setContradictionAlerts(snapshot.contradiction_alerts ?? []);
              setScore(snapshot.session_score);
              readyRef.current = true;
              attempts = 0;
              setStatus("connected");
              break;
            }
            case "fallacy":
              setFallacies((previous) => [
                ...previous,
                frame.data as FallacyResult,
              ]);
              break;
            case "contradiction":
              setContradictionAlerts((previous) => [
                ...previous,
                String(frame.data),
              ]);
              break;
            case "grading":
              finishStream();
              busyRef.current = true;
              setIsGrading(true);
              setSession((previous) =>
                previous ? { ...previous, status: "ended" } : previous,
              );
              break;
            case "score":
              finishStream();
              setIsGrading(false);
              setScore(frame.data as SessionScore);
              setSession((previous) =>
                previous ? { ...previous, status: "graded" } : previous,
              );
              break;
            case "session_ended":
              finishStream();
              setIsGrading(false);
              setSession((previous) =>
                previous
                  ? {
                      ...previous,
                      status: (frame.data as { status: SessionStatus }).status,
                    }
                  : previous,
              );
              break;
            case "error":
              setFailedMessage(pendingMessageRef.current);
              pendingMessageRef.current = null;
              finishStream();
              setIsGrading(false);
              setError(String(frame.data));
              break;
          }
        } catch {
          setError("Invalid server response. Please reconnect.");
          finishStream();
        }
      };
      ws.onclose = (event) => {
        if (!isCurrent()) return;
        clearInterval(heartbeat);
        readyRef.current = false;
        finishStream();
        setIsGrading(false);
        if (![1000, 1008].includes(event.code) && attempts < 5) {
          attempts += 1;
          setStatus("reconnecting");
          reconnectTimer = setTimeout(connect, 1000 * 2 ** (attempts - 1));
        } else {
          setStatus("disconnected");
          if (![1000, 1008].includes(event.code))
            setError("Mất kết nối. Vui lòng kết nối lại để tiếp tục phiên tranh luận.");
        }
      };
    };
    connect();
    return () => {
      disposed = true;
      clearTimeout(reconnectTimer);
      clearInterval(heartbeat);
      readyRef.current = false;
      wsRef.current?.close(1000, "Rời khỏi phiên tranh luận");
      wsRef.current = null;
    };
  }, [sessionId, retry, finishStream]);

  const sendMessage = useCallback(
    (content: string, language = "vi"): boolean => {
      const ws = wsRef.current;
      if (
        !ws ||
        ws.readyState !== WebSocket.OPEN ||
        !readyRef.current ||
        busyRef.current ||
        score ||
        session?.status === "ended"
      )
        return false;
      if (!content.trim() || content.length > 1000) return false;
      try {
        ws.send(
          JSON.stringify({
            type: "user_message",
            data: { content: content.trim(), language },
          }),
        );
      } catch {
        setError("Không thể gửi tin nhắn. Vui lòng kết nối lại.");
        return false;
      }
      busyRef.current = true;
      pendingMessageRef.current = content;
      setFailedMessage(null);
      streamIdRef.current = null;
      setError(null);
      setIsStreaming(true);
      setMessages((previous) => [
        ...previous,
        {
          id: crypto.randomUUID(),
          role: "user",
          content: content.trim(),
          timestamp: Date.now(),
        },
      ]);
      return true;
    },
    [session, score],
  );
  const endDebate = useCallback(
    (reason = "User ended debate") => {
      const ws = wsRef.current;
      if (
        !ws ||
        ws.readyState !== WebSocket.OPEN ||
        !readyRef.current ||
        busyRef.current ||
        score
      )
        return;
      try {
        ws.send(JSON.stringify({ type: "end_session", data: { reason } }));
      } catch {
        setError("Unable to request scoring. Please reconnect.");
        return;
      }
      busyRef.current = true;
      setIsGrading(true);
      setError(null);
    },
    [score],
  );
  return {
    sendMessage,
    endDebate,
    messages,
    isStreaming,
    isGrading,
    fallacies,
    claims,
    score,
    contradictionAlerts,
    status,
    session,
    error,
    failedMessage,
    reconnect: () => setRetry((value) => value + 1),
    dismissError: () => setError(null),
  };
}

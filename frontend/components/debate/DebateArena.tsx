// frontend/components/debate/DebateArena.tsx
// Three-panel debate room: Session Info | Chat | Claim Tracker
"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import {
  MessageSquare,
  Zap,
  FileText,
  Clock,
  ChevronLeft,
  Send,
  StopCircle,
  Wifi,
  WifiOff,
  Loader2,
} from "lucide-react";
import { useDebateSession } from "@/lib/websocket";
import type { ConnectionStatus, Claim } from "@/lib/websocket";
import { FallacyCard } from "@/components/FallacyCard";
import { ScoreModal } from "@/components/ScoreModal";

// ─── Types ──────────────────────────────────────────────────────────────────

interface DebateArenaProps {
  sessionId: string;
  topic?: string;
  userPosition?: string;
  historyWarning?: boolean;
}

// ─── Connection Status Badge ─────────────────────────────────────────────────

const STATUS_CONFIG: Record<
  ConnectionStatus,
  { label: string; icon: React.ReactNode; color: string }
> = {
  connecting: {
    label: "Đang kết nối…",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
    color: "text-yellow-400",
  },
  connected: {
    label: "Đã kết nối",
    icon: <Wifi className="h-3 w-3" />,
    color: "text-emerald-400",
  },
  reconnecting: {
    label: "Đang kết nối lại…",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
    color: "text-orange-400",
  },
  disconnected: {
    label: "Mất kết nối",
    icon: <WifiOff className="h-3 w-3" />,
    color: "text-red-400",
  },
};

// ─── Claim Card ──────────────────────────────────────────────────────────────

interface ClaimCardProps {
  claim: Claim;
  index: number;
}

function ClaimCard({ claim, index }: ClaimCardProps) {
  const isUser = claim.speaker === "user";
  const borderColor = isUser ? "border-l-brand-500" : "border-l-accent";

  const typeLabels: Record<string, { label: string; className: string }> = {
    assertion: {
      label: "Khẳng định",
      className: "bg-brand-600/15 text-brand-300",
    },
    concession: {
      label: "Nhượng bộ",
      className: "bg-amber-500/15 text-amber-400",
    },
    retraction: {
      label: "Rút lại",
      className: "bg-red-500/15 text-red-400",
    },
    commitment: {
      label: "Cam kết",
      className: "bg-teal-500/15 text-teal-400",
    },
    question: {
      label: "Câu hỏi",
      className: "bg-purple-500/15 text-purple-400",
    },
  };

  const typeConfig = typeLabels[claim.claim_type] ?? typeLabels.assertion;

  return (
    <motion.div
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25, delay: index * 0.03 }}
      className={`border-l-2 ${borderColor} bg-socratic-surface-2/40 rounded-r-lg p-3`}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
          {isUser ? "Bạn" : "SocraticAI"}
        </span>
        <span
          className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${typeConfig.className}`}
        >
          {typeConfig.label}
        </span>
      </div>
      <p className="text-xs text-foreground/80 leading-relaxed">
        {claim.claim_text}
      </p>
    </motion.div>
  );
}

// ─── DebateArena ─────────────────────────────────────────────────────────────

export function DebateArena({
  sessionId,
  topic,
  userPosition,
  historyWarning = false,
}: DebateArenaProps) {
  const {
    sendMessage,
    endDebate,
    messages,
    isStreaming,
    fallacies,
    claims,
    score,
    contradictionAlerts,
    status,
    session,
    error,
    reconnect,
    dismissError,
    isGrading,
    failedMessage,
  } = useDebateSession(sessionId);

  const [inputValue, setInputValue] = useState("");
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [showScoreModal, setShowScoreModal] = useState(false);

  const shouldScrollRef = useRef(true);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const charLimit = 1000;
  const charCount = inputValue.length;

  useEffect(() => {
    if (failedMessage) setInputValue(failedMessage);
  }, [failedMessage]);

  // Auto-scroll chat on new messages
  useEffect(() => {
    if (shouldScrollRef.current)
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-show score modal when score arrives
  useEffect(() => {
    if (score) {
      setShowScoreModal(true);
    }
  }, [score]);

  // Send handler
  const handleSend = useCallback(() => {
    const content = inputValue.trim();
    if (!content || isStreaming || status !== "connected") return;
    if (content.length > charLimit) return;

    shouldScrollRef.current = true;
    if (sendMessage(content, session?.config.language)) setInputValue("");
    inputRef.current?.focus();
  }, [inputValue, isStreaming, status, sendMessage, session]);

  // Key handler: Cmd/Ctrl+Enter to send
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleEndDebate = () => {
    endDebate("Người dùng kết thúc tranh luận");
  };

  topic = session?.config.topic ?? topic;
  userPosition = session?.config.user_position ?? userPosition;
  const userPositionLabel =
    userPosition === "pro"
      ? "Ủng hộ (Pro)"
      : userPosition === "con"
        ? "Phản đối (Con)"
        : userPosition;
  const ended =
    !!score || session?.status === "ended" || session?.status === "graded";
  const inputDisabled =
    isStreaming || isGrading || ended || status !== "connected";
  const statusConfig = STATUS_CONFIG[status];
  const turnCount = messages.filter((m) => m.role === "user").length;

  return (
    <>
      <div className="flex flex-col h-dvh max-h-dvh bg-socratic-bg">
        {/* ── Header ─────────────────────────────────────────────────────── */}
        <header className="glass-strong border-b border-socratic-border/50 px-4 py-3 flex items-center justify-between shrink-0 z-20">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="p-1.5 rounded-lg hover:bg-socratic-surface-2 transition-colors"
              aria-label="Quay lại trang chủ"
            >
              <ChevronLeft className="h-4 w-4 text-muted-foreground" />
            </Link>
            <div>
              <h1 className="font-heading font-bold text-base gradient-text">
                SocraticAI
              </h1>
              <p className="text-[11px] text-muted-foreground font-mono">
                {sessionId.slice(0, 8)}…
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Turn counter */}
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              <span>
                Lượt{" "}
                <strong className="text-foreground">
                  {session?.turn_count ?? turnCount}/{session?.max_turns ?? "–"}
                </strong>
              </span>
            </div>

            {/* Connection status */}
            <div
              className={`flex items-center gap-1.5 text-xs font-medium ${statusConfig.color}`}
            >
              {statusConfig.icon}
              <span className="hidden sm:inline">{statusConfig.label}</span>
            </div>

            {/* End debate */}
            <button
              onClick={handleEndDebate}
              aria-label={isGrading ? "Đang chấm điểm" : "Kết thúc & Chấm điểm"}
              disabled={
                status !== "connected" ||
                isStreaming ||
                isGrading ||
                !!score ||
                !turnCount
              }
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {isGrading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <StopCircle className="h-3.5 w-3.5" />
              )}
              <span className="hidden sm:inline">
                {isGrading ? "Đang chấm điểm…" : "Kết thúc & Chấm điểm"}
              </span>
            </button>
          </div>
        </header>

        {historyWarning && (
          <div
            role="alert"
            className="shrink-0 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-200"
          >
            Phiên đã được tạo nhưng không lưu được vào lịch sử trên trình duyệt
            này. Hãy kiểm tra quyền lưu trữ của trình duyệt.
          </div>
        )}

        {error && (
          <div
            role="alert"
            className="flex shrink-0 items-center gap-3 border-b border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300"
          >
            <span className="flex-1">{error}</span>
            {status === "disconnected" && !score && (
              <button onClick={reconnect} className="underline">
                Kết nối lại
              </button>
            )}
            <button onClick={dismissError} aria-label="Bỏ qua thông báo lỗi">
              ×
            </button>
          </div>
        )}
        {isGrading && (
          <div
            role="status"
            className="shrink-0 bg-brand-600/10 px-4 py-2 text-center text-sm"
          >
            Đang chấm điểm phiên tranh luận của bạn…
          </div>
        )}
        {ended && !isGrading && (
          <div className="flex shrink-0 flex-wrap items-center justify-center gap-4 px-4 py-2 text-sm bg-brand-600/10">
            <span>Phiên tranh luận đã kết thúc</span>
            {score && (
              <button
                onClick={() => setShowScoreModal(true)}
                className="text-brand-300 underline"
              >
                Xem kết quả
              </button>
            )}
            {!score && status === "disconnected" && (
              <button onClick={reconnect} className="underline">
                Kết nối lại để chấm điểm
              </button>
            )}
            <Link href="/debate/new" className="text-brand-300 underline">
              Tạo phiên mới
            </Link>
          </div>
        )}
        <div className="xl:hidden shrink-0 border-b border-socratic-border/50 px-4 py-2 flex min-w-0 items-center gap-3">
          <p className="min-w-0 flex-1 truncate text-xs" title={topic}>
            {topic ?? "Đang tải phiên…"}
            {userPositionLabel ? ` · ${userPositionLabel}` : ""}
          </p>
          <button
            onClick={() => setShowAnalysis((value) => !value)}
            aria-expanded={showAnalysis}
            aria-controls="mobile-analysis"
            className="shrink-0 text-xs text-brand-300"
          >
            {showAnalysis
              ? "Đóng phân tích"
              : `Phân tích (${fallacies.length} / ${claims.length})`}
          </button>
        </div>
        {showAnalysis && (
          <section
            id="mobile-analysis"
            aria-label="Phân tích tranh luận"
            className="xl:hidden max-h-[40dvh] shrink-0 overflow-y-auto border-b border-socratic-border p-4 space-y-3"
          >
            <h2 className="text-sm font-semibold">
              Ngụy biện ({fallacies.length})
            </h2>
            {fallacies.length ? (
              fallacies.map((fallacy, index) => (
                <FallacyCard key={index} fallacy={fallacy} />
              ))
            ) : (
              <p className="text-xs text-muted-foreground">
                Chưa phát hiện ngụy biện nào.
              </p>
            )}
            <h2 className="text-sm font-semibold">
              Luận điểm ({claims.length})
            </h2>
            {claims.length ? (
              claims.map((claim, index) => (
                <ClaimCard key={claim.claim_id} claim={claim} index={index} />
              ))
            ) : (
              <p className="text-xs text-muted-foreground">
                Chưa trích xuất luận điểm nào.
              </p>
            )}
          </section>
        )}

        {/* ── Three-Panel Layout ──────────────────────────────────────────── */}
        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* ── LEFT PANEL: Session Info + Fallacy Feed ────────────────────── */}
          <aside className="hidden lg:flex flex-col w-[280px] shrink-0 border-r border-socratic-border/50 bg-socratic-surface/30">
            {/* Session Info */}
            <div className="p-4 border-b border-socratic-border/30">
              <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
                <MessageSquare className="h-3.5 w-3.5" />
                Thông tin phiên
              </h2>
              {topic && (
                <p className="text-sm text-foreground font-medium mb-2 leading-snug">
                  {topic}
                </p>
              )}
              {userPositionLabel && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span>Lập trường của bạn:</span>
                  <span className="px-2 py-0.5 rounded-full bg-brand-600/15 text-brand-300 font-medium">
                    {userPositionLabel}
                  </span>
                </div>
              )}
            </div>

            {/* Fallacy Feed */}
            <div className="flex-1 flex flex-col min-h-0">
              <div className="p-4 pb-2">
                <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                  <Zap className="h-3.5 w-3.5 text-danger" />
                  Bảng ngụy biện
                  {fallacies.length > 0 && (
                    <span className="ml-auto text-[10px] bg-red-500/15 text-red-400 px-1.5 py-0.5 rounded-full">
                      {fallacies.length}
                    </span>
                  )}
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-2">
                {fallacies.length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-8 italic">
                    Chưa phát hiện ngụy biện nào.
                    <br />
                    Hãy tiếp tục tranh luận!
                  </p>
                ) : (
                  fallacies.map((f, i) => (
                    <FallacyCard
                      key={`${f.fallacy_type}-${i}`}
                      fallacy={f}
                      index={i}
                    />
                  ))
                )}
              </div>
            </div>
          </aside>

          {/* ── CENTER PANEL: Chat ──────────────────────────────────────────── */}
          <div className="flex-1 flex flex-col min-w-0">
            {/* Message area */}
            <div
              onScroll={(event) => {
                const node = event.currentTarget;
                shouldScrollRef.current =
                  node.scrollHeight - node.scrollTop - node.clientHeight < 120;
              }}
              className="flex-1 overflow-y-auto px-4 md:px-6 py-6 space-y-4"
            >
              <AnimatePresence initial={false}>
                {messages.length === 0 && (
                  <motion.div
                    key="empty"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="flex flex-col items-center justify-center h-full text-center py-20 text-muted-foreground"
                  >
                    <div className="p-4 rounded-2xl bg-brand-600/10 mb-4">
                      <MessageSquare className="h-8 w-8 text-brand-400" />
                    </div>
                    <p className="text-lg font-heading font-semibold text-foreground mb-2">
                      Đưa ra lập luận mở đầu của bạn
                    </p>
                    <p className="text-sm max-w-xs leading-relaxed">
                      Trình bày rõ lập trường của bạn. AI sẽ phản biện theo
                      phương pháp Socratic.
                    </p>
                    <p className="text-xs mt-4 text-muted-foreground/60">
                      Nhấn Ctrl+Enter để gửi
                    </p>
                  </motion.div>
                )}

                {messages.map((msg) => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, ease: "easeOut" }}
                    className={`flex ${
                      msg.role === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    <div className="max-w-[90%] sm:max-w-[78%] min-w-0 space-y-1.5">
                      {/* Speaker label */}
                      <div
                        className={`flex items-center gap-2 text-[11px] text-muted-foreground ${
                          msg.role === "user" ? "justify-end" : "justify-start"
                        }`}
                      >
                        <span className="font-medium">
                          {msg.role === "user" ? "Bạn" : "SocraticAI"}
                        </span>
                        {msg.hasContradiction && (
                          <span className="flex items-center gap-0.5 text-amber-400">
                            <Zap className="h-3 w-3" />
                            <span className="text-[10px]">Mâu thuẫn</span>
                          </span>
                        )}
                      </div>

                      {/* Bubble */}
                      <div
                        className={
                          msg.role === "user" ? "bubble-user" : "bubble-ai"
                        }
                      >
                        <p className="text-sm leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere]">
                          {msg.content}
                          {msg.isStreaming && (
                            <span className="inline-block w-1.5 h-4 bg-brand-400 ml-0.5 align-middle animate-pulse rounded-sm" />
                          )}
                        </p>
                      </div>
                    </div>
                  </motion.div>
                ))}

                {/* AI thinking indicator */}
                {isStreaming && !messages.some((m) => m.isStreaming) && (
                  <motion.div
                    key="thinking"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="flex justify-start"
                  >
                    <div className="bubble-ai flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        AI đang suy nghĩ
                      </span>
                      <span className="flex gap-1">
                        {[0, 1, 2].map((i) => (
                          <span
                            key={i}
                            className="h-1.5 w-1.5 rounded-full bg-brand-400 animate-bounce"
                            style={{ animationDelay: `${i * 150}ms` }}
                          />
                        ))}
                      </span>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
              <div ref={bottomRef} />
            </div>

            {contradictionAlerts.length > 0 && (
              <div role="status" className="px-4 py-2 text-xs text-amber-300">
                {contradictionAlerts[contradictionAlerts.length - 1]}
              </div>
            )}
            {/* ── Input bar ──────────────────────────────────────────────────── */}
            <div className="border-t border-socratic-border/50 bg-socratic-surface/50 backdrop-blur-sm px-4 py-3 shrink-0">
              <div className="flex items-end gap-3 max-w-3xl mx-auto">
                <div className="flex-1 relative">
                  <textarea
                    ref={inputRef}
                    aria-label="Lập luận của bạn"
                    id="debate-input"
                    value={inputValue}
                    onChange={(e) => {
                      if (e.target.value.length <= charLimit) {
                        setInputValue(e.target.value);
                      }
                    }}
                    onKeyDown={handleKeyDown}
                    placeholder="Trình bày lập luận của bạn… (Ctrl+Enter để gửi)"
                    rows={3}
                    disabled={inputDisabled}
                    className="w-full resize-none rounded-xl bg-socratic-surface-2/80 border border-socratic-border/60 px-4 py-3 pr-16 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500/60 disabled:opacity-40 transition-all"
                    maxLength={charLimit}
                  />
                  {/* Character counter */}
                  <span
                    className={`absolute bottom-2 right-3 text-[10px] font-mono ${
                      charCount > charLimit * 0.9
                        ? "text-danger"
                        : charCount > charLimit * 0.75
                          ? "text-warning"
                          : "text-muted-foreground/40"
                    }`}
                  >
                    {charCount}/{charLimit}
                  </span>
                </div>

                <button
                  id="send-turn-btn"
                  onClick={handleSend}
                  disabled={
                    !inputValue.trim() || inputDisabled || charCount > charLimit
                  }
                  className="shrink-0 h-12 w-12 rounded-xl bg-brand-600 text-white flex items-center justify-center hover:bg-brand-500 hover:shadow-lg hover:shadow-brand-600/25 disabled:opacity-30 disabled:cursor-not-allowed active:scale-95 transition-all duration-200"
                  aria-label="Gửi lập luận"
                >
                  <Send className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>

          {/* ── RIGHT PANEL: Claim Tracker ──────────────────────────────────── */}
          <aside className="hidden xl:flex flex-col w-[280px] shrink-0 border-l border-socratic-border/50 bg-socratic-surface/30">
            <div className="p-4 border-b border-socratic-border/30">
              <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                <FileText className="h-3.5 w-3.5" />
                Theo dõi luận điểm
                {claims.length > 0 && (
                  <span className="ml-auto text-[10px] bg-brand-600/15 text-brand-300 px-1.5 py-0.5 rounded-full">
                    {claims.length}
                  </span>
                )}
              </h2>
            </div>

            <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
              {claims.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-8 italic">
                  Các luận điểm sẽ xuất hiện tại đây trong quá trình tranh luận.
                </p>
              ) : (
                claims.map((claim, i) => (
                  <ClaimCard key={claim.claim_id} claim={claim} index={i} />
                ))
              )}
            </div>
          </aside>
        </div>

        {/* ── Mobile Fallacy/Claims Drawer (visible on smaller screens) ──── */}
        <div className="lg:hidden border-t border-socratic-border/50 bg-socratic-surface/80 backdrop-blur-sm">
          {fallacies.length > 0 && (
            <div className="px-4 py-2 flex items-center gap-2 overflow-x-auto">
              <Zap className="h-3.5 w-3.5 text-danger shrink-0" />
              {fallacies.slice(0, 3).map((f, i) => (
                <span
                  key={i}
                  className={`shrink-0 text-[11px] font-medium px-2 py-0.5 rounded-full border ${
                    f.severity === "major"
                      ? "severity-major"
                      : f.severity === "moderate"
                        ? "severity-moderate"
                        : "severity-minor"
                  }`}
                >
                  {f.fallacy_name_vi || f.fallacy_type}
                </span>
              ))}
              {fallacies.length > 3 && (
                <span className="text-[11px] text-muted-foreground shrink-0">
                  +{fallacies.length - 3} ngụy biện khác
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Score Modal */}
      {score && (
        <ScoreModal
          score={score}
          isOpen={showScoreModal}
          initialLanguage="vi"
          onClose={() => setShowScoreModal(false)}
        />
      )}
    </>
  );
}

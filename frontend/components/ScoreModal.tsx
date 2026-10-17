// frontend/components/ScoreModal.tsx
"use client";

import { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Trophy, TrendingUp, AlertCircle, Globe } from "lucide-react";
import type { SessionScore } from "@/lib/websocket";

interface ScoreModalProps {
  initialLanguage?: "en" | "vi";
  score: SessionScore;
  isOpen: boolean;
  onClose: () => void;
}

// ─── SVG Circular Progress Ring ─────────────────────────────────────────────

interface ProgressRingProps {
  value: number;
  maxValue: number;
  label: string;
  color: string;
  delay?: number;
}

function ProgressRing({
  value,
  maxValue,
  label,
  color,
  delay = 0,
}: ProgressRingProps) {
  const [animatedValue, setAnimatedValue] = useState(0);
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const progress = (animatedValue / maxValue) * circumference;
  const strokeDashoffset = circumference - progress;

  useEffect(() => {
    let animationFrame = 0;
    const timer = setTimeout(() => {
      const duration = 1200;
      const startTime = performance.now();

      const animate = (currentTime: number) => {
        const elapsed = currentTime - startTime;
        const fraction = Math.min(elapsed / duration, 1);
        // Ease out cubic
        const eased = 1 - Math.pow(1 - fraction, 3);
        setAnimatedValue(Math.round(eased * value));

        if (fraction < 1) {
          animationFrame = requestAnimationFrame(animate);
        }
      };

      animationFrame = requestAnimationFrame(animate);
    }, delay);

    return () => {
      clearTimeout(timer);
      cancelAnimationFrame(animationFrame);
    };
  }, [value, delay]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, delay: delay / 1000 }}
      className="flex flex-col items-center gap-2"
    >
      <div className="relative w-24 h-24">
        <svg className="w-24 h-24 -rotate-90" viewBox="0 0 96 96">
          {/* Background ring */}
          <circle
            cx="48"
            cy="48"
            r={radius}
            stroke="currentColor"
            strokeWidth="6"
            fill="none"
            className="text-socratic-surface-3"
          />
          {/* Progress ring */}
          <circle
            cx="48"
            cy="48"
            r={radius}
            stroke={color}
            strokeWidth="6"
            fill="none"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            style={{ transition: "stroke-dashoffset 0.1s ease-out" }}
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-bold text-foreground font-mono">
            {animatedValue}
          </span>
          <span className="text-[10px] text-muted-foreground">/{maxValue}</span>
        </div>
      </div>
      <span className="text-xs text-muted-foreground text-center leading-tight max-w-[90px]">
        {label}
      </span>
    </motion.div>
  );
}

// ─── Grade badge ─────────────────────────────────────────────────────────────

const GRADE_COLORS: Record<string, { bg: string; text: string; glow: string }> =
  {
    A: {
      bg: "bg-emerald-500/15",
      text: "text-emerald-400",
      glow: "shadow-emerald-500/25",
    },
    B: {
      bg: "bg-teal-500/15",
      text: "text-teal-400",
      glow: "shadow-teal-500/25",
    },
    C: {
      bg: "bg-yellow-500/15",
      text: "text-yellow-400",
      glow: "shadow-yellow-500/25",
    },
    D: {
      bg: "bg-orange-500/15",
      text: "text-orange-400",
      glow: "shadow-orange-500/25",
    },
    F: {
      bg: "bg-red-500/15",
      text: "text-red-400",
      glow: "shadow-red-500/25",
    },
  };

const RING_COLORS: Record<string, string> = {
  argument_depth: "#6366F1",
  logical_consistency: "#10B981",
  evidence_quality: "#F59E0B",
  rebuttal_effectiveness: "#EC4899",
};

// ─── ScoreModal ──────────────────────────────────────────────────────────────

export function ScoreModal({
  score,
  isOpen,
  onClose,
  initialLanguage = "vi",
}: ScoreModalProps) {
  const [language, setLanguage] = useState<"en" | "vi">(initialLanguage);
  const dialogRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!isOpen) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialogRef.current?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
      if (event.key === "Tab") {
        const elements = dialogRef.current?.querySelectorAll<HTMLElement>(
          'button, a[href], [tabindex="0"]',
        );
        if (!elements?.length) {
          event.preventDefault();
          return;
        }
        const first = elements[0],
          last = elements[elements.length - 1];
        if (
          event.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === dialogRef.current)
        ) {
          event.preventDefault();
          last.focus();
        }
        if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKey);
      previousFocus?.focus();
    };
  }, [isOpen, onClose]);
  const gradeStyle = GRADE_COLORS[score.grade] ?? GRADE_COLORS.C;

  const strengths = language === "en" ? score.strengths_en : score.strengths_vi;
  const improvements =
    language === "en" ? score.improvements_en : score.improvements_vi;
  const verdict = language === "en" ? score.verdict_en : score.verdict_vi;

  const dimensions = [
    {
      key: "argument_depth",
      label: language === "en" ? "Argument Depth" : "Độ sâu lập luận",
      value: score.argument_depth,
    },
    {
      key: "logical_consistency",
      label: language === "en" ? "Logical Consistency" : "Tính nhất quán logic",
      value: score.logical_consistency,
    },
    {
      key: "evidence_quality",
      label: language === "en" ? "Evidence Quality" : "Chất lượng bằng chứng",
      value: score.evidence_quality,
    },
    {
      key: "rebuttal_effectiveness",
      label:
        language === "en" ? "Rebuttal Effectiveness" : "Hiệu quả phản biện",
      value: score.rebuttal_effectiveness,
    },
  ];

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50"
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            onClick={(event) => {
              if (event.target === event.currentTarget) onClose();
            }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
            <div
              ref={dialogRef}
              role="dialog"
              aria-modal="true"
              aria-labelledby="score-title"
              tabIndex={-1}
              className="outline-none w-full max-w-xl max-h-[90vh] overflow-y-auto bg-socratic-surface border border-socratic-border rounded-2xl shadow-2xl"
            >
              {/* Header */}
              <div className="flex items-center justify-between p-6 pb-4 border-b border-socratic-border/50">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-brand-600/15">
                    <Trophy className="h-5 w-5 text-brand-400" />
                  </div>
                  <div>
                    <h2
                      id="score-title"
                      className="text-lg font-heading font-bold text-foreground"
                    >
                      {language === "en"
                        ? "Debate Results"
                        : "Kết Quả Tranh Luận"}
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      {language === "en"
                        ? "Your performance analysis"
                        : "Phân tích phần thể hiện của bạn"}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {/* Language toggle */}
                  <button
                    onClick={() =>
                      setLanguage((l) => (l === "en" ? "vi" : "en"))
                    }
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-socratic-surface-2 border border-socratic-border hover:border-brand-500/40 transition-colors"
                    title={
                      language === "en"
                        ? "Chuyển sang tiếng Việt"
                        : "Switch to English"
                    }
                  >
                    <Globe className="h-3.5 w-3.5" />
                    {language === "en" ? "EN" : "VI"}
                  </button>

                  <button
                    onClick={onClose}
                    className="p-1.5 rounded-lg hover:bg-socratic-surface-2 transition-colors"
                    aria-label={language === "en" ? "Close" : "Đóng"}
                  >
                    <X className="h-4 w-4 text-muted-foreground" />
                  </button>
                </div>
              </div>

              {/* Grade hero */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 }}
                className="flex flex-col items-center py-6 px-6"
              >
                <div
                  className={`w-20 h-20 rounded-2xl flex items-center justify-center text-4xl font-heading font-bold shadow-lg ${gradeStyle.bg} ${gradeStyle.text} ${gradeStyle.glow}`}
                >
                  {score.grade}
                </div>
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.4 }}
                  className="mt-3 text-2xl font-bold text-foreground font-mono"
                >
                  {score.total}
                  <span className="text-sm text-muted-foreground font-normal">
                    /100
                  </span>
                </motion.p>
                <p className="text-xs text-muted-foreground mt-1">
                  {score.fallacies_committed}{" "}
                  {language === "en" ? "fallacies" : "ngụy biện"} ·{" "}
                  {score.contradictions_caught}{" "}
                  {language === "en" ? "contradictions" : "mâu thuẫn"}
                </p>
              </motion.div>

              {/* Score dimensions — 4 progress rings */}
              <div className="px-6 pb-6">
                <div className="grid grid-cols-4 gap-4">
                  {dimensions.map((dim, i) => (
                    <ProgressRing
                      key={dim.key}
                      value={dim.value}
                      maxValue={25}
                      label={dim.label}
                      color={
                        RING_COLORS[dim.key as keyof typeof RING_COLORS] ??
                        "#6366F1"
                      }
                      delay={300 + i * 200}
                    />
                  ))}
                </div>
              </div>

              {/* Strengths & Improvements */}
              <div className="px-6 pb-6 space-y-4">
                {/* Strengths */}
                {strengths.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 1.1 }}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <TrendingUp className="h-4 w-4 text-success" />
                      <h3 className="text-sm font-semibold text-success">
                        {language === "en" ? "Strengths" : "Điểm mạnh"}
                      </h3>
                    </div>
                    <ul className="space-y-1.5">
                      {strengths.map((s, i) => (
                        <motion.li
                          key={i}
                          initial={{ opacity: 0, x: -8 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 1.2 + i * 0.1 }}
                          className="flex items-start gap-2 text-sm text-foreground/80"
                        >
                          <span className="text-success mt-0.5 shrink-0">
                            ✓
                          </span>
                          {s}
                        </motion.li>
                      ))}
                    </ul>
                  </motion.div>
                )}

                {/* Improvements */}
                {improvements.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 1.4 }}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <AlertCircle className="h-4 w-4 text-accent" />
                      <h3 className="text-sm font-semibold text-accent">
                        {language === "en"
                          ? "Areas for Improvement"
                          : "Cần cải thiện"}
                      </h3>
                    </div>
                    <ul className="space-y-1.5">
                      {improvements.map((s, i) => (
                        <motion.li
                          key={i}
                          initial={{ opacity: 0, x: -8 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 1.5 + i * 0.1 }}
                          className="flex items-start gap-2 text-sm text-foreground/80"
                        >
                          <span className="text-accent mt-0.5 shrink-0">→</span>
                          {s}
                        </motion.li>
                      ))}
                    </ul>
                  </motion.div>
                )}
              </div>

              {/* Verdict */}
              {verdict && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 1.8 }}
                  className="mx-6 mb-6 p-4 rounded-xl bg-socratic-surface-2/60 border border-socratic-border/40"
                >
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                    {language === "en" ? "Verdict" : "Nhận xét"}
                  </p>
                  <p className="text-sm text-foreground/90 leading-relaxed">
                    {verdict}
                  </p>
                </motion.div>
              )}

              <p className="mx-6 mb-4 text-xs leading-relaxed text-muted-foreground">
                {language === "en"
                  ? "This is an AI-generated practice assessment, not a verified grade. Review the feedback critically and ask a teacher to compare it when needed."
                  : "Đây là đánh giá luyện tập do AI tạo, chưa được giáo viên xác minh. Hãy xem phản hồi một cách chủ động và nhờ thầy cô đối chiếu khi cần."}
              </p>

              {/* Close button */}
              <div className="px-6 pb-6">
                <button
                  onClick={onClose}
                  className="w-full py-3 rounded-xl bg-brand-600 text-white font-semibold text-sm hover:bg-brand-500 transition-colors"
                >
                  {language === "en" ? "Close Results" : "Đóng kết quả"}
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

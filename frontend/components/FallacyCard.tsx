// frontend/components/FallacyCard.tsx
"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, AlertTriangle } from "lucide-react";
import type { FallacyResult, FallacySeverity } from "@/lib/websocket";

interface FallacyCardProps {
  fallacy: FallacyResult;
  index?: number;
}

const SEVERITY_CONFIG: Record<
  FallacySeverity,
  { label: string; className: string; dotColor: string }
> = {
  minor: {
    label: "Nhẹ",
    className: "severity-minor border",
    dotColor: "bg-yellow-400",
  },
  moderate: {
    label: "Vừa",
    className: "severity-moderate border",
    dotColor: "bg-orange-400",
  },
  major: {
    label: "Nghiêm trọng",
    className: "severity-major border",
    dotColor: "bg-red-400",
  },
};

export function FallacyCard({ fallacy, index = 0 }: FallacyCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const severity = SEVERITY_CONFIG[fallacy.severity];
  const primaryName = fallacy.fallacy_name_vi || fallacy.fallacy_type;
  const secondaryName = fallacy.fallacy_name_vi ? fallacy.fallacy_type : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -8, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className="rounded-xl border border-socratic-border bg-socratic-surface overflow-hidden"
    >
      {/* Header — always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-3 p-3 text-left hover:bg-socratic-surface-2/50 transition-colors"
        aria-expanded={isExpanded}
      >
        <AlertTriangle className="h-4 w-4 shrink-0 text-muted-foreground" />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-foreground">
              {primaryName}
            </span>
            {secondaryName && (
              <span className="text-xs text-muted-foreground">
                · {secondaryName}
              </span>
            )}
          </div>
          {/* Collapsed preview: offending excerpt */}
          {!isExpanded && (
            <p className="text-xs text-muted-foreground italic mt-1 truncate">
              &ldquo;{fallacy.offending_excerpt}&rdquo;
            </p>
          )}
        </div>

        <span
          className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${severity.className}`}
        >
          {severity.label}
        </span>

        <motion.div
          animate={{ rotate: isExpanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          className="shrink-0"
        >
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </motion.div>
      </button>

      {/* Expanded content */}
      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 space-y-3 border-t border-socratic-border/50">
              {/* Offending excerpt */}
              <div className="pt-3">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
                  Đoạn trích chứa ngụy biện
                </p>
                <p className="text-sm italic text-muted-foreground bg-socratic-surface-2/50 px-3 py-2 rounded-lg border border-socratic-border/30">
                  &ldquo;{fallacy.offending_excerpt}&rdquo;
                </p>
              </div>

              {/* Explanation */}
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
                  Tại sao đây là ngụy biện
                </p>
                <p className="text-sm text-foreground/90 leading-relaxed">
                  {fallacy.explanation}
                </p>
              </div>

              {/* Suggestion */}
              {fallacy.suggestion && (
                <div>
                  <p className="text-xs font-medium text-success uppercase tracking-wider mb-1">
                    Gợi ý khắc phục
                  </p>
                  <p className="text-sm text-foreground/80 leading-relaxed">
                    {fallacy.suggestion}
                  </p>
                </div>
              )}

              {/* Confidence */}
              <div className="flex items-center gap-2 pt-1">
                <span className="text-xs text-muted-foreground">
                  AI tự ước tính:
                </span>
                <div className="flex-1 h-1.5 bg-socratic-surface-3 rounded-full overflow-hidden max-w-[100px]">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${fallacy.confidence * 100}%` }}
                    transition={{ duration: 0.5, delay: 0.1 }}
                    className="h-full bg-brand-500 rounded-full"
                  />
                </div>
                <span className="text-xs text-muted-foreground font-mono">
                  {Math.round(fallacy.confidence * 100)}%
                </span>
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                Đây là gợi ý do AI tạo, không phải kết luận chắc chắn. Hãy tự
                đối chiếu với lập luận và trao đổi với thầy cô nếu chưa đồng ý.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

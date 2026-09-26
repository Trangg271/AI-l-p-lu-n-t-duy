// frontend/app/page.tsx
// Landing page — Hero + Topic Picker Grid → POST /session/create → redirect
"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createSession } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import {
  Brain,
  Atom,
  Coins,
  Globe2,
  Leaf,
  Rocket,
  Sparkles,
  Zap,
  Shield,
  BarChart3,
  ChevronDown,
} from "lucide-react";

// ─── Topic data ──────────────────────────────────────────────────────────────

type Difficulty = "beginner" | "advanced" | "expert";
type Stance = "pro" | "con";

interface TopicConfig {
  id: string;
  nameEn: string;
  nameVi: string;
  icon: React.ReactNode;
  difficulty: Difficulty;
  description: string;
  color: string;
}

const TOPICS: TopicConfig[] = [
  {
    id: "ai-ethics",
    nameEn: "AI Ethics",
    nameVi: "Đạo đức AI",
    icon: <Brain className="h-6 w-6" />,
    difficulty: "advanced",
    description:
      "Liệu các hệ thống AI có nên được trao quyền đạo đức? Khám phá những ranh giới đạo đức của trí tuệ nhân tạo.",
    color: "from-indigo-500/20 to-violet-500/10",
  },
  {
    id: "nuclear-energy",
    nameEn: "Nuclear Energy",
    nameVi: "Năng lượng hạt nhân",
    icon: <Atom className="h-6 w-6" />,
    difficulty: "advanced",
    description:
      "Năng lượng hạt nhân có thiết yếu cho tương lai bền vững, hay mang lại những rủi ro thảm họa không thể chấp nhận?",
    color: "from-emerald-500/20 to-teal-500/10",
  },
  {
    id: "universal-basic-income",
    nameEn: "Universal Basic Income",
    nameVi: "Thu nhập cơ bản toàn dân",
    icon: <Coins className="h-6 w-6" />,
    difficulty: "beginner",
    description:
      "Mọi công dân có nên nhận một mức thu nhập định kỳ được bảo đảm bất kể tình trạng việc làm của họ hay không?",
    color: "from-amber-500/20 to-yellow-500/10",
  },
  {
    id: "social-media-democracy",
    nameEn: "Social Media & Democracy",
    nameVi: "Mạng xã hội & Dân chủ",
    icon: <Globe2 className="h-6 w-6" />,
    difficulty: "beginner",
    description:
      "Mạng xã hội đang củng cố sự tham gia dân chủ hay phá hoại xã hội thông qua các thuật toán gây phân cực?",
    color: "from-blue-500/20 to-cyan-500/10",
  },
  {
    id: "veganism",
    nameEn: "Veganism",
    nameVi: "Chủ nghĩa thuần chay",
    icon: <Leaf className="h-6 w-6" />,
    difficulty: "beginner",
    description:
      "Ăn thuần chay là một mệnh lệnh đạo đức bắt buộc để bảo vệ hành tinh, hay chỉ là lựa chọn lối sống mang tính cá nhân?",
    color: "from-green-500/20 to-lime-500/10",
  },
  {
    id: "space-colonization",
    nameEn: "Space Colonization",
    nameVi: "Thuộc địa hóa vũ trụ",
    icon: <Rocket className="h-6 w-6" />,
    difficulty: "expert",
    description:
      "Nhân loại có nên đầu tư nguồn lực khổng lồ để định cư trên các hành tinh khác như một chính sách bảo hiểm sinh tồn?",
    color: "from-purple-500/20 to-pink-500/10",
  },
];

const DIFFICULTY_BADGES: Record<
  Difficulty,
  { label: string; className: string }
> = {
  beginner: {
    label: "Sơ cấp",
    className: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  },
  advanced: {
    label: "Nâng cao",
    className: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  },
  expert: {
    label: "Chuyên gia",
    className: "bg-red-500/15 text-red-400 border-red-500/30",
  },
};

const FEATURES = [
  {
    icon: <Sparkles className="h-5 w-5" />,
    title: "Phương pháp Socratic",
    desc: "AI dẫn dắt bằng các câu hỏi phản biện sâu sắc — không bao giờ mớm sẵn câu trả lời.",
  },
  {
    icon: <Shield className="h-5 w-5" />,
    title: "Kỹ thuật Steelmanning",
    desc: "Lập luận của bạn được củng cố phiên bản mạnh nhất trước khi đối phương phản biện.",
  },
  {
    icon: <Zap className="h-5 w-5" />,
    title: "Phát hiện ngụy biện",
    desc: "Quét và phân tích ngụy biện logic theo thời gian thực cùng mô hình Gemini.",
  },
  {
    icon: <BarChart3 className="h-5 w-5" />,
    title: "Bảng điểm Rubric",
    desc: "Đánh giá chi tiết 4 chiều kỹ năng sau mỗi phiên tranh luận.",
  },
] as const;

// ─── Topic Card Component ────────────────────────────────────────────────────

interface TopicCardProps {
  topic: TopicConfig;
  index: number;
  onStart: (topic: TopicConfig, stance: Stance) => void;
  isSubmitting: boolean;
}

function TopicCard({ topic, index, onStart, isSubmitting }: TopicCardProps) {
  const [stance, setStance] = useState<Stance>("pro");
  const [isStanceOpen, setIsStanceOpen] = useState(false);
  const badge = DIFFICULTY_BADGES[topic.difficulty];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 + index * 0.08 }}
      className="topic-card group flex flex-col p-5 relative overflow-hidden"
    >
      {/* Gradient accent bg */}
      <div
        className={`absolute inset-0 bg-gradient-to-br ${topic.color} opacity-0 group-hover:opacity-100 transition-opacity duration-500`}
      />

      <div className="relative z-10 flex flex-col h-full">
        {/* Icon + Badge row */}
        <div className="flex items-start justify-between mb-3">
          <div className="p-2.5 rounded-xl bg-socratic-surface-2 border border-socratic-border/50 text-brand-400 group-hover:text-brand-300 transition-colors">
            {topic.icon}
          </div>
          <span
            className={`text-[11px] font-medium px-2 py-0.5 rounded-full border ${badge.className}`}
          >
            {badge.label}
          </span>
        </div>

        {/* Topic names */}
        <h3 className="text-base font-heading font-bold text-foreground mb-0.5 leading-tight">
          {topic.nameVi}
        </h3>
        <p className="text-xs text-muted-foreground mb-2">{topic.nameEn}</p>

        {/* Description */}
        <p className="text-xs text-muted-foreground leading-relaxed mb-4 flex-1">
          {topic.description}
        </p>

        {/* Position selector + Start button */}
        <div className="flex items-center gap-2">
          {/* Stance dropdown */}
          <div className="relative flex-1">
            <button
              onClick={() => setIsStanceOpen(!isStanceOpen)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm bg-socratic-surface-2 border border-socratic-border/60 text-foreground hover:border-brand-500/40 transition-colors"
              aria-haspopup="listbox"
              aria-expanded={isStanceOpen}
            >
              <span>
                {stance === "pro" ? "🟢 Ủng hộ (Pro)" : "🔴 Phản đối (Con)"}
              </span>
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            </button>

            <AnimatePresence>
              {isStanceOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                  className="absolute bottom-full mb-1 left-0 right-0 bg-socratic-surface-2 border border-socratic-border rounded-lg overflow-hidden shadow-xl z-20"
                >
                  <button
                    onClick={() => {
                      setStance("pro");
                      setIsStanceOpen(false);
                    }}
                    className={`w-full px-3 py-2 text-left text-sm hover:bg-socratic-surface-3/50 transition-colors ${
                      stance === "pro"
                        ? "text-emerald-400 bg-emerald-500/10"
                        : "text-foreground"
                    }`}
                  >
                    🟢 Tranh luận ủng hộ (Pro)
                  </button>
                  <button
                    onClick={() => {
                      setStance("con");
                      setIsStanceOpen(false);
                    }}
                    className={`w-full px-3 py-2 text-left text-sm hover:bg-socratic-surface-3/50 transition-colors ${
                      stance === "con"
                        ? "text-red-400 bg-red-500/10"
                        : "text-foreground"
                    }`}
                  >
                    🔴 Tranh luận phản đối (Con)
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Start Debate button */}
          <button
            onClick={() => onStart(topic, stance)}
            disabled={isSubmitting}
            className="shrink-0 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold hover:bg-brand-500 hover:shadow-lg hover:shadow-brand-600/25 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
          >
            {isSubmitting ? (
              <span className="flex items-center gap-1.5">
                <svg
                  className="animate-spin h-3.5 w-3.5"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v8H4z"
                  />
                </svg>
                …
              </span>
            ) : (
              "Bắt đầu →"
            )}
          </button>
        </div>
      </div>
    </motion.div>
  );
}

// ─── Landing Page ────────────────────────────────────────────────────────────

export default function HomePage() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const handleStartDebate = (topic: TopicConfig, stance: Stance) => {
    if (isPending) return;
    setError(null);

    startTransition(async () => {
      try {
        const session = await createSession({
          topic: `${topic.nameVi} (${topic.nameEn})`,
          topic_description: topic.description,
          language: "vi",
          user_position: stance,
          difficulty: topic.difficulty,
        });
        router.push(`/debate/${session.session_id}`);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Không thể tạo phiên tranh luận",
        );
      }
    });
  };

  return (
    <main className="min-h-screen flex flex-col animated-gradient-bg">
      {/* ── Nav ───────────────────────────────────────────────────────────── */}
      <nav className="fixed top-0 inset-x-0 z-50 glass-strong border-b border-socratic-border/50">
        <div className="container mx-auto flex items-center justify-between h-16 px-4">
          <span className="text-xl font-heading font-bold gradient-text tracking-tight">
            SocraticAI
          </span>
          <div className="flex items-center gap-3">
            <span className="text-[11px] text-muted-foreground px-2.5 py-1 rounded-full border border-socratic-border/50 bg-socratic-surface/50">
              Bản thử nghiệm
            </span>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              Gemini 2.5
            </div>
          </div>
        </div>
      </nav>

      {/* ── Hero Section ──────────────────────────────────────────────────── */}
      <section className="relative flex flex-col items-center justify-center px-4 pt-36 pb-16 text-center overflow-hidden">
        {/* Glow orbs */}
        <div
          aria-hidden
          className="absolute -top-40 -left-40 w-[500px] h-[500px] rounded-full bg-brand-600/12 blur-[120px] pointer-events-none"
        />
        <div
          aria-hidden
          className="absolute -bottom-40 -right-40 w-[400px] h-[400px] rounded-full bg-accent/8 blur-[100px] pointer-events-none"
        />
        <div
          aria-hidden
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-brand-800/6 blur-[140px] pointer-events-none"
        />

        <div className="relative z-10 max-w-4xl mx-auto space-y-6">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass text-sm text-muted-foreground border border-socratic-border/50"
          >
            <Sparkles className="h-4 w-4 text-accent" />
            Luyện tập tranh luận cùng AI
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-5xl md:text-7xl font-heading font-bold tracking-tight leading-[1.1]"
          >
            Rèn Luyện Tư Duy.
            <br />
            <span className="gradient-text">Làm Chủ Mọi Tranh Biện.</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="text-lg md:text-xl text-muted-foreground italic font-heading"
          >
            Nâng tầm tư duy phản biện cùng SocraticAI
          </motion.p>

          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="text-base text-muted-foreground max-w-2xl mx-auto leading-relaxed"
          >
            Đối đầu trực tiếp với AI tranh biện ứng dụng phương pháp Socratic, nhận diện
            ngụy biện logic theo thời gian thực và nhận đánh giá chi tiết theo bảng điểm rubric chuẩn mực
            — hoàn toàn bằng <strong className="text-foreground">Tiếng Việt</strong>.
          </motion.p>

          {/* Mini feature pills */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="flex flex-wrap justify-center gap-3 pt-2"
          >
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="flex items-center gap-2 px-3 py-1.5 rounded-full glass text-xs text-muted-foreground border border-socratic-border/40"
              >
                <span className="text-brand-400">{f.icon}</span>
                <span>{f.title}</span>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ── Topic Picker ──────────────────────────────────────────────────── */}
      <section className="relative z-10 px-4 pb-16">
        <div className="container mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.5 }}
            className="text-center mb-10"
          >
            <h2 className="text-2xl md:text-3xl font-heading font-bold text-foreground mb-2">
              Chọn Đề Tài{" "}
              <span className="gradient-text-accent">Tranh Biện</span>
            </h2>
            <p className="text-sm text-muted-foreground">
              Chọn một chủ đề, xác định lập trường của bạn và bắt đầu tranh luận.
            </p>
          </motion.div>

          {/* Error alert */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm mb-6 max-w-xl mx-auto"
              >
                <span>⚠️</span>
                <span>{error}</span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Topic grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {TOPICS.map((topic, index) => (
              <TopicCard
                key={topic.id}
                topic={topic}
                index={index}
                onStart={handleStartDebate}
                isSubmitting={isPending}
              />
            ))}
          </div>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────────────────── */}
      <footer className="relative z-10 border-t border-socratic-border/30 py-8 px-4 text-center">
        <p className="text-xs text-muted-foreground">
          SocraticAI · Được xây dựng với Next.js 15, FastAPI, LangGraph &amp; Gemini ·
          Tranh luận văn minh
        </p>
      </footer>
    </main>
  );
}

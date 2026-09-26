// frontend/app/debate/new/page.tsx
// Setup form — collects topic, stance, language, then creates a session and redirects
"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createSession } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";

type Stance = "pro" | "con";
type Language = "en" | "vi";

const EXAMPLE_TOPICS: Record<Language, string[]> = {
  en: [
    "Artificial intelligence will create more jobs than it destroys",
    "Social media does more harm than good to democracy",
    "Universal basic income should be implemented globally",
    "Nuclear energy is essential for a sustainable future",
  ],
  vi: [
    "Trí tuệ nhân tạo sẽ tạo ra nhiều việc làm hơn nó phá hủy",
    "Mạng xã hội gây hại nhiều hơn lợi cho xã hội",
    "Thu nhập cơ bản phổ quát nên được áp dụng toàn cầu",
    "Năng lượng hạt nhân là thiết yếu cho tương lai bền vững",
  ],
};

export default function NewDebatePage() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const [topic, setTopic] = useState("");
  const [stance, setStance] = useState<Stance>("pro");
  const [language, setLanguage] = useState<Language>("vi");
  const [error, setError] = useState<string | null>(null);

  const canProceedStep1 = topic.trim().length >= 10;
  const isSubmitting = isPending;

  const handleExampleClick = (t: string) => {
    setTopic(t);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting || !canProceedStep1) return;
    setError(null);

    startTransition(async () => {
      try {
        const session = await createSession({
          topic: topic.trim(),
          language,
          user_position: stance,
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
    <main className="min-h-screen flex flex-col items-center justify-center px-4 py-16 relative overflow-hidden">
      {/* Background glows */}
      <div
        aria-hidden
        className="absolute -top-60 -left-60 w-[500px] h-[500px] rounded-full bg-brand-600/15 blur-3xl pointer-events-none"
      />
      <div
        aria-hidden
        className="absolute -bottom-60 -right-60 w-[500px] h-[500px] rounded-full bg-accent/15 blur-3xl pointer-events-none"
      />

      {/* Back link */}
      <motion.a
        href="/"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-10 text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center gap-2 group"
      >
        <span className="group-hover:-translate-x-0.5 transition-transform">
          ←
        </span>
        Quay lại trang chủ
      </motion.a>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-2xl"
      >
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold tracking-tight mb-3">
            Thiết lập phiên <span className="gradient-text">tranh luận</span>
          </h1>
          <p className="text-muted-foreground">
            Chọn chủ đề và xác định lập trường của bạn. AI sẽ tranh luận ở phe đối lập.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Step 1 — Topic */}
          <motion.div
            className="glass rounded-2xl p-6 space-y-4"
            animate={{ opacity: 1 }}
          >
            <div className="flex items-center gap-3 mb-1">
              <span className="flex h-7 w-7 rounded-full bg-primary/20 text-primary text-sm font-bold items-center justify-center border border-primary/30">
                1
              </span>
              <h2 className="font-semibold text-foreground">Chủ đề tranh luận</h2>
            </div>

            <textarea
              aria-label="Chủ đề tranh luận"
              disabled={isSubmitting}
              id="topic-input"
              value={topic}
              onChange={(e) => {
                setTopic(e.target.value);
              }}
              placeholder="Ví dụ: Trí tuệ nhân tạo sẽ tạo ra nhiều việc làm hơn nó phá hủy..."
              rows={3}
              className="w-full bg-background/50 border border-border/60 rounded-xl px-4 py-3 text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary/60 transition-all"
              minLength={10}
              maxLength={500}
              required
            />

            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Tối thiểu 10 ký tự</span>
              <span className={topic.length > 450 ? "text-yellow-400" : ""}>
                {topic.length}/500
              </span>
            </div>

            {/* Example topics */}
            <div>
              <p className="text-xs text-muted-foreground mb-2">
                Hoặc chọn đề tài gợi ý (
                {language === "en" ? "Tiếng Anh" : "Tiếng Việt"}):
              </p>
              <div className="flex gap-2 flex-wrap">
                {EXAMPLE_TOPICS[language].map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => handleExampleClick(t)}
                    className="text-xs px-3 py-1.5 rounded-full glass border border-border/50 text-muted-foreground hover:text-foreground hover:border-primary/40 transition-all"
                  >
                    {t.length > 50 ? t.slice(0, 50) + "…" : t}
                  </button>
                ))}
              </div>
            </div>
          </motion.div>

          {/* Steps 2 & 3 — revealed once topic is valid */}
          <AnimatePresence>
            {canProceedStep1 && (
              <motion.div
                key="step2-3"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 16 }}
                transition={{ duration: 0.3 }}
                className="space-y-6"
              >
                {/* Step 2 — Language */}
                <div className="glass rounded-2xl p-6 space-y-4">
                  <div className="flex items-center gap-3 mb-1">
                    <span className="flex h-7 w-7 rounded-full bg-primary/20 text-primary text-sm font-bold items-center justify-center border border-primary/30">
                      2
                    </span>
                    <h2 className="font-semibold text-foreground">Ngôn ngữ</h2>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    {(["vi", "en"] as Language[]).map((lang) => (
                      <button
                        key={lang}
                        type="button"
                        aria-pressed={language === lang}
                        disabled={isSubmitting}
                        id={`lang-${lang}`}
                        onClick={() => {
                          setLanguage(lang);
                        }}
                        className={`px-4 py-3 rounded-xl border font-medium text-sm transition-all ${
                          language === lang
                            ? "bg-primary/20 border-primary text-primary shadow-sm shadow-primary/20"
                            : "glass border-border/50 text-muted-foreground hover:border-primary/40 hover:text-foreground"
                        }`}
                      >
                        {lang === "vi" ? "🇻🇳  Tiếng Việt" : "🇬🇧  English"}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Step 3 — Stance */}
                <div className="glass rounded-2xl p-6 space-y-4">
                  <div className="flex items-center gap-3 mb-1">
                    <span className="flex h-7 w-7 rounded-full bg-primary/20 text-primary text-sm font-bold items-center justify-center border border-primary/30">
                      3
                    </span>
                    <h2 className="font-semibold text-foreground">
                      Lập trường của bạn
                    </h2>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      aria-pressed={stance === "pro"}
                      disabled={isSubmitting}
                      id="stance-pro"
                      onClick={() => setStance("pro")}
                      className={`px-4 py-4 rounded-xl border font-medium text-sm transition-all flex flex-col items-center gap-1 ${
                        stance === "pro"
                          ? "bg-green-500/20 border-green-500 text-green-400 shadow-sm shadow-green-500/20"
                          : "glass border-border/50 text-muted-foreground hover:border-green-500/40 hover:text-green-300"
                      }`}
                    >
                      <span className="text-xl">✅</span>
                      <span>Tôi đồng tình</span>
                      <span className="text-xs opacity-70">
                        Tranh luận ủng hộ (Pro)
                      </span>
                    </button>
                    <button
                      type="button"
                      aria-pressed={stance === "con"}
                      disabled={isSubmitting}
                      id="stance-con"
                      onClick={() => setStance("con")}
                      className={`px-4 py-4 rounded-xl border font-medium text-sm transition-all flex flex-col items-center gap-1 ${
                        stance === "con"
                          ? "bg-red-500/20 border-red-500 text-red-400 shadow-sm shadow-red-500/20"
                          : "glass border-border/50 text-muted-foreground hover:border-red-500/40 hover:text-red-300"
                      }`}
                    >
                      <span className="text-xl">❌</span>
                      <span>Tôi phản đối</span>
                      <span className="text-xs opacity-70">
                        Tranh luận phản đối (Con)
                      </span>
                    </button>
                  </div>
                </div>

                {/* Error */}
                <AnimatePresence>
                  {error && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm"
                    >
                      <span>⚠️</span>
                      <span>{error}</span>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Submit */}
                <button
                  type="submit"
                  id="start-session-btn"
                  disabled={isSubmitting}
                  className="w-full py-4 rounded-xl bg-primary text-primary-foreground font-bold text-base hover:bg-primary/90 hover:scale-[1.02] hover:shadow-lg hover:shadow-primary/25 active:scale-100 transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed disabled:scale-100 disabled:shadow-none animate-pulse-glow"
                >
                  {isSubmitting ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg
                        className="animate-spin h-4 w-4"
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
                      Đang tạo phiên…
                    </span>
                  ) : (
                    "Bắt đầu tranh luận →"
                  )}
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </form>
      </motion.div>
    </main>
  );
}

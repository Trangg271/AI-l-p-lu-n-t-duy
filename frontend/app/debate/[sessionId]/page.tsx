// frontend/app/debate/[sessionId]/page.tsx
// Live debate arena page — streams AI responses via WebSocket

import type { Metadata } from "next";
import { DebateArena } from "@/components/debate/DebateArena";

interface DebatePageProps {
  params: Promise<{ sessionId: string }>;
  searchParams: Promise<{ history?: string }>;
}

export async function generateMetadata({
  params,
}: DebatePageProps): Promise<Metadata> {
  const { sessionId } = await params;
  return {
    title: `Debate ${sessionId.slice(0, 8)} — SocraticAI`,
    description: "Live AI-powered debate training session",
    robots: { index: false, follow: false },
  };
}

export default async function DebatePage({
  params,
  searchParams,
}: DebatePageProps) {
  const [{ sessionId }, query] = await Promise.all([params, searchParams]);

  return (
    <main className="min-h-screen flex flex-col">
      <DebateArena
        sessionId={sessionId}
        historyWarning={query.history === "unavailable"}
      />
    </main>
  );
}

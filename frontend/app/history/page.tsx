"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  BarChart3,
  Clock3,
  LoaderCircle,
  Trophy,
} from "lucide-react";
import { getSessionHistory, type SessionHistoryEntry } from "@/lib/api";
import { forgetSessions, readSessionHistory } from "@/lib/session-history";

function weekStart(date: Date): Date {
  const monday = new Date(date);
  monday.setHours(0, 0, 0, 0);
  monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7));
  return monday;
}

function dateKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

export default function HistoryPage() {
  const [sessions, setSessions] = useState<SessionHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expiredCount, setExpiredCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      try {
        const ids = readSessionHistory();
        if (ids.length === 0) {
          setSessions([]);
          return;
        }
        const history = await getSessionHistory(ids);
        if (cancelled) return;

        if (history.missing_session_ids.length) {
          forgetSessions(history.missing_session_ids);
          setExpiredCount(history.missing_session_ids.length);
        }
        setSessions(history.sessions);
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Không thể đọc lịch sử luyện tập.",
          );
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void loadHistory();
    return () => {
      cancelled = true;
    };
  }, []);

  const weeklyScores = useMemo(() => {
    const currentWeek = weekStart(new Date());
    return Array.from({ length: 8 }, (_, index) => {
      const start = new Date(currentWeek);
      start.setDate(start.getDate() - (7 - index) * 7);
      const key = dateKey(start);
      const scores = sessions
        .filter(
          (session) =>
            session.grade &&
            dateKey(
              weekStart(new Date(session.ended_at || session.created_at)),
            ) === key,
        )
        .map((session) => session.grade!.total);
      return {
        key,
        label: start.toLocaleDateString("vi-VN", {
          day: "numeric",
          month: "numeric",
        }),
        average: scores.length
          ? Math.round(
              scores.reduce((sum, score) => sum + score, 0) / scores.length,
            )
          : null,
        count: scores.length,
      };
    });
  }, [sessions]);

  const gradedSessions = sessions.filter((session) => session.grade);
  const averageScore = gradedSessions.length
    ? Math.round(
        gradedSessions.reduce(
          (sum, session) => sum + (session.grade?.total ?? 0),
          0,
        ) / gradedSessions.length,
      )
    : null;

  return (
    <main className="min-h-screen bg-socratic-bg px-4 py-10 text-foreground">
      <div className="mx-auto max-w-4xl space-y-8">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Trang chủ
        </Link>

        <header>
          <p className="text-sm font-semibold uppercase tracking-widest text-brand-400">
            Tiến độ cá nhân
          </p>
          <h1 className="mt-2 text-3xl font-bold">Lịch sử luyện tập</h1>
          <p className="mt-2 text-muted-foreground">
            Theo dõi điểm rubric qua từng tuần để thấy kỹ năng tranh biện thay
            đổi theo thời gian.
          </p>
        </header>

        {error && (
          <div
            role="alert"
            className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300"
          >
            {error}
          </div>
        )}
        {expiredCount > 0 && (
          <p className="text-sm text-muted-foreground">
            Đã bỏ {expiredCount} phiên hết hạn khỏi lịch sử trên thiết bị này.
          </p>
        )}

        {isLoading ? (
          <div className="flex items-center gap-2 py-12 text-muted-foreground">
            <LoaderCircle className="h-5 w-5 animate-spin" />
            Đang tải lịch sử…
          </div>
        ) : (
          <>
            <section className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-socratic-border/60 bg-socratic-surface p-5">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Trophy className="h-4 w-4 text-amber-400" />
                  Phiên đã chấm điểm
                </div>
                <p className="mt-3 text-3xl font-bold">
                  {gradedSessions.length}
                </p>
              </div>
              <div className="rounded-2xl border border-socratic-border/60 bg-socratic-surface p-5">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <BarChart3 className="h-4 w-4 text-emerald-400" />
                  Điểm trung bình
                </div>
                <p className="mt-3 text-3xl font-bold">
                  {averageScore === null ? "—" : `${averageScore}/100`}
                </p>
              </div>
            </section>

            <section className="rounded-2xl border border-socratic-border/60 bg-socratic-surface p-5 sm:p-6">
              <h2 className="font-semibold">Điểm trung bình theo tuần</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Tối đa 8 tuần gần nhất; tuần chưa có phiên đã chấm sẽ để trống.
              </p>
              <div className="mt-6 grid grid-cols-4 gap-3 sm:grid-cols-8">
                {weeklyScores.map((week) => (
                  <div
                    key={week.key}
                    className="flex flex-col items-center gap-2"
                  >
                    <span className="text-xs font-medium">
                      {week.average === null ? "—" : week.average}
                    </span>
                    <div
                      className="flex h-32 w-full items-end overflow-hidden rounded-lg bg-socratic-surface-2"
                      title={`${week.count} phiên`}
                    >
                      {week.average !== null && (
                        <div
                          className="w-full rounded-t-md bg-brand-500 transition-[height]"
                          style={{ height: `${week.average}%` }}
                          aria-label={`Điểm trung bình tuần bắt đầu ${week.label}: ${week.average}`}
                        />
                      )}
                    </div>
                    <span className="text-[10px] text-muted-foreground">
                      {week.label}
                    </span>
                  </div>
                ))}
              </div>
            </section>

            <section className="space-y-3">
              <h2 className="font-semibold">Các phiên gần đây</h2>
              {sessions.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-socratic-border p-8 text-center">
                  <Clock3 className="mx-auto h-8 w-8 text-muted-foreground" />
                  <p className="mt-3 font-medium">Chưa có lịch sử luyện tập</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Các phiên mới trên thiết bị này sẽ xuất hiện tại đây.
                  </p>
                  <Link
                    href="/debate/new"
                    className="mt-5 inline-flex rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
                  >
                    Bắt đầu tranh luận
                  </Link>
                </div>
              ) : (
                sessions.map((session) => (
                  <Link
                    key={session.session_id}
                    href={`/debate/${session.session_id}`}
                    className="flex flex-col gap-3 rounded-xl border border-socratic-border/60 bg-socratic-surface p-4 transition-colors hover:border-brand-500/50 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium">{session.topic}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {new Date(session.created_at).toLocaleString("vi-VN")} ·{" "}
                        {session.turn_count} lượt ·{" "}
                        {session.user_position === "pro"
                          ? "Ủng hộ"
                          : "Phản đối"}
                      </p>
                    </div>
                    <span className="shrink-0 text-sm font-semibold">
                      {session.grade
                        ? `${session.grade.total}/100 · ${session.grade.grade}`
                        : session.status === "active"
                          ? "Đang diễn ra"
                          : "Chưa có điểm"}
                    </span>
                  </Link>
                ))
              )}
            </section>
          </>
        )}
        <p className="text-xs text-muted-foreground">
          Lịch sử được lưu trên trình duyệt này; dữ liệu phiên trên máy chủ tự
          hết hạn sau 90 ngày.
        </p>
      </div>
    </main>
  );
}

const STORAGE_KEY = "socratic-ai-session-history";
const MAX_HISTORY_ITEMS = 100;

export function readSessionHistory(): string[] {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === null) return [];

  const parsed: unknown = JSON.parse(stored);
  if (
    !Array.isArray(parsed) ||
    !parsed.every((id): id is string => typeof id === "string")
  ) {
    throw new Error("Dữ liệu lịch sử luyện tập trên trình duyệt không hợp lệ.");
  }
  return parsed;
}

export function rememberSession(sessionId: string): void {
  const history = readSessionHistory().filter((id) => id !== sessionId);
  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify([sessionId, ...history].slice(0, MAX_HISTORY_ITEMS)),
  );
}

export function forgetSessions(sessionIds: string[]): void {
  const expired = new Set(sessionIds);
  const history = readSessionHistory().filter((id) => !expired.has(id));
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
}

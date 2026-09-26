import { test, expect, type Page, type WebSocketRoute } from "@playwright/test";
import type { SessionSnapshot, SessionScore } from "../lib/websocket";

const sessionId = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa";
const snapshot = (): SessionSnapshot => ({
  turns: [],
  extracted_claims: [],
  fallacy_analysis: [],
  contradiction_alerts: [],
  session_score: null,
  status: "active",
  turn_count: 0,
  max_turns: 20,
  config: {
    topic: "Nuclear energy is essential for a sustainable future",
    topic_description: "",
    language: "vi",
    difficulty: "beginner",
    user_position: "con",
    ai_position: "pro",
  },
});
const score: SessionScore = {
  argument_depth: 20,
  logical_consistency: 21,
  evidence_quality: 19,
  rebuttal_effectiveness: 22,
  total: 82,
  grade: "B",
  fallacies_committed: 0,
  contradictions_caught: 0,
  strengths_en: ["Clear reasoning"],
  strengths_vi: ["Lập luận rõ ràng"],
  improvements_en: ["Add evidence"],
  improvements_vi: ["Bổ sung bằng chứng"],
  verdict_en: "Well argued.",
  verdict_vi: "Lập luận tốt.",
};

async function mockSession(
  page: Page,
  options: { fail?: boolean; completed?: boolean } = {},
) {
  const state = snapshot();
  if (options.completed) {
    state.status = "graded";
    state.session_score = score;
  }
  let socket: WebSocketRoute;
  const requests: {
    type: string;
    data: { content?: string; language?: string };
  }[] = [];
  await page.routeWebSocket(`**/ws/debate/${sessionId}`, (ws) => {
    socket = ws;
    ws.send(JSON.stringify({ type: "sync", data: state }));
    if (options.completed) {
      setTimeout(() => ws.close({ code: 1000 }), 100);
      return;
    }
    ws.onMessage((raw) => {
      const message = JSON.parse(String(raw));
      requests.push(message);
      if (message.type === "user_message") {
        if (options.fail) {
          ws.send(
            JSON.stringify({
              type: "error",
              data: "Unable to complete this turn. Please try again.",
            }),
          );
          ws.send(JSON.stringify({ type: "sync", data: state }));
          return;
        }
        const index = state.turns.length;
        state.turns.push({
          turn_number: index,
          speaker: "user",
          content: message.data.content,
          timestamp: new Date().toISOString(),
        });
        ws.send(JSON.stringify({ type: "token", data: "Xin chào. " }));
        ws.send(
          JSON.stringify({ type: "token", data: "Bạn có bằng chứng nào?" }),
        );
        setTimeout(() => {
          state.turns.push({
            turn_number: index + 1,
            speaker: "ai",
            content: "Xin chào. Bạn có bằng chứng nào?",
            timestamp: new Date().toISOString(),
          });
          state.turn_count += 1;
          state.extracted_claims.push({
            claim_id: `claim-${index}`,
            session_id: sessionId,
            turn_number: index,
            speaker: "user",
            claim_text: "Nuclear energy has low emissions.",
            claim_type: "assertion",
            key_entities: [],
          });
          ws.send(JSON.stringify({ type: "turn_done", data: state }));
        }, 150);
      } else if (message.type === "end_session") {
        ws.send(JSON.stringify({ type: "grading", data: {} }));
        setTimeout(() => {
          state.status = "graded";
          state.session_score = score;
          ws.send(JSON.stringify({ type: "score", data: score }));
          ws.send(
            JSON.stringify({
              type: "session_ended",
              data: { status: "graded" },
            }),
          );
          ws.close({ code: 1000 });
        }, 100);
      }
    });
  });
  return { state, requests, disconnect: () => socket.close({ code: 1011 }) };
}

test("custom form preserves con stance and Vietnamese language", async ({
  page,
}) => {
  let payload: Record<string, unknown> = {};
  await mockSession(page);
  await page.route("**/session/create", async (route) => {
    payload = route.request().postDataJSON();
    await route.fulfill({ status: 201, json: { session_id: sessionId } });
  });
  await page.goto("/debate/new");
  await page
    .getByLabel("Debate topic")
    .fill("Nuclear energy is essential for our future");
  await page.locator("#lang-vi").click();
  await page.locator("#stance-con").click();
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(new RegExp(sessionId));
  expect(payload).toMatchObject({ language: "vi", user_position: "con" });
  await expect(page.getByLabel("Your argument")).toBeEnabled();
});

test("streams complete turns, updates claims, restores reload, and reopens score", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const mock = await mockSession(page);
  await page.goto(`/debate/${sessionId}`);
  const input = page.getByLabel("Your argument");
  await expect(input).toBeEnabled();
  await input.fill("Nuclear energy has low emissions.");
  await page.getByRole("button", { name: "Send argument" }).click();
  await expect(
    page.getByText("Xin chào. Bạn có bằng chứng nào?", { exact: true }),
  ).toHaveCount(1);
  await expect(input).toBeEnabled();
  expect(
    mock.requests.find((request) => request.type === "user_message")?.data
      .language,
  ).toBe("vi");
  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: /Analysis/ }).click();
    await expect(page.locator("#mobile-analysis")).toContainText(
      "Nuclear energy has low emissions.",
    );
    await page.getByRole("button", { name: "Close analysis" }).click();
  }
  await page.reload();
  await expect(
    page.getByText("Xin chào. Bạn có bằng chứng nào?", { exact: true }),
  ).toHaveCount(1);
  await expect(input).toBeEnabled();
  await page.getByRole("button", { name: "End & Score", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText("Lập luận tốt.");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(input).toBeDisabled();
  await page.getByRole("button", { name: "View results" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({path: testInfo.outputPath("score.png"), fullPage: true});
  expect(errors).toEqual([]);
});

test("provider failure displays an error and unlocks input", async ({
  page,
}) => {
  await mockSession(page, { fail: true });
  await page.goto(`/debate/${sessionId}`);
  const input = page.getByLabel("Your argument");
  await expect(input).toBeEnabled();
  await input.fill("A test argument");
  await page.getByRole("button", { name: "Send argument" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Unable to complete" }),
  ).toContainText("Unable to complete");
  await expect(input).toBeEnabled();
  await expect(input).toHaveValue("A test argument");
});

test("completed session restores results and prevents more messages", async ({
  page,
}) => {
  await mockSession(page, { completed: true });
  await page.goto(`/debate/${sessionId}`);
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await expect(page.getByLabel("Your argument")).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "View results" }),
  ).toBeVisible();
});

test("backend validation messages are readable", async ({ page }) => {
  await page.route("**/session/create", (route) =>
    route.fulfill({
      status: 422,
      json: { detail: [{ msg: "Topic is invalid" }] },
    }),
  );
  await page.goto("/debate/new");
  await page.getByLabel("Debate topic").fill("A valid length topic");
  await page.locator('button[type="submit"]').click();
  await expect(
    page.getByText("Topic is invalid", { exact: true }),
  ).toBeVisible();
  await expect(page.locator('button[type="submit"]')).toBeEnabled();
});

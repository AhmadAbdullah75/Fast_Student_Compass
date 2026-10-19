import { test, expect, type Page } from "@playwright/test";

test("publication: sidebar search isolates the selected saved conversation", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("textbox", { name: "Search conversations" })
    .fill("Earlier campus");
  await expect(
    page.getByRole("button", { name: "Earlier campus notes", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Interrupted conversation", exact: true }),
  ).not.toBeVisible();
  await page
    .getByRole("button", { name: "Earlier campus notes", exact: true })
    .click();
  await expect(page.getByText("An existing saved answer.")).toBeVisible();
  await page.getByRole("button", { name: "Clear search" }).click();
  await expect(
    page.getByRole("button", { name: "Interrupted conversation", exact: true }),
  ).toBeVisible();
});

test("publication: timeout recovery preserves one question and hides provider internals", async ({
  page,
  request,
}) => {
  await ready(page);
  await send(page, "[timeout] recover provider failure");
  await expect(
    page.getByRole("button", { name: "Retry answer" }),
  ).toBeVisible();
  await expect(page.getByText("SECRET", { exact: false })).not.toBeVisible();
  await page.getByRole("button", { name: "Retry answer" }).click();
  await complete(page);
  await expect(page.locator(".exchange")).toHaveCount(1);
  const calls = await (await request.get("/api/test/calls")).json();
  expect(
    calls.filter(
      (c: any) => c.question === "[timeout] recover provider failure",
    ),
  ).toHaveLength(2);
});

test("publication: reduced motion, keyboard dialog and oversized input validation", async ({
  page,
  request,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await ready(page);
  await expect(page.locator("textarea")).toHaveAttribute("maxlength", "6000");
  expect(
    await page.evaluate(
      () => matchMedia("(prefers-reduced-motion: reduce)").matches,
    ),
  ).toBe(true);
  await page
    .getByRole("button", { name: "Options for Earlier campus notes" })
    .focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Home");
  await page.getByRole("menuitem", { name: "Rename" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const created = await (
    await request.post("/api/conversations", { data: {} })
  ).json();
  try {
    const r = await request.post(`/api/conversations/${created.id}/turns`, {
      data: { question: "x".repeat(6001), request_id: crypto.randomUUID() },
    });
    expect(r.status()).toBe(422);
    expect(
      (await (await request.get(`/api/conversations/${created.id}`)).json())
        .turns,
    ).toHaveLength(0);
    expect(
      (
        await request.patch(`/api/conversations/${created.id}`, {
          data: { title: "   " },
        })
      ).status(),
    ).toBe(422);
  } finally {
    await request.delete(`/api/conversations/${created.id}`);
  }
});
const composer = (page: Page) =>
  page.getByRole("textbox", { name: "Message Student Compass" });
async function ready(page: Page) {
  await page.goto("/");
  await expect(composer(page)).toBeEnabled();
}
async function send(page: Page, q: string) {
  await composer(page).fill(q);
  await composer(page).press("Enter");
}
async function complete(page: Page) {
  await expect(page.locator(".markdown").last()).toContainText(
    "A documented answer",
  );
}
async function menu(page: Page, title: string) {
  const row = page
    .locator(".chat-row")
    .filter({ has: page.getByRole("button", { name: title, exact: true }) });
  await row.hover();
  await row
    .getByRole("button", { name: `Options for ${title}`, exact: true })
    .click();
}

test("fresh opening and refresh show a blank draft; saved chat resumes manually", async ({
  page,
  request,
}) => {
  await ready(page);
  await expect(
    page.getByRole("heading", { name: "Your campus. A clearer path." }),
  ).toBeVisible();
  await expect(page.getByText("An existing saved answer.")).not.toBeVisible();
  const before = (await (await request.get("/api/conversations")).json())
    .length;
  await page.reload();
  await expect(composer(page)).toBeEnabled();
  expect((await (await request.get("/api/conversations")).json()).length).toBe(
    before,
  );
  await page
    .getByRole("button", { name: "Earlier campus notes", exact: true })
    .click();
  await expect(page.getByText("An existing saved answer.")).toBeVisible();
  await page.reload();
  await expect(page.locator(".exchange")).toHaveCount(0);
});

test("Enter renders user immediately, loading, no duplicates, then cited answer and timestamps", async ({
  page,
  request,
}) => {
  await ready(page);
  const q = "[slow] Explain the degree duration";
  await send(page, q);
  await expect(page.locator(".user-bubble")).toHaveText(q, { timeout: 1000 });
  await expect(page.getByRole("status")).toContainText(
    "Finding a clearer answer",
  );
  await expect(composer(page)).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Send message" }),
  ).toBeDisabled();
  await complete(page);
  await expect(page.locator(".exchange")).toHaveCount(1);
  await expect(page.locator(".user-message time")).toContainText("You ·");
  await expect(page.locator(".answer-footer time")).not.toBeEmpty();
  await expect(
    page.getByText("gemini-3.5-flash-lite", { exact: true }),
  ).not.toBeVisible();
  expect(
    (await (await request.get("/api/test/calls")).json()).filter(
      (c: any) => c.question === q,
    ),
  ).toHaveLength(1);
  await page.screenshot({
    path: "../reports/react-chat-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
});

test("sources, citation anchors, technical details, math and safe Markdown", async ({
  page,
}) => {
  await ready(page);
  await send(page, "Show sources and math");
  await complete(page);
  await expect(page.locator(".katex").first()).toBeVisible();
  await expect(page.locator(".markdown code")).toHaveText("[S1]");
  expect(await page.evaluate(() => Boolean((window as any).compassXss))).toBe(
    false,
  );
  await page.locator(".inline-citation").first().click();
  await expect(page.locator(".source-body pre")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open original source" }),
  ).toHaveAttribute("rel", "noopener noreferrer");
  await page.getByText("Response details", { exact: true }).click();
  await expect(
    page.getByText("gemini-3.5-flash-lite", { exact: true }),
  ).toBeVisible();
  await page.getByText("Retrieval and active history", { exact: true }).click();
  await expect(page.locator(".technical pre")).toContainText(
    "Show sources and math",
  );
});

test("hover menu rename, keyboard dismissal and confirmed delete preserve other chats", async ({
  page,
  request,
}) => {
  await ready(page);
  await send(page, "A chat to rename");
  await complete(page);
  await menu(page, "A chat to rename");
  await page.getByRole("menuitem", { name: "Rename" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog
    .getByRole("textbox", { name: "Conversation name" })
    .fill("Course planning");
  await dialog.getByRole("button", { name: "Save name" }).click();
  await expect(
    page.getByRole("button", { name: "Course planning", exact: true }),
  ).toBeVisible();
  await menu(page, "Course planning");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu")).toHaveCount(0);
  await menu(page, "Course planning");
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator(".exchange")).toHaveCount(1);
  await menu(page, "Course planning");
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await dialog.getByRole("button", { name: "Delete conversation" }).click();
  await expect(
    page.getByRole("button", { name: "Course planning", exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".exchange")).toHaveCount(0);
  expect(
    (await (await request.get("/api/conversations")).json()).some(
      (c: any) => c.title === "Earlier campus notes",
    ),
  ).toBe(true);
});

test("Send click, follow-up memory, and New conversation isolation", async ({
  page,
}) => {
  await ready(page);
  await composer(page).fill("A private first topic");
  await page.getByRole("button", { name: "Send message" }).click();
  await complete(page);
  await send(page, "What about the next semester?");
  await expect(page.locator(".exchange")).toHaveCount(2);
  await expect(page.locator(".markdown").last()).toContainText(
    "A private first topic",
  );
  await page
    .getByRole("button", { name: "New conversation", exact: true })
    .click();
  await expect(page.locator(".exchange")).toHaveCount(0);
  await send(page, "An isolated question");
  await complete(page);
  await expect(page.locator(".markdown")).toContainText(
    "Previous questions in this chat: None",
  );
});

test("failed generation preserves question and retry does not duplicate", async ({
  page,
}) => {
  await ready(page);
  await send(page, "[quota] Keep my question");
  await expect(
    page.getByRole("button", { name: "Retry answer", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".user-bubble")).toHaveText(
    "[quota] Keep my question",
  );
  await expect(page.getByText("SECRET", { exact: false })).toHaveCount(0);
  await page.getByRole("button", { name: "Retry answer", exact: true }).click();
  await complete(page);
  await expect(page.locator(".exchange")).toHaveCount(1);
});

test("interrupted persisted question can be discarded and composer recovers", async ({
  page,
}) => {
  await ready(page);
  await page
    .getByRole("button", { name: "Interrupted conversation", exact: true })
    .click();
  await expect(
    page.getByText("This question was interrupted", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Discard question" }).click();
  await expect(composer(page)).toBeEnabled();
  await expect(page.locator(".exchange")).toHaveCount(0);
});

test("lost submit response reconnects idempotently without a second turn", async ({
  page,
  request,
}) => {
  await ready(page);
  const q = "A network recovery question";
  let once = true;
  await page.route("**/api/conversations/*/turns", async (route) => {
    if (once) {
      once = false;
      await route.fetch();
      await route.abort("failed");
    } else await route.continue();
  });
  await send(page, q);
  await expect(
    page.getByRole("button", { name: "Reconnect & retry" }),
  ).toBeVisible();
  await expect(page.locator(".user-bubble")).toHaveText(q);
  await page.getByRole("button", { name: "Reconnect & retry" }).click();
  await complete(page);
  await expect(page.locator(".exchange")).toHaveCount(1);
  expect(
    (await (await request.get("/api/test/calls")).json()).filter(
      (c: any) => c.question === q,
    ),
  ).toHaveLength(1);
});

test("malformed response is recoverable and question stays visible", async ({
  page,
}) => {
  await ready(page);
  let once = true;
  await page.route("**/api/conversations/*/turns", async (route) => {
    if (once) {
      once = false;
      await route.fulfill({ status: 202, json: { unexpected: true } });
    } else await route.continue();
  });
  await send(page, "Unexpected response recovery");
  await expect(page.locator(".user-bubble")).toHaveText(
    "Unexpected response recovery",
  );
  await expect(
    page.getByRole("button", { name: "Reconnect & retry" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reconnect & retry" }).click();
  await complete(page);
});

test("empty inputs are not submitted and Shift+Enter inserts a newline", async ({
  page,
  request,
}) => {
  await ready(page);
  const before = (await (await request.get("/api/test/calls")).json()).length;
  await composer(page).fill("   ");
  await expect(
    page.getByRole("button", { name: "Send message" }),
  ).toBeDisabled();
  await composer(page).press("Enter");
  await expect(page.locator(".exchange")).toHaveCount(0);
  await composer(page).fill("First line");
  await composer(page).press("Shift+Enter");
  await composer(page).type("Second line");
  await expect(composer(page)).toHaveValue("First line\nSecond line");
  expect((await (await request.get("/api/test/calls")).json()).length).toBe(
    before,
  );
});

test("switching while an answer runs does not leak it into the new draft", async ({
  page,
}) => {
  await ready(page);
  await send(page, "[slow] Keep this in its own chat");
  await expect(
    page.getByRole("button", {
      name: "[slow] Keep this in its own chat",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "New conversation", exact: true })
    .click();
  await expect(page.locator(".exchange")).toHaveCount(0);
  await page.waitForTimeout(4500);
  await expect(page.locator(".exchange")).toHaveCount(0);
  await page
    .getByRole("button", {
      name: "[slow] Keep this in its own chat",
      exact: true,
    })
    .click();
  await complete(page);
});

test("mobile sidebar, composer, sources and no horizontal overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await ready(page);
  await page.screenshot({
    path: "../reports/react-welcome-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Open sidebar" }).click();
  await expect(
    page.getByRole("button", { name: "New conversation", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Earlier campus notes", exact: true })
    .click();
  await expect(page.getByText("An existing saved answer.")).toBeVisible();
  await page.getByRole("button", { name: "Open sidebar" }).click();
  await page
    .getByRole("button", { name: "New conversation", exact: true })
    .click();
  await send(page, "A mobile question");
  await complete(page);
  await page.locator(".sources>summary").click();
  await page.locator(".source-card>summary").click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../reports/react-chat-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
});

test("welcome desktop visual and document shortcuts", async ({ page }) => {
  await ready(page);
  await page.screenshot({
    path: "../reports/react-welcome-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("button", { name: "Academic guidance", exact: false })
    .click();
  await expect(composer(page)).toHaveValue("How do I withdraw from a course?");
  await expect(composer(page)).toBeFocused();
});

test("losing the create response safely reuses the draft conversation ID", async ({
  page,
  request,
}) => {
  await ready(page);
  let once = true;
  const before = (await (await request.get("/api/conversations")).json())
    .length;
  await page.route("**/api/conversations", async (route) => {
    if (route.request().method() === "POST" && once) {
      once = false;
      await route.fetch();
      await route.abort("failed");
    } else await route.continue();
  });
  await send(page, "Recover creation response");
  await page.getByRole("button", { name: "Reconnect & retry" }).click();
  await complete(page);
  expect((await (await request.get("/api/conversations")).json()).length).toBe(
    before + 1,
  );
  await expect(page.locator(".exchange")).toHaveCount(1);
});

test("network interruption during generation recovers by polling the saved turn", async ({
  page,
  request,
}) => {
  await ready(page);
  const q = "[slow] Recover polling";
  await send(page, q);
  await expect(
    page.getByRole("button", { name: q, exact: true }),
  ).toBeVisible();
  await page.context().setOffline(true);
  await expect(page.locator(".connection-notice")).toBeVisible();
  await expect(page.locator(".user-bubble")).toHaveText(q);
  await page.context().setOffline(false);
  await complete(page);
  expect(
    (await (await request.get("/api/test/calls")).json()).filter(
      (c: any) => c.question === q,
    ),
  ).toHaveLength(1);
});

test("a failed formatting asset preserves plain text and expandable sources", async ({
  page,
}) => {
  await page.route("**/assets/AnswerMarkdown-*.js", (route) =>
    route.abort("failed"),
  );
  await ready(page);
  await send(page, "A formatting fallback question");
  await complete(page);
  await expect(
    page.getByText("Plain-text view", { exact: false }),
  ).toBeVisible();
  await page.locator(".sources>summary").click();
  await page.locator(".source-card>summary").click();
  await expect(page.locator(".source-body pre")).toBeVisible();
  await expect(composer(page)).toBeEnabled();
});

test("slow saved-chat response cannot overwrite a later selection", async ({
  page,
  request,
}) => {
  await ready(page);
  await send(page, "The later selected chat");
  await complete(page);
  const old = (await (await request.get("/api/conversations")).json()).find(
    (c: any) => c.title === "Earlier campus notes",
  );
  await page.route(`**/api/conversations/${old.id}`, async (route) => {
    await new Promise((r) => setTimeout(r, 1500));
    await route.continue();
  });
  await page
    .getByRole("button", { name: "Earlier campus notes", exact: true })
    .click();
  await page
    .getByRole("button", { name: "The later selected chat", exact: true })
    .click();
  await expect(page.locator(".user-bubble")).toHaveText(
    "The later selected chat",
  );
  await page.waitForTimeout(1800);
  await expect(page.locator(".user-bubble")).toHaveText(
    "The later selected chat",
  );
});

test("long history menus remain visible outside the scrolling list", async ({
  page,
  request,
}) => {
  const ids: string[] = [];
  for (let i = 0; i < 22; i++) {
    const c = await (
      await request.post("/api/conversations", { data: {} })
    ).json();
    ids.push(c.id);
    await request.patch(`/api/conversations/${c.id}`, {
      data: { title: `Overflow conversation ${i}` },
    });
  }
  try {
    await page.setViewportSize({ width: 1100, height: 700 });
    await ready(page);
    await menu(page, "Earlier campus notes");
    await expect(
      page.getByRole("menuitem", { name: "Delete" }),
    ).toBeInViewport();
    await page.getByRole("menuitem", { name: "Rename" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
  } finally {
    for (const id of ids) await request.delete(`/api/conversations/${id}`);
  }
});

test("copy feedback and privacy dialog work without generation", async ({
  page,
}) => {
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await ready(page);
  await send(page, "A copyable answer");
  await complete(page);
  await page.getByRole("button", { name: "Copy answer", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Answer copied", exact: true }),
  ).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain(
    "A documented answer",
  );
  await page
    .getByRole("button", { name: "About Compass", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("sent to Google");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("a saved rename stays applied when only the subsequent list refresh fails", async ({
  page,
}) => {
  await ready(page);
  await send(page, "A rename acknowledgement test");
  await complete(page);
  await menu(page, "A rename acknowledgement test");
  await page.getByRole("menuitem", { name: "Rename" }).click();
  await page
    .getByRole("textbox", { name: "Conversation name" })
    .fill("Confirmed renamed chat");
  let once = true;
  await page.route("**/api/conversations", async (route) => {
    if (route.request().method() === "GET" && once) {
      once = false;
      await route.abort("failed");
    } else await route.continue();
  });
  await page.getByRole("button", { name: "Save name", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Confirmed renamed chat", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".connection-notice")).toBeVisible();
  await page.getByRole("button", { name: "Reconnect", exact: true }).click();
  await expect(page.locator(".connection-notice")).toHaveCount(0);
});

test("malformed error fields cannot crash the conversation view", async ({
  page,
}) => {
  await ready(page);
  let once = true;
  await page.route("**/api/conversations/*/turns", async (route) => {
    if (once) {
      once = false;
      await route.fulfill({
        status: 202,
        json: {
          id: "unexpected",
          question: "A malformed failure",
          created: new Date().toISOString(),
          completed: null,
          running: false,
          status: "failed",
          answer: null,
          error: { message: "bad shape" },
          citations: [],
        },
      });
    } else await route.continue();
  });
  await send(page, "A malformed failure");
  await expect(page.locator(".user-bubble")).toHaveText("A malformed failure");
  await page.getByRole("button", { name: "Reconnect & retry" }).click();
  await complete(page);
  await expect(page.locator(".exchange")).toHaveCount(1);
});

test('hardening: unsafe Markdown/source links stay inert while HTTPS and citations work', async ({ page }) => {
  await page.route('**/api/conversations/*', async route => {
    if (route.request().method() !== 'GET') return route.continue();
    const response = await route.fetch();
    const data = await response.json();
    for (const turn of data.turns ?? []) {
      if (turn.question === 'Verify unsafe links' && turn.status === 'completed') {
        turn.answer = 'A documented answer [S1]. [JavaScript link](javascript:alert%281%29) [Data link](data:text/html,hello) [Relative host](//example.com) [Safe HTTPS](https://example.com)';
        turn.citations[0].references[0].url = 'javascript:alert(1)';
      }
    }
    return route.fulfill({ response, json: data });
  });
  await ready(page);
  await send(page, 'Verify unsafe links');
  await complete(page);
  await expect(page.getByText('JavaScript link', { exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'JavaScript link' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Data link' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Relative host' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Safe HTTPS' })).toHaveAttribute('href', 'https://example.com');
  await page.locator('.inline-citation').first().click();
  await expect(page.locator('.source-body pre')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open original source' })).toHaveCount(0);
});

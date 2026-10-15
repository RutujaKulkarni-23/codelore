import { test, expect } from "@playwright/test";

test.describe("CodeLore E2E Integration Suite", () => {
  test("1. /board shows 5 Python files and total line count from /api/project", async ({ page }) => {
    await page.goto("/board");

    // Wait for real backend project data to load
    await expect(page.locator("text=Naive_RAG").first()).toBeVisible({ timeout: 15000 });

    // Verify 5 files and line count (1,219 total py lines) from /api/project
    const filesBadge = page.locator("span:has-text('files')").first();
    await expect(filesBadge).toBeVisible();
    await expect(page.locator("span.font-heading:has-text('5')").first()).toBeVisible();

    const linesBadge = page.locator("span:has-text('lines')").first();
    await expect(linesBadge).toBeVisible();
    await expect(page.locator("span.font-heading:has-text('1,219')").first()).toBeVisible();

    // Verify commit text in active codebase footer
    await expect(page.locator("p:has-text('5 files · indexed')")).toBeVisible();
  });

  test("2. /files: click query_pipeline.py -> code shows; outline lists 6 functions; click embed_query range -> lines 27-86 highlighted", async ({ page }) => {
    await page.goto("/files");

    // Wait for file tree to load from /api/project
    const queryPipelineTreeBtn = page.locator("button:has-text('query_pipeline.py')").first();
    await expect(queryPipelineTreeBtn).toBeVisible({ timeout: 15000 });

    // Click query_pipeline.py in file tree
    await queryPipelineTreeBtn.click();

    // Verify code viewer displays file contents from /api/file
    await expect(page.locator("span.font-semibold.text-white:has-text('query_pipeline.py')")).toBeVisible();
    await expect(page.locator("pre:has-text('def embed_query')").first()).toBeVisible({ timeout: 10000 });

    // Verify outline from /api/outline lists 6 functions
    const outlineHeader = page.locator("text=OUTLINE · QUERY_PIPELINE.PY");
    await expect(outlineHeader).toBeVisible();

    const outlineButtons = page.locator("aside button:has-text('()')");
    await expect(outlineButtons).toHaveCount(6);

    // Verify specific function names
    await expect(page.locator("button:has-text('embed_query()')")).toBeVisible();
    await expect(page.locator("button:has-text('retrieve_top_k()')")).toBeVisible();
    await expect(page.locator("button:has-text('build_prompt_with_context()')")).toBeVisible();
    await expect(page.locator("button:has-text('generate_answer()')")).toBeVisible();
    await expect(page.locator("button:has-text('generate_answer_without_rag()')")).toBeVisible();
    await expect(page.locator("button:has-text('run_query_pipeline()')")).toBeVisible();

    // Click embed_query range
    await page.locator("button:has-text('embed_query()')").click();

    // Verify lines 27-86 are highlighted in CodeViewer header and line gutter
    await expect(page.locator("span:has-text('L27–86')")).toBeVisible();
  });

  test("3. /start shows entry point main.py and 4 commands", async ({ page }) => {
    await page.goto("/start");

    // Wait for real backend overview data to load
    await expect(page.locator("h3:has-text('main.py')")).toBeVisible({ timeout: 15000 });

    // Verify 4 commands from /api/overview
    const commandBoxes = page.locator("div.font-mono.text-xs.text-cyan-200");
    await expect(commandBoxes).toHaveCount(4);

    await expect(page.locator("span:has-text('python main.py --mock')")).toBeVisible();
    await expect(page.locator("span:has-text('python main.py --index')")).toBeVisible();
    await expect(page.locator("span:has-text('python main.py --query \"your question\"')")).toBeVisible();
    await expect(page.locator("span:has-text('python main.py --compare')")).toBeVisible();
  });

  test("4. Case flow with fake stream: timeline shows Boss -> Architecture Mapper -> analyze_imports; verdict chip indexer.py:27-27 opens file with line 27 highlighted; Import map shows edge indexer.py -> vector_store.py", async ({ page }) => {
    // Intercept ONLY POST /api/ask with recorded fake SSE stream
    await page.route("**/api/ask", async (route) => {
      if (route.request().method() === "POST") {
        const sseBody = [
          "event: session",
          'data: {"session_id": "test_e2e_session"}',
          "",
          "event: routed",
          'data: {"agent": "Boss"}',
          "",
          "event: routed",
          'data: {"agent": "Architecture Mapper"}',
          "",
          "event: tool_call",
          'data: {"agent": "Architecture Mapper", "tool": "analyze_imports", "args": {"module_name": "upsert_to_vector_db"}}',
          "",
          "event: tool_done",
          'data: {"agent": "Architecture Mapper", "tool": "analyze_imports"}',
          "",
          "event: answer",
          'data: {"agent": "Architecture Mapper", "text": "upsert_to_vector_db is referenced at indexer.py:27-27."}',
          "",
          "event: citations",
          'data: {"items": [{"path": "indexer.py", "start": 27, "end": 27}]}',
          "",
          "event: done",
          'data: {"seconds": 1.25}',
          "",
          "",
        ].join("\n");

        await route.fulfill({
          status: 200,
          headers: {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
          },
          body: sseBody,
        });
      } else {
        await route.continue();
      }
    });

    // Navigate to case with inquiry
    await page.goto("/case/e2e-case-100?q=Which%20files%20import%20upsert_to_vector_db%3F");

    // 1. Verify timeline shows Boss -> Architecture Mapper -> analyze_imports
    await expect(page.locator("span.font-bold:has-text('Boss:')")).toBeVisible({ timeout: 15000 });
    await expect(page.locator("span.font-bold:has-text('Architecture Mapper:')").first()).toBeVisible();
    await expect(page.locator("span.text-cyan-300:has-text('analyze_imports')")).toBeVisible();

    // 2. Verify verdict text and citation chip indexer.py:27-27
    const chip = page.locator("button:has-text('indexer.py:27-27')");
    await expect(chip).toBeVisible();

    // 3. Click chip -> opens indexer.py with line 27 highlighted in Evidence Panel
    await chip.click();
    await expect(page.locator("span.text-cyan-300.font-mono:has-text('L27–27')")).toBeVisible();
    await expect(page.locator("span.font-semibold.text-white:has-text('indexer.py')")).toBeVisible();

    // 4. Switch to "Import map" tab in Evidence Panel
    const importMapTabBtn = page.locator("button:has-text('Import map')");
    await importMapTabBtn.click();

    // Verify Import map renders nodes and edge from indexer.py to vector_store.py
    await expect(page.locator(".react-flow__node:has-text('indexer.py')")).toBeVisible({ timeout: 10000 });
    await expect(page.locator(".react-flow__node:has-text('vector_store.py')")).toBeVisible();
    await expect(page.locator(".react-flow__edge-text:has-text('L27')")).toBeVisible();
  });

  test("5. Error flow: fake stream returns error code 429 -> Lore error card is visible", async ({ page }) => {
    // Intercept POST /api/ask to return 429
    await page.route("**/api/ask", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 429,
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            detail: "Too many case requests. Please wait a few minutes before opening a new case.",
            code: 429,
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/case/e2e-error-case?q=Trigger%20rate%20limit");

    // Verify Lore error card is visible
    await expect(
      page.locator("text=Rate limit reached — Lore needs a quick breather")
    ).toBeVisible({ timeout: 15000 });
    await expect(
      page.locator("text=Too many case requests. Please wait a few minutes before opening a new case.")
    ).toBeVisible();
  });
});

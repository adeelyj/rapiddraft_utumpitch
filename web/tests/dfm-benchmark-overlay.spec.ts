import { expect, test, type Page, type Route } from "@playwright/test";

const MODEL_ID = "benchmark-overlay-model";
const COMPONENT_NODE_NAME = "Part__sample_2";
const BENCHMARK_REVIEW_CACHE_KEY = `dfm_benchmark_sidebar_review_last_v1:${MODEL_ID}:${COMPONENT_NODE_NAME}`;

const minimalPreviewScene = JSON.stringify({
  asset: { version: "2.0" },
  scene: 0,
  scenes: [{ nodes: [] }],
  nodes: [],
});

const componentProfiles = {
  [COMPONENT_NODE_NAME]: {
    material: "Aluminum 6061",
    manufacturingProcess: "CNC Milling",
    industry: "Aerospace",
  },
};

const cachedBenchmarkReview = {
  saved_at: "2026-03-14T19:00:00.000Z",
  payload: {
    routes: [
      {
        plan_id: "plan-cnc-milling",
        process_id: "cnc_milling",
        process_label: "CNC Milling",
        findings: [
          {
            rule_id: "corner_radius_consistency",
            pack_id: "pack-1",
            finding_type: "rule_violation",
            title: "Corner radius consistency across pockets",
            severity: "warning",
            description: "Mixed internal corner radii create avoidable tool changes and setup friction.",
            recommended_action: "Normalize the inside pocket radius so the same cutter can finish each corner.",
            expected_impact: {
              risk_reduction: "Medium",
              cost_impact: "Medium",
              lead_time_impact: "Low",
            },
            evidence: {
              violating_instances: [
                {
                  instance_id: "top-right-front-pocket-corner",
                  location_description: "top-right-front pocket corner",
                  radius_mm: 1.5,
                  bbox_bounds_mm: [10, 20, 3, 18, 28, 11],
                },
              ],
            },
          },
        ],
      },
    ],
    geometry_evidence: {
      process_summary: {
        effective_process_label: "CNC Milling",
      },
      feature_groups: [],
      detail_metrics: [],
    },
  },
};

const dfmConfigResponse = {
  profile_options: {
    materials: [{ id: "al_6061", label: "Aluminum 6061" }],
    manufacturingProcesses: [{ id: "cnc_milling", label: "CNC Milling" }],
    industries: [
      {
        id: "aerospace",
        label: "Aerospace",
        standards: ["ASME Y14.5", "ISO 2768", "NADCAP AC7108"],
      },
    ],
  },
  processes: [{ process_id: "cnc_milling", label: "CNC Milling" }],
  roles: [{ role_id: "general_dfm", label: "General DFM" }],
  ui_bindings: {
    screens: {
      dfm_review_panel: {
        flow_order: ["generate_review"],
        controls: [
          {
            control_id: "generate_review",
            label: "Generate review",
          },
        ],
      },
    },
  },
};

const modelTemplatesResponse = {
  templates: [
    {
      template_id: "executive_1page",
      label: "Executive 1-page",
      source: "system",
    },
  ],
};

const partFactsResponse = {
  schema_version: "1.0",
  model_id: MODEL_ID,
  component_node_name: COMPONENT_NODE_NAME,
  component_display_name: "sample 2",
  generated_at: "2026-03-14T19:00:00.000Z",
  coverage: {
    core_extraction_coverage: {
      known_metrics: 0,
      applicable_metrics: 0,
      not_applicable_metrics: 0,
      total_metrics: 0,
      percent: 0,
    },
    full_rule_readiness_coverage: {
      known_metrics: 0,
      applicable_metrics: 0,
      not_applicable_metrics: 0,
      total_metrics: 0,
      percent: 0,
    },
  },
  overall_confidence: "medium",
  missing_inputs: [],
  assumptions: [],
  errors: [],
  geometry_instances: {
    internal_radius_instances: [],
    hole_instances: [],
    wall_thickness_instances: [],
  },
  sections: {
    geometry: {},
    manufacturing_signals: {},
    declared_context: {},
    process_inputs: {},
    rule_inputs: {},
  },
};

const corsHeaders = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS",
  "access-control-allow-headers": "*",
};

const fulfillJson = async (route: Route, payload: unknown, status = 200) => {
  await route.fulfill({
    status,
    contentType: "application/json",
    headers: corsHeaders,
    body: JSON.stringify(payload),
  });
};

const mockApi = async (page: Page) => {
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;

    if (pathname === `/api/models/${MODEL_ID}/preview`) {
      await route.fulfill({
        status: 200,
        contentType: "model/gltf-binary",
        headers: corsHeaders,
        body: minimalPreviewScene,
      });
      return;
    }

    if (pathname === "/api/dfm/config") {
      await fulfillJson(route, dfmConfigResponse);
      return;
    }

    if (pathname === "/api/review-templates") {
      await fulfillJson(route, []);
      return;
    }

    if (pathname === "/api/models" && request.method() === "POST") {
      await fulfillJson(route, {
        modelId: MODEL_ID,
        originalName: "sample 2.stp",
        previewUrl: `/api/models/${MODEL_ID}/preview`,
        views: {},
        components: [
          {
            id: "component-sample-2",
            nodeName: COMPONENT_NODE_NAME,
            displayName: "sample 2",
            triangleCount: 128,
          },
        ],
        componentProfiles,
      });
      return;
    }

    if (pathname === `/api/models/${MODEL_ID}/component-profiles`) {
      await fulfillJson(route, {
        componentProfiles,
      });
      return;
    }

    if (pathname === `/api/models/${MODEL_ID}/tickets`) {
      await fulfillJson(route, []);
      return;
    }

    if (pathname === `/api/models/${MODEL_ID}/design-reviews`) {
      await fulfillJson(route, []);
      return;
    }

    if (pathname === `/api/models/${MODEL_ID}/dfm/templates`) {
      await fulfillJson(route, modelTemplatesResponse);
      return;
    }

    if (pathname === `/api/models/${MODEL_ID}/components/${COMPONENT_NODE_NAME}/part-facts`) {
      await fulfillJson(route, partFactsResponse);
      return;
    }

    if (pathname === "/api/template/drawing") {
      await route.fulfill({ status: 204, headers: corsHeaders, body: "" });
      return;
    }

    await fulfillJson(route, { detail: `Unhandled mock API path: ${pathname}` }, 404);
  });
};

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.addInitScript(
    ({ reviewCacheKey, cachedReviewValue }) => {
      window.localStorage.setItem(reviewCacheKey, JSON.stringify(cachedReviewValue));
    },
    {
      reviewCacheKey: BENCHMARK_REVIEW_CACHE_KEY,
      cachedReviewValue: cachedBenchmarkReview,
    },
  );
});

test("keeps the compact benchmark overlay anchored to the viewer top-right", async ({ page }) => {
  await page.goto("/?mode=expert");

  await page.locator('input[type="file"]').first().setInputFiles({
    name: "sample 2.stp",
    mimeType: "application/step",
    buffer: Buffer.from("ISO-10303-21;"),
  });

  await expect(page.locator(".component-profile-panel")).toContainText("sample 2");

  await page
    .locator(".sidebar-rail--right .sidebar-rail__button")
    .filter({ hasText: "DFM Benchmark Bar" })
    .click();

  const benchmarkSidebar = page.locator(".dfm-sidebar").filter({ hasText: "DFM Benchmark Bar" });

  await expect(benchmarkSidebar).toBeVisible();
  await expect(benchmarkSidebar.locator(".dfm-sidebar__issue-card")).toContainText("Corner radius consistency across pockets");

  await benchmarkSidebar.getByRole("button", { name: "Show in model" }).first().click();

  const overlay = page.locator(".analysis-focus-overlay.analysis-focus-overlay--compact");
  const overlayTitle = overlay.locator(".analysis-focus-overlay__title");
  const overlayLocationChip = overlay.locator(".analysis-focus-overlay__location-chip");
  const overlayDetails = overlay.locator(".analysis-focus-overlay__details");

  await expect(overlay).toBeVisible();
  await expect(overlayTitle).toHaveText("Corner radius consistency across pockets");
  await expect(overlayLocationChip).toHaveText("top-right-front pocket corner");
  await expect(overlayDetails).toHaveCount(0);

  const viewerBounds = await page.locator(".viewer-area").boundingBox();
  const overlayBounds = await overlay.boundingBox();

  expect(viewerBounds).not.toBeNull();
  expect(overlayBounds).not.toBeNull();

  if (!viewerBounds || !overlayBounds) {
    throw new Error("Expected viewer and overlay bounds to be available.");
  }

  const overlayRightInset = viewerBounds.x + viewerBounds.width - (overlayBounds.x + overlayBounds.width);
  const overlayTopInset = overlayBounds.y - viewerBounds.y;

  expect(overlayRightInset).toBeGreaterThanOrEqual(0);
  expect(overlayRightInset).toBeLessThanOrEqual(24);
  expect(overlayTopInset).toBeGreaterThanOrEqual(0);
  expect(overlayTopInset).toBeLessThanOrEqual(28);
  expect(overlayBounds.width).toBeLessThanOrEqual(190);
});

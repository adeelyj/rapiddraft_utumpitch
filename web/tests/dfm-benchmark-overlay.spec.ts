import { expect, test, type Locator, type Page, type Route } from "@playwright/test";

const MODEL_ID = "benchmark-overlay-model";
const COMPONENT_NODE_NAME = "Part__sample_2";
const BENCHMARK_REVIEW_CACHE_KEY = `dfm_benchmark_sidebar_review_last_v1:${MODEL_ID}:${COMPONENT_NODE_NAME}`;
const DEFAULT_INDUSTRY_STANDARDS = [
  "ASME Y14.5",
  "ISO 2768",
  "NADCAP AC7108",
  "SAE AS9100D",
  "MIL-STD-31000",
];

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

const benchmarkReviewPayload: Record<string, any> = {
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
};

const pocketFeatureGroupAnchor = {
  anchor_id: "pocket-open",
  component_node_name: COMPONENT_NODE_NAME,
  anchor_kind: "region",
  position_mm: [14, 24, 7],
  bbox_bounds_mm: [10, 20, 3, 18, 28, 11],
  face_indices: [17, 18],
  label: "Open pocket",
};

const localizedPocketFeature = {
  feature_id: "open-pocket-1",
  label: "Open pocket 1",
  summary: "2 connected faces",
  geometry_anchor: {
    ...pocketFeatureGroupAnchor,
    anchor_id: "open-pocket-1",
    label: "Open pocket 1",
  },
};

const turningFeatureGroupAnchor = {
  anchor_id: "turning-primary",
  component_node_name: COMPONENT_NODE_NAME,
  anchor_kind: "region",
  position_mm: [42, 12, 10],
  bbox_bounds_mm: [38, 8, 6, 46, 16, 14],
  face_indices: [31, 32],
  label: "Primary turning region",
};

const localizedTurningFeature = {
  feature_id: "turning-diameter-1",
  label: "Turned diameter band 1",
  summary: "R 15 mm | 2 faces",
  geometry_anchor: {
    ...turningFeatureGroupAnchor,
    anchor_id: "turning-diameter-1",
    label: "Turned diameter band 1",
  },
};

const milledFeatureGroupAnchor = {
  anchor_id: "milled-curved",
  component_node_name: COMPONENT_NODE_NAME,
  anchor_kind: "region",
  position_mm: [58, 18, 16],
  bbox_bounds_mm: [54, 14, 12, 62, 22, 20],
  face_indices: [41, 42],
  label: "Curved milled face region",
};

const localizedMilledFeature = {
  feature_id: "milled-curved-1",
  label: "Curved milled face region 1",
  summary: "2 connected faces",
  geometry_anchor: {
    ...milledFeatureGroupAnchor,
    anchor_id: "milled-curved-1",
    label: "Curved milled face region 1",
  },
};

const benchmarkReviewWithFeatureGroupAnchor: Record<string, any> = {
  ...benchmarkReviewPayload,
  geometry_evidence: {
    process_summary: {
      effective_process_label: "CNC Milling",
    },
    feature_groups: [
      {
        group_id: "pockets",
        label: "Pocket features",
        summary: "2 pockets detected, including 1 open pocket candidate.",
        geometry_anchor: pocketFeatureGroupAnchor,
        localized_features: [localizedPocketFeature],
        metrics: [
          {
            key: "pocket_count",
            label: "Pocket features",
            value: 2,
            geometry_anchor: pocketFeatureGroupAnchor,
          },
        ],
      },
      {
        group_id: "turning",
        label: "Turning features",
        summary: "1 turned diameter band with a strong primary turning region.",
        geometry_anchor: turningFeatureGroupAnchor,
        localized_features: [localizedTurningFeature],
        metrics: [
          {
            key: "turned_face_count",
            label: "Turned faces",
            value: 2,
            geometry_anchor: turningFeatureGroupAnchor,
          },
        ],
      },
      {
        group_id: "milled_faces",
        label: "Milled-face features",
        summary: "1 curved milled region detected on the side wall.",
        geometry_anchor: milledFeatureGroupAnchor,
        localized_features: [localizedMilledFeature],
        metrics: [
          {
            key: "milled_face_count",
            label: "Milled faces",
            value: 2,
            geometry_anchor: milledFeatureGroupAnchor,
          },
        ],
      },
    ],
    detail_metrics: [],
  },
};

const benchmarkReviewWithLocalizedFindingAnchor: Record<string, any> = {
  ...benchmarkReviewWithFeatureGroupAnchor,
  routes: [
    {
      ...benchmarkReviewWithFeatureGroupAnchor.routes[0],
      findings: [
        {
          ...benchmarkReviewWithFeatureGroupAnchor.routes[0].findings[0],
          blame_map: {
            localization_status: "region",
            primary_anchor: localizedPocketFeature.geometry_anchor,
            secondary_anchors: [],
            source_fact_keys: ["max_pocket_depth_mm", "min_internal_radius_mm"],
            source_feature_refs: [localizedPocketFeature.feature_id],
            explanation: "Mapped region for CNC-024: deep rib pocket corner.",
          },
        },
      ],
    },
  ],
};

const cachedBenchmarkReview = {
  saved_at: "2026-03-14T19:00:00.000Z",
  payload: benchmarkReviewPayload,
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

type MockApiOptions = {
  industryStandards?: string[];
  reviewPayload?: typeof benchmarkReviewPayload;
  onReviewRequest?: (payload: unknown) => void;
};

type ReviewRequestPayload = {
  component_node_name?: string;
  planning_inputs?: {
    selected_role?: string;
    selected_template?: string;
    run_both_if_mismatch?: boolean;
  };
  context_payload?: {
    include_geometry_anchors?: boolean;
  };
};

const buildDfmConfigResponse = (industryStandards: string[]) => ({
  profile_options: {
    materials: [{ id: "al_6061", label: "Aluminum 6061" }],
    manufacturingProcesses: [{ id: "cnc_milling", label: "CNC Milling" }],
    industries: [
      {
        id: "aerospace",
        label: "Aerospace",
        standards: industryStandards,
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
});

const fulfillJson = async (route: Route, payload: unknown, status = 200) => {
  await route.fulfill({
    status,
    contentType: "application/json",
    headers: corsHeaders,
    body: JSON.stringify(payload),
  });
};

const mockApi = async (page: Page, options: MockApiOptions = {}) => {
  const industryStandards = options.industryStandards ?? DEFAULT_INDUSTRY_STANDARDS;
  const reviewPayload = options.reviewPayload ?? benchmarkReviewPayload;

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
      await fulfillJson(route, buildDfmConfigResponse(industryStandards));
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

    if (pathname === `/api/models/${MODEL_ID}/dfm/review-v2` && request.method() === "POST") {
      let requestPayload: unknown = null;
      try {
        requestPayload = request.postDataJSON();
      } catch {
        requestPayload = null;
      }
      options.onReviewRequest?.(requestPayload);
      await fulfillJson(route, reviewPayload);
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

const seedCachedBenchmarkReview = async (page: Page, reviewPayload: typeof benchmarkReviewPayload = benchmarkReviewPayload) => {
  await page.addInitScript(
    ({ reviewCacheKey, cachedReviewValue }) => {
      window.localStorage.setItem(reviewCacheKey, JSON.stringify(cachedReviewValue));
    },
    {
      reviewCacheKey: BENCHMARK_REVIEW_CACHE_KEY,
      cachedReviewValue: {
        ...cachedBenchmarkReview,
        payload: reviewPayload,
      },
    },
  );
};

const importBenchmarkModel = async (page: Page) => {
  await page.goto("/?mode=expert");

  await page.locator('input[type="file"]').first().setInputFiles({
    name: "sample 2.stp",
    mimeType: "application/step",
    buffer: Buffer.from("ISO-10303-21;"),
  });

  const profilePanel = page.locator(".component-profile-panel");
  await expect(profilePanel).toContainText("sample 2");
  return profilePanel;
};

const openBenchmarkSidebar = async (page: Page) => {
  await page
    .locator(".sidebar-rail--right .sidebar-rail__button")
    .filter({ hasText: "DFM Benchmark Bar" })
    .click();

  const benchmarkSidebar = page.locator(".dfm-sidebar").filter({ hasText: "DFM Benchmark Bar" });
  await expect(benchmarkSidebar).toBeVisible();
  return benchmarkSidebar;
};

const expectCompactOverlayTopRight = async (
  page: Page,
  expectations: { title: string; location: string },
) => {
  const overlay = page.locator(".analysis-focus-overlay.analysis-focus-overlay--compact");
  const overlayTitle = overlay.locator(".analysis-focus-overlay__title");
  const overlayLocationChip = overlay.locator(".analysis-focus-overlay__location-chip");
  const overlayDetails = overlay.locator(".analysis-focus-overlay__details");

  await expect(overlay).toBeVisible();
  await expect(overlayTitle).toHaveText(expectations.title);
  await expect(overlayLocationChip).toHaveText(expectations.location);
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
};

const standardChipTexts = async (locator: Locator) => locator.allTextContents();

test("shows a compact standards preview before expanding the full list", async ({ page }) => {
  await mockApi(page);
  const profilePanel = await importBenchmarkModel(page);

  const standardsBlock = profilePanel.locator(".component-profile-panel__standards");
  const visibleStandardChips = standardsBlock.locator(
    ".component-profile-panel__standards-chip:not(.component-profile-panel__standards-chip--muted)",
  );
  const hiddenSummaryChip = standardsBlock.locator(".component-profile-panel__standards-chip--muted");
  const fullListDetails = standardsBlock.locator(".component-profile-panel__standards-details");

  await expect(standardsBlock.locator(".component-profile-panel__standards-count")).toHaveText("5 mapped");
  await expect(visibleStandardChips).toHaveCount(3);
  expect(await standardChipTexts(visibleStandardChips)).toEqual(DEFAULT_INDUSTRY_STANDARDS.slice(0, 3));
  await expect(hiddenSummaryChip).toHaveText("+2 more");
  await expect(fullListDetails.locator("summary")).toHaveText("Show full standards list");

  await fullListDetails.locator("summary").click();
  await expect(fullListDetails.locator("p")).toHaveText(DEFAULT_INDUSTRY_STANDARDS.join(", "));
});

test("keeps the compact benchmark overlay anchored to the viewer top-right from cached benchmark state", async ({ page }) => {
  await mockApi(page);
  await seedCachedBenchmarkReview(page);
  await importBenchmarkModel(page);

  const benchmarkSidebar = await openBenchmarkSidebar(page);

  await expect(benchmarkSidebar.locator(".dfm-sidebar__issue-card")).toContainText("Corner radius consistency across pockets");

  await benchmarkSidebar.getByRole("button", { name: "Show in model" }).first().click();

  await expectCompactOverlayTopRight(page, {
    title: "Corner radius consistency across pockets",
    location: "top-right-front pocket corner",
  });
});

test("prefers a localized feature anchor over the raw violating instance for benchmark issue focus", async ({ page }) => {
  await mockApi(page, { reviewPayload: benchmarkReviewWithLocalizedFindingAnchor });
  await seedCachedBenchmarkReview(page, benchmarkReviewWithLocalizedFindingAnchor);
  await importBenchmarkModel(page);

  const benchmarkSidebar = await openBenchmarkSidebar(page);
  await expect(benchmarkSidebar.locator(".dfm-sidebar__issue-card")).toContainText("Corner radius consistency across pockets");

  await benchmarkSidebar.getByRole("button", { name: "Show in model" }).first().click();

  await expectCompactOverlayTopRight(page, {
    title: "Corner radius consistency across pockets",
    location: "Open pocket 1",
  });
});

test("focuses a feature-recognition group from its geometry anchor", async ({ page }) => {
  await mockApi(page, { reviewPayload: benchmarkReviewWithFeatureGroupAnchor });
  await seedCachedBenchmarkReview(page, benchmarkReviewWithFeatureGroupAnchor);
  await importBenchmarkModel(page);

  const benchmarkSidebar = await openBenchmarkSidebar(page);
  const featureRecognition = benchmarkSidebar.locator(".dfm-sidebar__evidence");
  await featureRecognition.locator("summary").click();

  await benchmarkSidebar.getByRole("button", { name: "Show pocket features in model" }).click();

  const overlay = page.locator(".analysis-focus-overlay");
  await expect(overlay).toBeVisible();
  await expect(overlay.locator(".analysis-focus-overlay__title")).toHaveText("Pocket features");
  await expect(overlay.locator(".analysis-focus-overlay__details")).toContainText(
    "2 pockets detected, including 1 open pocket candidate.",
  );
  await expect(overlay.locator(".analysis-focus-overlay__details")).toContainText("Open pocket");
});

test("focuses a localized feature-recognition item from its geometry anchor", async ({ page }) => {
  await mockApi(page, { reviewPayload: benchmarkReviewWithFeatureGroupAnchor });
  await seedCachedBenchmarkReview(page, benchmarkReviewWithFeatureGroupAnchor);
  await importBenchmarkModel(page);

  const benchmarkSidebar = await openBenchmarkSidebar(page);
  const featureRecognition = benchmarkSidebar.locator(".dfm-sidebar__evidence");
  await featureRecognition.locator("summary").click();

  await benchmarkSidebar.getByRole("button", { name: "Show open pocket 1 in model" }).click();

  const overlay = page.locator(".analysis-focus-overlay");
  await expect(overlay).toBeVisible();
  await expect(overlay.locator(".analysis-focus-overlay__title")).toHaveText("Open pocket 1");
  await expect(overlay.locator(".analysis-focus-overlay__details")).toContainText("Pocket features");
  await expect(overlay.locator(".analysis-focus-overlay__details")).toContainText("2 connected faces");
});

test("focuses turning and milled localized feature-recognition items from their geometry anchors", async ({ page }) => {
  await mockApi(page, { reviewPayload: benchmarkReviewWithFeatureGroupAnchor });
  await seedCachedBenchmarkReview(page, benchmarkReviewWithFeatureGroupAnchor);
  await importBenchmarkModel(page);

  const benchmarkSidebar = await openBenchmarkSidebar(page);
  const featureRecognition = benchmarkSidebar.locator(".dfm-sidebar__evidence");
  await featureRecognition.locator("summary").click();

  await benchmarkSidebar.getByRole("button", { name: "Show turned diameter band 1 in model" }).click();

  const overlay = page.locator(".analysis-focus-overlay");
  await expect(overlay).toBeVisible();
  await expect(overlay.locator(".analysis-focus-overlay__title")).toHaveText("Turned diameter band 1");
  await expect(overlay.locator(".analysis-focus-overlay__details")).toContainText("Turning features");
  await expect(overlay.locator(".analysis-focus-overlay__details")).toContainText("R 15 mm");

  await benchmarkSidebar.getByRole("button", { name: "Show curved milled face region 1 in model" }).click();

  await expect(overlay.locator(".analysis-focus-overlay__title")).toHaveText("Curved milled face region 1");
  await expect(overlay.locator(".analysis-focus-overlay__details")).toContainText("Milled-face features");
  await expect(overlay.locator(".analysis-focus-overlay__details")).toContainText("2 connected faces");
});

test("runs the benchmark generate review flow before showing the compact overlay", async ({ page }) => {
  let observedReviewRequest: unknown = null;

  await mockApi(page, {
    onReviewRequest: (payload) => {
      observedReviewRequest = payload;
    },
  });
  await importBenchmarkModel(page);

  const benchmarkSidebar = await openBenchmarkSidebar(page);
  await expect(benchmarkSidebar).toContainText(
    "Run a review to see design issues first, with feature recognition tucked into a collapsible section below.",
  );
  await expect(benchmarkSidebar.locator(".dfm-sidebar__issue-card")).toHaveCount(0);

  await benchmarkSidebar.getByRole("button", { name: "Generate review" }).click();

  await expect.poll(() => Boolean(observedReviewRequest)).toBe(true);

  const requestPayload = observedReviewRequest as ReviewRequestPayload;
  expect(requestPayload.component_node_name).toBe(COMPONENT_NODE_NAME);
  expect(requestPayload.planning_inputs?.selected_role).toBe("general_dfm");
  expect(requestPayload.planning_inputs?.selected_template).toBe("executive_1page");
  expect(requestPayload.planning_inputs?.run_both_if_mismatch).toBe(true);
  expect(requestPayload.context_payload?.include_geometry_anchors).toBe(true);

  await expect(benchmarkSidebar.locator(".dfm-sidebar__issue-card")).toContainText("Corner radius consistency across pockets");
  await expect(benchmarkSidebar).toContainText("1 design issue");

  await benchmarkSidebar.getByRole("button", { name: "Show in model" }).first().click();

  await expectCompactOverlayTopRight(page, {
    title: "Corner radius consistency across pockets",
    location: "top-right-front pocket corner",
  });
});

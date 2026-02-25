import type {
  DraftLintReportResponse,
  DraftLintSessionResponse,
} from "../types/draftlint";

const joinApiUrl = (base: string, path: string): string => {
  const normalizedBase = base.replace(/\/$/, "");
  if (!normalizedBase) return path;
  if (path.startsWith("http")) return path;
  return `${normalizedBase}${path}`;
};

const readErrorText = async (response: Response, fallback: string): Promise<string> => {
  try {
    const payload = (await response.json()) as { detail?: string; message?: string };
    return payload.detail ?? payload.message ?? fallback;
  } catch {
    return fallback;
  }
};

const runWithFallback = async (
  apiBase: string,
  path: string,
  init: RequestInit,
): Promise<{ response: Response; usedApiBase: string }> => {
  try {
    const response = await fetch(joinApiUrl(apiBase, path), init);
    return { response, usedApiBase: apiBase };
  } catch {
    const response = await fetch(path, init);
    return { response, usedApiBase: "" };
  }
};

export type DraftLintCreateSessionResult = {
  payload: DraftLintSessionResponse;
  usedApiBase: string;
};

export const createDraftLintSession = async (
  apiBase: string,
  file: File,
  standardProfile: string,
): Promise<DraftLintCreateSessionResult> => {
  const path = "/api/draftlint/sessions";
  const formData = new FormData();
  formData.append("file", file);
  formData.append("standard_profile", standardProfile);

  const { response, usedApiBase } = await runWithFallback(apiBase, path, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const detail = await readErrorText(response, "Failed to create DraftLint session.");
    throw new Error(`${detail} (HTTP ${response.status})`);
  }
  const payload = (await response.json()) as DraftLintSessionResponse;
  return { payload, usedApiBase };
};

export type DraftLintGetSessionResult = {
  payload: DraftLintSessionResponse;
  usedApiBase: string;
};

export const getDraftLintSession = async (
  apiBase: string,
  sessionId: string,
): Promise<DraftLintGetSessionResult> => {
  const path = `/api/draftlint/sessions/${sessionId}`;
  const { response, usedApiBase } = await runWithFallback(apiBase, path, {
    method: "GET",
  });
  if (!response.ok) {
    const detail = await readErrorText(response, "Failed to fetch DraftLint session.");
    throw new Error(`${detail} (HTTP ${response.status})`);
  }
  const payload = (await response.json()) as DraftLintSessionResponse;
  return { payload, usedApiBase };
};

export type DraftLintGetReportResult = {
  payload: DraftLintReportResponse;
  usedApiBase: string;
};

export const getDraftLintReport = async (
  apiBase: string,
  reportId: string,
): Promise<DraftLintGetReportResult> => {
  const path = `/api/draftlint/reports/${reportId}`;
  const { response, usedApiBase } = await runWithFallback(apiBase, path, {
    method: "GET",
  });
  if (!response.ok) {
    const detail = await readErrorText(response, "Failed to fetch DraftLint report.");
    throw new Error(`${detail} (HTTP ${response.status})`);
  }
  const payload = (await response.json()) as DraftLintReportResponse;
  return { payload, usedApiBase };
};

export const resolveDraftLintAssetUrl = (
  apiBase: string,
  path: string,
): string => joinApiUrl(apiBase, path);

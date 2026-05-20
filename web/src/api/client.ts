import type {
  Asset,
  AssetTextRequest,
  BackgroundMusic,
  Project,
  ProjectCreateRequest,
  ProjectDetail,
  ProjectListResponse,
} from "../types/project";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

interface ErrorPayload {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const ERROR_MESSAGES: Record<string, string> = {
  asset_preview_not_found: "图片预览尚未生成。",
  background_music_metadata_invalid: "背景音乐元数据无效。",
  background_music_too_large: "背景音乐文件过大。",
  empty_background_music_upload: "上传的背景音乐文件为空。",
  empty_image_upload: "上传的图片文件为空。",
  image_too_large: "图片文件过大。",
  image_too_small: "图片尺寸低于当前输出规格要求。",
  invalid_image_file: "无法解析上传的图片文件。",
  invalid_project_id: "项目 ID 无效。",
  project_file_not_found: "项目文件不存在。",
  project_metadata_invalid: "项目元数据无效。",
  project_not_found: "项目不存在。",
  render_preset_invalid: "渲染规格配置无效。",
  render_preset_missing: "渲染规格配置缺失。",
  render_presets_invalid: "渲染规格配置不是有效 JSON。",
  render_presets_missing: "找不到渲染规格配置。",
  unsupported_background_music_format: "不支持该背景音乐格式。",
  unsupported_image_format: "不支持该图片格式。",
  validation_error: "请求参数校验失败。",
};

export async function listProjects(): Promise<Project[]> {
  const response = await request<ProjectListResponse>("/api/projects");
  return response.projects;
}

export function createProject(payload: ProjectCreateRequest): Promise<Project> {
  return request<Project>("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getProject(projectId: string): Promise<ProjectDetail> {
  return request<ProjectDetail>(`/api/projects/${encodeURIComponent(projectId)}`);
}

export function uploadImage(projectId: string, file: File): Promise<Asset> {
  const form = new FormData();
  form.append("file", file);
  return request<Asset>(`/api/projects/${encodeURIComponent(projectId)}/assets/image`, {
    method: "POST",
    body: form,
  });
}

export function saveAssetText(
  projectId: string,
  payload: AssetTextRequest,
): Promise<Asset> {
  return request<Asset>(`/api/projects/${encodeURIComponent(projectId)}/assets/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function uploadBackgroundMusic(
  projectId: string,
  file: File,
): Promise<BackgroundMusic> {
  const form = new FormData();
  form.append("file", file);
  return request<BackgroundMusic>(
    `/api/projects/${encodeURIComponent(projectId)}/assets/background-music`,
    {
      method: "POST",
      body: form,
    },
  );
}

export function assetPreviewUrl(projectId: string, updatedAt?: string | null): string {
  const query = updatedAt ? `?v=${encodeURIComponent(updatedAt)}` : "";
  return `${API_BASE_URL}/api/projects/${encodeURIComponent(projectId)}/assets/preview${query}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    throw await buildApiError(response);
  }
  return (await response.json()) as T;
}

async function buildApiError(response: Response): Promise<ApiError> {
  let payload: ErrorPayload = {};
  try {
    payload = (await response.json()) as ErrorPayload;
  } catch {
    return new ApiError("请求失败。", response.status, "request_failed");
  }

  return new ApiError(
    localizedErrorMessage(payload.error?.code, payload.error?.message),
    response.status,
    payload.error?.code ?? "request_failed",
    payload.error?.details ?? {},
  );
}

function localizedErrorMessage(code?: string, fallback?: string): string {
  if (code && ERROR_MESSAGES[code]) {
    return ERROR_MESSAGES[code];
  }
  return fallback ?? "请求失败。";
}

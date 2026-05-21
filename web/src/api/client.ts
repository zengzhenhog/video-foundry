import type {
  Asset,
  AssetTextRequest,
  BackgroundMusic,
  DownloadsResponse,
  JobRecord,
  JobSubmitResponse,
  Project,
  ProjectCreateRequest,
  ProjectDetail,
  ProjectListResponse,
  ProjectLogsResponse,
  QualityReport,
  Script,
  ScriptGenerateRequest,
  ScriptUpdateRequest,
  Storyboard,
  StoryboardGenerateRequest,
  StoryboardUpdateRequest,
  SubtitlesManifest,
  VoiceConfig,
  VoiceConfigRequest,
  VoicePresetsResponse,
  VoiceProvidersResponse,
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
  job_metadata_invalid: "任务记录无效。",
  job_not_found: "任务不存在。",
  ffmpeg_assembly_failed: "FFmpeg 合成失败。",
  ffmpeg_not_available: "当前环境找不到 FFmpeg。",
  quality_gate_failed: "导出质量检查未通过。",
  quality_report_invalid: "质量报告无效。",
  quality_report_not_found: "尚未生成质量报告。",
  render_output_not_found: "尚未生成视频文件。",
  render_source_hash_missing: "原图缺少 hash，无法渲染。",
  render_source_image_missing: "缺少原图，无法渲染。",
  script_grounding_missing: "脚本缺少来源约束说明。",
  script_metadata_invalid: "脚本元数据无效。",
  script_narration_required: "脚本文案不能为空。",
  script_not_approved: "请先批准脚本。",
  script_not_found: "尚未生成或保存脚本。",
  script_provider_output_invalid: "脚本生成结果格式无效。",
  script_segments_required: "脚本至少需要一个段落。",
  asset_not_ready_for_script: "请先补齐图片、描述、来源 URL 和署名。",
  download_not_found: "下载文件尚未生成。",
  invalid_download_path: "下载路径无效。",
  needs_script_approval: "脚本已生成，请先审核批准。",
  needs_storyboard_approval: "分镜已生成，请先审核批准。",
  needs_voice_config: "请先保存旁白配置。",
  storyboard_crop_invalid: "分镜裁切坐标无效。",
  storyboard_duration_invalid: "分镜时长无效。",
  storyboard_metadata_invalid: "分镜元数据无效。",
  storyboard_not_found: "尚未生成或保存分镜。",
  storyboard_not_approved: "请先批准分镜。",
  storyboard_shots_required: "分镜至少需要一个镜头。",
  storyboard_timeline_invalid: "分镜时间线必须连续且不重叠。",
  storyboard_zoom_exceeded: "裁切缩放超过当前输出规格限制。",
  subtitle_cues_required: "字幕至少需要一条内容。",
  subtitles_metadata_invalid: "字幕元数据无效。",
  subtitles_not_found: "尚未生成字幕。",
  subtitles_stale_or_missing: "字幕缺失或已过期。",
  unsupported_background_music_format: "不支持该背景音乐格式。",
  unsupported_tts_provider: "不支持或未启用该语音服务。",
  unsupported_image_format: "不支持该图片格式。",
  validation_error: "请求参数校验失败。",
  voice_audio_not_found: "旁白音频尚未生成。",
  voice_config_invalid: "旁白配置无效。",
  voice_config_not_found: "请先保存旁白配置。",
  voice_presets_invalid: "旁白音色配置无效。",
  voice_presets_missing: "旁白音色配置缺失。",
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

export function generateScript(
  projectId: string,
  payload: ScriptGenerateRequest,
): Promise<Script> {
  return request<Script>(`/api/projects/${encodeURIComponent(projectId)}/script/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getScript(projectId: string): Promise<Script> {
  return request<Script>(`/api/projects/${encodeURIComponent(projectId)}/script`);
}

export function saveScript(
  projectId: string,
  payload: ScriptUpdateRequest,
): Promise<Script> {
  return request<Script>(`/api/projects/${encodeURIComponent(projectId)}/script`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function approveScript(projectId: string): Promise<Script> {
  return request<Script>(`/api/projects/${encodeURIComponent(projectId)}/script/approve`, {
    method: "POST",
  });
}

export async function getVoiceProviders() {
  const response = await request<VoiceProvidersResponse>("/api/voice/providers");
  return response.providers;
}

export async function getVoicePresets() {
  const response = await request<VoicePresetsResponse>("/api/voice/presets");
  return response.presets;
}

export function saveVoiceConfig(
  projectId: string,
  payload: VoiceConfigRequest,
): Promise<VoiceConfig> {
  return request<VoiceConfig>(`/api/projects/${encodeURIComponent(projectId)}/voice/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function generateVoice(projectId: string): Promise<VoiceConfig> {
  return request<VoiceConfig>(`/api/projects/${encodeURIComponent(projectId)}/voice/generate`, {
    method: "POST",
  });
}

export function voiceAudioUrl(projectId: string, updatedAt?: string | null): string {
  const query = updatedAt ? `?v=${encodeURIComponent(updatedAt)}` : "";
  return `${API_BASE_URL}/api/projects/${encodeURIComponent(projectId)}/voice/audio${query}`;
}

export function generateStoryboard(
  projectId: string,
  payload: StoryboardGenerateRequest,
): Promise<Storyboard> {
  return request<Storyboard>(`/api/projects/${encodeURIComponent(projectId)}/storyboard/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getStoryboard(projectId: string): Promise<Storyboard> {
  return request<Storyboard>(`/api/projects/${encodeURIComponent(projectId)}/storyboard`);
}

export function saveStoryboard(
  projectId: string,
  payload: StoryboardUpdateRequest,
): Promise<Storyboard> {
  return request<Storyboard>(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function approveStoryboard(projectId: string): Promise<Storyboard> {
  return request<Storyboard>(`/api/projects/${encodeURIComponent(projectId)}/storyboard/approve`, {
    method: "POST",
  });
}

export function generateSubtitles(projectId: string): Promise<SubtitlesManifest> {
  return request<SubtitlesManifest>(
    `/api/projects/${encodeURIComponent(projectId)}/subtitles/generate`,
    {
      method: "POST",
    },
  );
}

export function renderProject(projectId: string): Promise<JobSubmitResponse> {
  return request<JobSubmitResponse>(`/api/projects/${encodeURIComponent(projectId)}/render`, {
    method: "POST",
  });
}

export function exportProject(projectId: string): Promise<JobSubmitResponse> {
  return request<JobSubmitResponse>(`/api/projects/${encodeURIComponent(projectId)}/export`, {
    method: "POST",
  });
}

export function generateAll(projectId: string): Promise<JobSubmitResponse> {
  return request<JobSubmitResponse>(`/api/projects/${encodeURIComponent(projectId)}/generate-all`, {
    method: "POST",
  });
}

export function getJob(jobId: string): Promise<JobRecord> {
  return request<JobRecord>(`/api/jobs/${encodeURIComponent(jobId)}`);
}

export function getProjectLogs(projectId: string): Promise<ProjectLogsResponse> {
  return request<ProjectLogsResponse>(`/api/projects/${encodeURIComponent(projectId)}/logs`);
}

export function getQualityReport(projectId: string): Promise<QualityReport> {
  return request<QualityReport>(`/api/projects/${encodeURIComponent(projectId)}/quality-report`);
}

export function getDownloads(projectId: string): Promise<DownloadsResponse> {
  return request<DownloadsResponse>(`/api/projects/${encodeURIComponent(projectId)}/downloads`);
}

export function downloadFileUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export function renderPreviewUrl(projectId: string, updatedAt?: string | null): string {
  const query = updatedAt ? `?v=${encodeURIComponent(updatedAt)}` : "";
  return `${API_BASE_URL}/api/projects/${encodeURIComponent(projectId)}/render/preview${query}`;
}

export function exportVideoUrl(projectId: string, updatedAt?: string | null): string {
  const query = updatedAt ? `?v=${encodeURIComponent(updatedAt)}` : "";
  return `${API_BASE_URL}/api/projects/${encodeURIComponent(projectId)}/export/video${query}`;
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

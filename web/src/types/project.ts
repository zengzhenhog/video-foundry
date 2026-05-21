export type ProjectStatus =
  | "draft"
  | "asset_ready"
  | "script_ready"
  | "script_approved"
  | "storyboard_ready"
  | "storyboard_approved"
  | "voice_ready"
  | "rendered"
  | "exported"
  | "failed";

export interface Project {
  schema_version: "1.0";
  id: string;
  name: string;
  status: ProjectStatus;
  target_language: string;
  target_duration_sec: number;
  formats: string[];
  created_at: string;
  updated_at: string;
  current_step: string;
  stale_artifacts: Record<string, boolean>;
  metadata: Record<string, unknown>;
}

export interface Asset {
  schema_version: "1.0";
  project_id: string;
  title: string;
  source_url: string | null;
  original_filename: string | null;
  image_original_path: string | null;
  image_preview_path: string | null;
  image_format: string | null;
  description: string;
  credit: string;
  width: number | null;
  height: number | null;
  sha256: string | null;
  created_at: string;
  updated_at: string;
}

export interface BackgroundMusic {
  schema_version: "1.0";
  project_id: string | null;
  file_path: string;
  original_filename: string;
  duration_sec: number | null;
  volume_gain_db: number;
  loop: boolean;
  fade_in_sec: number;
  fade_out_sec: number;
  updated_at: string;
}

export interface VoiceConfig {
  schema_version: "1.0";
  project_id: string | null;
  provider: string;
  voice_id: string;
  language: string;
  speed: number;
  volume_gain_db: number;
  style: string | null;
  settings: Record<string, unknown>;
  audio_path: string | null;
  duration_sec: number | null;
  audio_format: string | null;
  provider_metadata: Record<string, unknown>;
  updated_at: string;
}

export interface VoiceProviderInfo {
  id: string;
  name: string;
  enabled: boolean;
  default: boolean;
}

export interface VoicePreset {
  id: string;
  provider: string;
  name: string;
  language: string;
  style: string | null;
}

export interface VoiceProvidersResponse {
  providers: VoiceProviderInfo[];
}

export interface VoicePresetsResponse {
  presets: VoicePreset[];
}

export interface AssetStatusSummary {
  has_original_image: boolean;
  has_preview_image: boolean;
  has_source_url: boolean;
  has_credit: boolean;
  has_description: boolean;
  has_background_music: boolean;
  ready_for_script: boolean;
}

export interface ProjectDetail extends Project {
  asset: Asset | null;
  background_music: BackgroundMusic | null;
  voice_config: VoiceConfig | null;
  asset_status: AssetStatusSummary;
}

export interface ScriptSegment {
  start_sec: number;
  end_sec: number;
  text: string;
}

export interface Script {
  schema_version: "1.0";
  project_id: string;
  language: string;
  duration_target_sec: number;
  title: string;
  narration: string;
  segments: ScriptSegment[];
  review_notes: string;
  approved: boolean;
  updated_at: string;
  approved_at: string | null;
}

export interface StoryboardShot {
  id: string;
  start_sec: number;
  end_sec: number;
  type: string;
  crop_start: [number, number, number, number];
  crop_end: [number, number, number, number];
  easing: string;
  caption: string;
}

export interface Storyboard {
  schema_version: "1.0";
  project_id: string;
  version: number;
  format: string;
  fps: number;
  duration_sec: number;
  safe_area: Record<string, number>;
  shots: StoryboardShot[];
  approved: boolean;
  updated_at: string;
}

export interface StoryboardGenerateRequest {
  format: string | null;
}

export interface StoryboardUpdateRequest {
  format: string;
  fps: number;
  duration_sec: number;
  safe_area: Record<string, number>;
  shots: StoryboardShot[];
}

export interface SubtitleCue {
  index: number;
  start_sec: number;
  end_sec: number;
  text: string;
}

export interface SubtitlesManifest {
  schema_version: "1.0";
  project_id: string;
  source: "script_segments" | "storyboard";
  storyboard_version: number | null;
  srt_path: string;
  vtt_path: string;
  cues: SubtitleCue[];
  stale: boolean;
  updated_at: string;
}

export interface RenderKeyframe {
  shot_id: string;
  frame_index: number;
  time_sec: number;
  crop: [number, number, number, number];
  output_path: string;
}

export interface RenderManifest {
  schema_version: "1.0";
  project_id: string;
  format: string;
  fps: number;
  width: number;
  height: number;
  duration_sec: number;
  source_image_path: string;
  source_image_sha256: string;
  storyboard_version: number;
  subtitles_path: string;
  credit_text: string;
  credit_overlay: Record<string, number | string>;
  subtitle_overlay: Record<string, number | string>;
  preview_output_path: string | null;
  final_output_path: string | null;
  frame_count: number;
  keyframes: RenderKeyframe[];
  deterministic_rules: string[];
  updated_at: string;
}

export interface ProjectListResponse {
  projects: Project[];
}

export interface ProjectCreateRequest {
  name: string;
  target_language: string;
  target_duration_sec: number;
  formats: string[];
}

export interface AssetTextRequest {
  title: string;
  description: string;
  source_url: string | null;
  credit: string;
}

export interface ScriptGenerateRequest {
  user_draft: string | null;
}

export interface ScriptUpdateRequest {
  language: string;
  duration_target_sec: number;
  title: string;
  narration: string;
  segments: ScriptSegment[];
  review_notes: string;
}

export interface VoiceConfigRequest {
  provider: string;
  voice_id: string;
  language: string;
  speed: number;
  volume_gain_db: number;
  style: string | null;
}

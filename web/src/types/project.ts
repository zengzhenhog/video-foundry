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

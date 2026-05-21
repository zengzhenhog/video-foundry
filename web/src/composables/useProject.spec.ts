import { describe, expect, it } from "vitest";

import type { ProjectDetail, Script, Storyboard } from "../types/project";
import { buildProjectStepSummaries, canSubmitGenerateAll } from "./useProject";

describe("project workflow summaries", () => {
  it("disables generate-all until required asset fields are complete", () => {
    const project = projectDetail({
      asset_status: {
        has_original_image: true,
        has_preview_image: true,
        has_source_url: true,
        has_credit: false,
        has_description: true,
        has_background_music: false,
        ready_for_script: false,
      },
    });

    expect(canSubmitGenerateAll(project, false)).toBe(false);
    expect(buildProjectStepSummaries(project)[0].missing).toContain("署名");
  });

  it("summarizes approval gates and export readiness from persisted API state", () => {
    const project = projectDetail({
      status: "exported",
      voice_config: {
        schema_version: "1.0",
        project_id: "prj_1",
        provider: "mock",
        voice_id: "mock-narrator",
        language: "zh-CN",
        speed: 1,
        volume_gain_db: 0,
        style: "clear",
        settings: {},
        audio_path: "audio/narration.wav",
        duration_sec: 20,
        audio_format: "wav",
        provider_metadata: {},
        updated_at: "2026-05-21T00:00:00Z",
      },
    });
    const summaries = buildProjectStepSummaries(project, {
      script: script({ approved: true }),
      storyboard: storyboard({ approved: true }),
      downloads: {
        project_id: "prj_1",
        files: [
          {
            kind: "video",
            label: "Final MP4",
            path: "exports/final_vertical_1080x1920.mp4",
            url: "/api/projects/prj_1/downloads/file/exports/final_vertical_1080x1920.mp4",
            media_type: "video/mp4",
            size_bytes: 12,
          },
        ],
        missing: [],
      },
    });

    expect(canSubmitGenerateAll(project, false)).toBe(true);
    expect(summaries.find((step) => step.key === "script")?.status).toBe("已批准");
    expect(summaries.find((step) => step.key === "storyboard")?.status).toBe("已批准");
    expect(summaries.find((step) => step.key === "export")?.ready).toBe(true);
  });
});

function projectDetail(overrides: Partial<ProjectDetail> = {}): ProjectDetail {
  return {
    schema_version: "1.0",
    id: "prj_1",
    name: "Demo",
    status: "asset_ready",
    target_language: "zh-CN",
    target_duration_sec: 20,
    formats: ["vertical_1080x1920"],
    created_at: "2026-05-21T00:00:00Z",
    updated_at: "2026-05-21T00:00:00Z",
    current_step: "assets_ready",
    stale_artifacts: {},
    metadata: {},
    asset: null,
    background_music: null,
    voice_config: null,
    asset_status: {
      has_original_image: true,
      has_preview_image: true,
      has_source_url: true,
      has_credit: true,
      has_description: true,
      has_background_music: false,
      ready_for_script: true,
    },
    ...overrides,
  };
}

function script(overrides: Partial<Script> = {}): Script {
  return {
    schema_version: "1.0",
    project_id: "prj_1",
    language: "zh-CN",
    duration_target_sec: 20,
    title: "Demo",
    narration: "Narration.",
    segments: [{ start_sec: 0, end_sec: 20, text: "Narration." }],
    review_notes: "Grounded in saved source metadata.",
    approved: false,
    updated_at: "2026-05-21T00:00:00Z",
    approved_at: null,
    ...overrides,
  };
}

function storyboard(overrides: Partial<Storyboard> = {}): Storyboard {
  return {
    schema_version: "1.0",
    project_id: "prj_1",
    version: 1,
    format: "vertical_1080x1920",
    fps: 30,
    duration_sec: 20,
    safe_area: { top: 0.08, right: 0.06, bottom: 0.12, left: 0.06 },
    shots: [
      {
        id: "shot_001",
        start_sec: 0,
        end_sec: 20,
        type: "push_in",
        crop_start: [0, 0, 1, 1],
        crop_end: [0.02, 0.02, 0.98, 0.98],
        easing: "ease_in_out",
        caption: "Narration.",
      },
    ],
    approved: false,
    updated_at: "2026-05-21T00:00:00Z",
    ...overrides,
  };
}

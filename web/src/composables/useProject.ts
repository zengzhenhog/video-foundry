import { ref } from "vue";

import { ApiError, getProject } from "../api/client";
import type { DownloadsResponse, ProjectDetail, Script, Storyboard } from "../types/project";

export type WorkflowStepKey = "assets" | "script" | "voice" | "storyboard" | "render" | "export";

export interface WorkflowStepSummary {
  key: WorkflowStepKey;
  label: string;
  status: string;
  ready: boolean;
  missing: string[];
  actionLabel: string;
  to: string;
}

interface ProjectArtifacts {
  script?: Script | null;
  storyboard?: Storyboard | null;
  downloads?: DownloadsResponse | null;
}

export function useProject(projectId: string) {
  const project = ref<ProjectDetail | null>(null);
  const isLoading = ref(false);
  const error = ref("");

  async function loadProject(): Promise<void> {
    isLoading.value = true;
    error.value = "";
    try {
      project.value = await getProject(projectId);
    } catch (caught) {
      error.value = caught instanceof ApiError ? caught.message : "无法加载项目。";
    } finally {
      isLoading.value = false;
    }
  }

  return {
    project,
    isLoading,
    error,
    loadProject,
  };
}

export function canSubmitGenerateAll(project: ProjectDetail | null, isBusy: boolean): boolean {
  return Boolean(project?.asset_status.ready_for_script && !isBusy);
}

export function buildProjectStepSummaries(
  project: ProjectDetail,
  artifacts: ProjectArtifacts = {},
): WorkflowStepSummary[] {
  const projectBase = `/projects/${project.id}`;
  const scriptExists = Boolean(artifacts.script) || statusAtLeast(project.status, "script_ready");
  const scriptApproved = Boolean(artifacts.script?.approved && !project.stale_artifacts.script);
  const voiceReady = Boolean(project.voice_config?.audio_path && !project.stale_artifacts.voice);
  const storyboardExists =
    Boolean(artifacts.storyboard) ||
    ["storyboard_ready", "storyboard_approved", "rendered", "exported"].includes(project.status);
  const storyboardApproved = Boolean(artifacts.storyboard?.approved && !project.stale_artifacts.storyboard);
  const hasFinalVideo = Boolean(
    artifacts.downloads?.files.some((file) => file.kind === "video" && file.path.startsWith("exports/")),
  );
  const renderReady = Boolean((statusAtLeast(project.status, "rendered") || hasFinalVideo) && !project.stale_artifacts.render);
  const exportReady = Boolean((project.status === "exported" || hasFinalVideo) && !project.stale_artifacts.export);

  return [
    {
      key: "assets",
      label: "素材",
      status: project.asset_status.ready_for_script ? "已就绪" : "待补齐",
      ready: project.asset_status.ready_for_script,
      missing: missingAssets(project),
      actionLabel: project.asset_status.ready_for_script ? "查看素材" : "补齐素材",
      to: `${projectBase}/assets`,
    },
    {
      key: "script",
      label: "脚本",
      status: scriptApproved ? "已批准" : scriptExists ? "待审核" : "待生成",
      ready: scriptApproved,
      missing: scriptApproved ? [] : [scriptExists ? "批准脚本" : "生成脚本"],
      actionLabel: scriptApproved ? "查看脚本" : "审核脚本",
      to: `${projectBase}/script`,
    },
    {
      key: "voice",
      label: "旁白",
      status: voiceReady ? "已生成" : project.voice_config ? "待生成" : "待配置",
      ready: voiceReady,
      missing: voiceReady ? [] : [project.voice_config ? "生成旁白音频" : "保存旁白配置"],
      actionLabel: voiceReady ? "试听旁白" : "配置旁白",
      to: `${projectBase}/voice`,
    },
    {
      key: "storyboard",
      label: "分镜",
      status: storyboardApproved ? "已批准" : storyboardExists ? "待审核" : "待生成",
      ready: storyboardApproved,
      missing: storyboardApproved ? missingSubtitles(project) : [storyboardExists ? "批准分镜" : "生成分镜"],
      actionLabel: storyboardApproved ? "查看分镜" : "审核分镜",
      to: `${projectBase}/storyboard`,
    },
    {
      key: "render",
      label: "渲染",
      status: renderReady ? "已渲染" : "待渲染",
      ready: renderReady,
      missing: renderReady ? [] : missingRenderInputs(scriptApproved, voiceReady, storyboardApproved, project),
      actionLabel: renderReady ? "查看预览" : "生成预览",
      to: `${projectBase}/render`,
    },
    {
      key: "export",
      label: "导出",
      status: exportReady ? "已导出" : "待导出",
      ready: exportReady,
      missing: exportReady ? [] : missingExportInputs(renderReady, project),
      actionLabel: exportReady ? "下载文件" : "打开导出",
      to: `${projectBase}/export`,
    },
  ];
}

function missingAssets(project: ProjectDetail): string[] {
  const missing: string[] = [];
  if (!project.asset_status.has_original_image) {
    missing.push("图片");
  }
  if (!project.asset_status.has_description) {
    missing.push("描述");
  }
  if (!project.asset_status.has_source_url) {
    missing.push("来源 URL");
  }
  if (!project.asset_status.has_credit) {
    missing.push("署名");
  }
  return missing;
}

function missingSubtitles(project: ProjectDetail): string[] {
  return project.stale_artifacts.subtitles ? ["重新生成字幕"] : [];
}

function missingRenderInputs(
  scriptApproved: boolean,
  voiceReady: boolean,
  storyboardApproved: boolean,
  project: ProjectDetail,
): string[] {
  const missing: string[] = [];
  if (!scriptApproved) {
    missing.push("批准脚本");
  }
  if (!voiceReady) {
    missing.push("生成旁白");
  }
  if (!storyboardApproved) {
    missing.push("批准分镜");
  }
  if (project.stale_artifacts.subtitles) {
    missing.push("重新生成字幕");
  }
  return missing.length ? missing : ["生成渲染产物"];
}

function missingExportInputs(renderReady: boolean, project: ProjectDetail): string[] {
  if (project.stale_artifacts.export) {
    return ["重新导出"];
  }
  return renderReady ? ["运行质量门禁"] : ["完成渲染"];
}

function statusAtLeast(status: ProjectDetail["status"], threshold: ProjectDetail["status"]): boolean {
  const order: ProjectDetail["status"][] = [
    "draft",
    "asset_ready",
    "script_ready",
    "script_approved",
    "storyboard_ready",
    "storyboard_approved",
    "voice_ready",
    "rendered",
    "exported",
  ];
  const currentIndex = order.indexOf(status);
  const thresholdIndex = order.indexOf(threshold);
  return currentIndex >= thresholdIndex && thresholdIndex >= 0;
}

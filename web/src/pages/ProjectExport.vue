<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  ApiError,
  exportProject,
  exportVideoUrl,
  generateAll,
  getDownloads,
  getQualityReport,
} from "../api/client";
import DownloadLinks from "../components/DownloadLinks.vue";
import JobStatusPanel from "../components/JobStatusPanel.vue";
import QualityReportPanel from "../components/QualityReportPanel.vue";
import StepNavigation from "../components/StepNavigation.vue";
import VideoPreview from "../components/VideoPreview.vue";
import { canSubmitGenerateAll, useProject } from "../composables/useProject";
import { useJobPolling } from "../composables/useJobPolling";
import type { DownloadsResponse, JobRecord, ProjectStatus, QualityReport } from "../types/project";

const props = defineProps<{
  id: string;
}>();

const { project, isLoading: isProjectLoading, error: projectError, loadProject } = useProject(props.id);
const qualityReport = ref<QualityReport | null>(null);
const downloads = ref<DownloadsResponse | null>(null);
const isQualityLoading = ref(false);
const isDownloadsLoading = ref(false);
const qualityError = ref("");
const downloadsError = ref("");
const activeJobType = ref<string | null>(null);
const finalVersion = ref<string | null>(null);
const actionMessage = ref("");
const actionError = ref("");

const { job, error: jobPollingError, isPolling, start: startJobPolling } = useJobPolling({
  onFinished: handleJobFinished,
});

const statusLabels: Record<ProjectStatus, string> = {
  draft: "草稿",
  asset_ready: "素材就绪",
  script_ready: "脚本就绪",
  script_approved: "脚本已批准",
  storyboard_ready: "分镜就绪",
  storyboard_approved: "分镜已批准",
  voice_ready: "旁白就绪",
  rendered: "已渲染",
  exported: "已导出",
  failed: "失败",
};

const isBusy = computed(
  () => isProjectLoading.value || isQualityLoading.value || isDownloadsLoading.value || isPolling.value,
);
const canContinue = computed(() => canSubmitGenerateAll(project.value, isBusy.value));
const canExport = computed(() => Boolean(project.value?.asset_status.ready_for_script && !isBusy.value));
const isGenerateAllJob = computed(() => isPolling.value && activeJobType.value === "generate_all");
const isExporting = computed(() => isPolling.value && activeJobType.value === "export_final");
const hasFinalDownload = computed(() =>
  Boolean(downloads.value?.files.some((file) => file.kind === "video" && file.path.startsWith("exports/"))),
);
const finalSource = computed(() =>
  hasFinalDownload.value || project.value?.status === "exported"
    ? exportVideoUrl(props.id, finalVersion.value ?? project.value?.updated_at)
    : "",
);

onMounted(refreshPage);

async function refreshPage(): Promise<void> {
  await loadProject();
  await Promise.all([loadQualityReport(), loadDownloads()]);
}

async function continuePipeline(): Promise<void> {
  actionMessage.value = "";
  actionError.value = "";
  try {
    const response = await generateAll(props.id);
    activeJobType.value = response.job.type;
    actionMessage.value = "一键生成任务已提交。";
    await startJobPolling(response.job_id, response.job);
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "一键生成失败。";
  }
}

async function exportFinal(): Promise<void> {
  actionMessage.value = "";
  actionError.value = "";
  try {
    const response = await exportProject(props.id);
    activeJobType.value = response.job.type;
    actionMessage.value = "导出任务已提交。";
    await startJobPolling(response.job_id, response.job);
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "导出失败。";
  }
}

async function handleJobFinished(doneJob: JobRecord): Promise<void> {
  await refreshPage();
  if (doneJob.status === "succeeded") {
    finalVersion.value = doneJob.updated_at;
    actionMessage.value = doneJob.type === "generate_all" ? "主流程已推进完成。" : "最终视频已导出。";
    return;
  }
  if (doneJob.status === "blocked") {
    actionMessage.value = doneJob.error?.reason ?? "流程需要人工处理后继续。";
    return;
  }
  if (doneJob.status === "failed") {
    actionError.value = doneJob.error?.reason ?? "任务失败。";
  }
}

async function retryLastJob(): Promise<void> {
  if (job.value?.type === "export_final") {
    await exportFinal();
    return;
  }
  await continuePipeline();
}

async function loadQualityReport(): Promise<void> {
  isQualityLoading.value = true;
  qualityError.value = "";
  try {
    qualityReport.value = await getQualityReport(props.id);
  } catch (caught) {
    if (caught instanceof ApiError && caught.code === "quality_report_not_found") {
      qualityReport.value = null;
    } else {
      qualityError.value = caught instanceof ApiError ? caught.message : "质量报告读取失败。";
    }
  } finally {
    isQualityLoading.value = false;
  }
}

async function loadDownloads(): Promise<void> {
  isDownloadsLoading.value = true;
  downloadsError.value = "";
  try {
    downloads.value = await getDownloads(props.id);
  } catch (caught) {
    downloadsError.value = caught instanceof ApiError ? caught.message : "下载列表读取失败。";
  } finally {
    isDownloadsLoading.value = false;
  }
}
</script>

<template>
  <main class="page-stack">
    <StepNavigation :project-id="id" current="export" />

    <p v-if="projectError" class="form-message form-message--error">{{ projectError }}</p>
    <p v-else-if="isProjectLoading" class="muted">正在加载导出状态...</p>

    <template v-else-if="project">
      <section class="page-header">
        <div>
          <p class="eyebrow">导出</p>
          <h1>{{ project.name }}</h1>
        </div>
        <span class="status-pill" :class="{ 'status-pill--ok': project.status === 'exported' }">
          {{ statusLabels[project.status] }}
        </span>
      </section>

      <div class="script-actions">
        <button class="button button--primary" type="button" :disabled="!canContinue" @click="continuePipeline">
          {{ isGenerateAllJob ? "正在推进..." : "一键生成 / 继续" }}
        </button>
        <button class="button" type="button" :disabled="!canExport" @click="exportFinal">
          {{ isExporting ? "正在导出..." : "重新导出" }}
        </button>
      </div>

      <p v-if="!project.asset_status.ready_for_script" class="form-message form-message--error">
        请先补齐图片、描述、来源 URL 和署名。
      </p>
      <p v-if="actionMessage" class="form-message form-message--success">{{ actionMessage }}</p>
      <p v-if="actionError" class="form-message form-message--error">{{ actionError }}</p>
      <p v-if="jobPollingError" class="form-message form-message--error">{{ jobPollingError }}</p>

      <VideoPreview :src="finalSource" label="最终 MP4" />
      <QualityReportPanel :report="qualityReport" :is-loading="isQualityLoading" :error="qualityError" />
      <DownloadLinks :downloads="downloads" :is-loading="isDownloadsLoading" :error="downloadsError" />
      <JobStatusPanel :job="job" :is-polling="isPolling" @retry="retryLastJob" />
    </template>
  </main>
</template>

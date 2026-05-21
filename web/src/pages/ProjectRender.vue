<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  ApiError,
  exportProject,
  exportVideoUrl,
  getProjectLogs,
  getQualityReport,
  renderPreviewUrl,
  renderProject,
} from "../api/client";
import JobStatusPanel from "../components/JobStatusPanel.vue";
import QualityReportPanel from "../components/QualityReportPanel.vue";
import StepNavigation from "../components/StepNavigation.vue";
import VideoPreview from "../components/VideoPreview.vue";
import { useJobPolling } from "../composables/useJobPolling";
import { useProject } from "../composables/useProject";
import type { JobRecord, ProjectLogsResponse, ProjectStatus, QualityReport } from "../types/project";

const props = defineProps<{
  id: string;
}>();

const { project, isLoading: isProjectLoading, error: projectError, loadProject } = useProject(props.id);
const qualityReport = ref<QualityReport | null>(null);
const logs = ref<ProjectLogsResponse | null>(null);
const isQualityLoading = ref(false);
const qualityError = ref("");
const activeJobType = ref<string | null>(null);
const previewVersion = ref<string | null>(null);
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

const isBusy = computed(() => isProjectLoading.value || isPolling.value);
const hasApprovedStoryboard = computed(() =>
  Boolean(
    project.value
      && ["storyboard_approved", "voice_ready", "rendered", "exported", "failed"].includes(project.value.status),
  ),
);
const hasVoice = computed(() => Boolean(project.value?.voice_config?.audio_path));
const hasCredit = computed(() => Boolean(project.value?.asset?.credit?.trim()));
const hasRenderStale = computed(() => Boolean(project.value?.stale_artifacts.render));
const canRender = computed(() => !isBusy.value && hasApprovedStoryboard.value && hasVoice.value && hasCredit.value);
const isRendering = computed(() => isPolling.value && activeJobType.value === "render_preview");
const isExporting = computed(() => isPolling.value && activeJobType.value === "export_final");
const hasPreviewOutput = computed(() =>
  Boolean(previewVersion.value || (project.value && ["rendered", "exported"].includes(project.value.status))),
);
const hasFinalOutput = computed(() => Boolean(finalVersion.value || project.value?.status === "exported"));
const previewSource = computed(() =>
  hasPreviewOutput.value ? renderPreviewUrl(props.id, previewVersion.value ?? project.value?.updated_at) : "",
);
const finalSource = computed(() =>
  hasFinalOutput.value ? exportVideoUrl(props.id, finalVersion.value ?? project.value?.updated_at) : "",
);
const recentLogEntries = computed(() => logs.value?.entries.slice(-6).reverse() ?? []);

onMounted(async () => {
  await loadProject();
  await Promise.all([loadLogs(), loadQualityReport()]);
});

async function renderPreview(): Promise<void> {
  actionMessage.value = "";
  actionError.value = "";
  try {
    const response = await renderProject(props.id);
    activeJobType.value = response.job.type;
    actionMessage.value = "预览任务已提交。";
    await startJobPolling(response.job_id, response.job);
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "渲染失败。";
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
  await Promise.all([loadProject(), loadLogs()]);
  if (doneJob.status === "succeeded") {
    if (doneJob.type === "render_preview") {
      previewVersion.value = doneJob.updated_at;
      actionMessage.value = "预览视频已生成。";
    }
    if (doneJob.type === "export_final") {
      finalVersion.value = doneJob.updated_at;
      actionMessage.value = "最终视频已导出。";
      await loadQualityReport();
    }
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
  await renderPreview();
}

async function loadLogs(): Promise<void> {
  try {
    logs.value = await getProjectLogs(props.id);
  } catch {
    logs.value = null;
  }
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
</script>

<template>
  <main class="page-stack">
    <StepNavigation :project-id="id" current="render" />

    <p v-if="projectError" class="form-message form-message--error">{{ projectError }}</p>
    <p v-else-if="isProjectLoading" class="muted">正在加载渲染状态...</p>

    <template v-else-if="project">
      <section class="page-header">
        <div>
          <p class="eyebrow">渲染</p>
          <h1>{{ project.name }}</h1>
        </div>
        <span class="status-pill" :class="{ 'status-pill--ok': project.status === 'rendered' || project.status === 'exported' }">
          {{ statusLabels[project.status] }}
        </span>
      </section>

      <section class="panel">
        <div class="panel__header">
          <div>
            <p class="eyebrow">输入检查</p>
            <h2>{{ canRender ? "可以渲染" : "等待上游产物" }}</h2>
          </div>
        </div>
        <dl class="status-grid status-grid--wide">
          <div>
            <dt>分镜</dt>
            <dd>{{ hasApprovedStoryboard ? "已批准" : "待批准" }}</dd>
          </div>
          <div>
            <dt>旁白</dt>
            <dd>{{ hasVoice ? "已生成" : "缺失" }}</dd>
          </div>
          <div>
            <dt>Credit</dt>
            <dd>{{ hasCredit ? "已保存" : "缺失" }}</dd>
          </div>
          <div>
            <dt>Render</dt>
            <dd>{{ hasRenderStale ? "已过期" : "当前" }}</dd>
          </div>
        </dl>
      </section>

      <div class="script-actions">
        <button class="button button--primary" type="button" :disabled="!canRender" @click="renderPreview">
          {{ isRendering ? "正在渲染..." : "生成预览" }}
        </button>
        <button class="button" type="button" :disabled="!canRender" @click="exportFinal">
          {{ isExporting ? "正在导出..." : "导出最终视频" }}
        </button>
      </div>

      <p v-if="!canRender" class="form-message form-message--error">
        请先完成原图、credit、已批准分镜、字幕和旁白音频。
      </p>
      <p v-if="actionMessage" class="form-message form-message--success">{{ actionMessage }}</p>
      <p v-if="actionError" class="form-message form-message--error">{{ actionError }}</p>
      <p v-if="jobPollingError" class="form-message form-message--error">{{ jobPollingError }}</p>

      <JobStatusPanel :job="job" :is-polling="isPolling" @retry="retryLastJob" />

      <QualityReportPanel :report="qualityReport" :is-loading="isQualityLoading" :error="qualityError" />

      <section class="panel">
        <div class="panel__header">
          <div>
            <p class="eyebrow">日志</p>
            <h2>{{ logs?.error ? "最近失败" : "Pipeline" }}</h2>
          </div>
        </div>
        <p v-if="logs?.error" class="form-message form-message--error">
          {{ logs.error.step }}：{{ logs.error.reason }}
        </p>
        <ul v-if="recentLogEntries.length" class="log-list">
          <li v-for="entry in recentLogEntries" :key="`${entry.timestamp}-${entry.step}-${entry.summary}`">
            <span>{{ new Date(entry.timestamp).toLocaleTimeString() }}</span>
            <strong>{{ entry.step }}</strong>
            <em>{{ entry.status }}</em>
            <p>{{ entry.summary }}</p>
          </li>
        </ul>
        <p v-else class="muted">暂无日志。</p>
      </section>

      <div class="render-videos">
        <VideoPreview :src="previewSource" label="预览视频" />
        <VideoPreview :src="finalSource" label="最终视频" />
      </div>
    </template>
  </main>
</template>

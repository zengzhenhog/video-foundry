<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  ApiError,
  generateAll,
  getDownloads,
  getProjectLogs,
  getScript,
  getStoryboard,
} from "../api/client";
import JobStatusPanel from "../components/JobStatusPanel.vue";
import StepNavigation from "../components/StepNavigation.vue";
import {
  buildProjectStepSummaries,
  canSubmitGenerateAll,
  useProject,
} from "../composables/useProject";
import { useJobPolling } from "../composables/useJobPolling";
import type {
  DownloadsResponse,
  JobRecord,
  ProjectLogsResponse,
  ProjectStatus,
  Script,
  Storyboard,
} from "../types/project";

const props = defineProps<{
  id: string;
}>();

const { project, isLoading: isProjectLoading, error: projectError, loadProject } = useProject(props.id);
const script = ref<Script | null>(null);
const storyboard = ref<Storyboard | null>(null);
const downloads = ref<DownloadsResponse | null>(null);
const logs = ref<ProjectLogsResponse | null>(null);
const isSnapshotLoading = ref(false);
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

const isBusy = computed(() => isProjectLoading.value || isSnapshotLoading.value || isPolling.value);
const canGenerateAll = computed(() => canSubmitGenerateAll(project.value, isBusy.value));
const stepSummaries = computed(() =>
  project.value ? buildProjectStepSummaries(project.value, { script: script.value, storyboard: storyboard.value, downloads: downloads.value }) : [],
);
const recentLogEntries = computed(() => logs.value?.entries.slice(-5).reverse() ?? []);
const completedCount = computed(() => stepSummaries.value.filter((step) => step.ready).length);

onMounted(refreshPage);

async function refreshPage(): Promise<void> {
  await loadProject();
  await Promise.all([loadArtifacts(), loadDownloads(), loadLogs()]);
}

async function loadArtifacts(): Promise<void> {
  isSnapshotLoading.value = true;
  try {
    const [nextScript, nextStoryboard] = await Promise.all([
      readOptional(() => getScript(props.id), "script_not_found"),
      readOptional(() => getStoryboard(props.id), "storyboard_not_found"),
    ]);
    script.value = nextScript;
    storyboard.value = nextStoryboard;
  } finally {
    isSnapshotLoading.value = false;
  }
}

async function loadDownloads(): Promise<void> {
  try {
    downloads.value = await getDownloads(props.id);
  } catch {
    downloads.value = null;
  }
}

async function loadLogs(): Promise<void> {
  try {
    logs.value = await getProjectLogs(props.id);
  } catch {
    logs.value = null;
  }
}

async function startGenerateAll(): Promise<void> {
  actionMessage.value = "";
  actionError.value = "";
  try {
    const response = await generateAll(props.id);
    actionMessage.value = "一键生成任务已提交。";
    await startJobPolling(response.job_id, response.job);
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "一键生成失败。";
  }
}

async function handleJobFinished(doneJob: JobRecord): Promise<void> {
  await refreshPage();
  if (doneJob.status === "succeeded") {
    actionMessage.value = "主流程已推进完成。";
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

async function retryGenerateAll(): Promise<void> {
  await startGenerateAll();
}

async function readOptional<T>(reader: () => Promise<T>, notFoundCode: string): Promise<T | null> {
  try {
    return await reader();
  } catch (caught) {
    if (caught instanceof ApiError && caught.code === notFoundCode) {
      return null;
    }
    throw caught;
  }
}
</script>

<template>
  <main class="page-stack">
    <StepNavigation :project-id="id" current="detail" />

    <p v-if="projectError" class="form-message form-message--error">{{ projectError }}</p>
    <p v-else-if="isProjectLoading" class="muted">正在加载控制台...</p>

    <template v-else-if="project">
      <section class="page-header">
        <div>
          <p class="eyebrow">控制台</p>
          <h1>{{ project.name }}</h1>
        </div>
        <span class="status-pill" :class="{ 'status-pill--ok': project.status === 'exported' }">
          {{ statusLabels[project.status] }}
        </span>
      </section>

      <section class="panel">
        <div class="panel__header">
          <div>
            <p class="eyebrow">主流程</p>
            <h2>{{ completedCount }} / {{ stepSummaries.length }} 步完成</h2>
          </div>
          <button class="button button--primary" type="button" :disabled="!canGenerateAll" @click="startGenerateAll">
            {{ isPolling ? "正在推进..." : "一键生成 / 继续" }}
          </button>
        </div>
        <p v-if="!project.asset_status.ready_for_script" class="form-message form-message--error">
          请先补齐图片、描述、来源 URL 和署名，然后再启动一键生成。
        </p>
        <p v-if="actionMessage" class="form-message form-message--success">{{ actionMessage }}</p>
        <p v-if="actionError" class="form-message form-message--error">{{ actionError }}</p>
        <p v-if="jobPollingError" class="form-message form-message--error">{{ jobPollingError }}</p>
      </section>

      <section class="workflow-grid">
        <article
          v-for="step in stepSummaries"
          :key="step.key"
          class="workflow-step"
          :class="{ 'workflow-step--ready': step.ready }"
        >
          <div class="panel__header">
            <div>
              <p class="eyebrow">{{ step.label }}</p>
              <h2>{{ step.status }}</h2>
            </div>
            <span class="status-pill" :class="{ 'status-pill--ok': step.ready }">
              {{ step.ready ? "完成" : "待处理" }}
            </span>
          </div>
          <ul v-if="step.missing.length" class="missing-list">
            <li v-for="item in step.missing" :key="item">{{ item }}</li>
          </ul>
          <p v-else class="muted">当前步骤可继续向后推进。</p>
          <RouterLink class="button" :to="step.to">{{ step.actionLabel }}</RouterLink>
        </article>
      </section>

      <JobStatusPanel :job="job" :is-polling="isPolling" @retry="retryGenerateAll" />

      <section class="panel">
        <div class="panel__header">
          <div>
            <p class="eyebrow">最近日志</p>
            <h2>{{ logs?.error ? "有失败诊断" : "Pipeline" }}</h2>
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
    </template>
  </main>
</template>

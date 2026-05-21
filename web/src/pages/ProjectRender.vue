<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  ApiError,
  exportProject,
  exportVideoUrl,
  renderPreviewUrl,
  renderProject,
} from "../api/client";
import StepNavigation from "../components/StepNavigation.vue";
import VideoPreview from "../components/VideoPreview.vue";
import { useProject } from "../composables/useProject";
import type { ProjectStatus, RenderManifest } from "../types/project";

const props = defineProps<{
  id: string;
}>();

const { project, isLoading: isProjectLoading, error: projectError, loadProject } = useProject(props.id);
const manifest = ref<RenderManifest | null>(null);
const isRendering = ref(false);
const isExporting = ref(false);
const actionMessage = ref("");
const actionError = ref("");

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

const isBusy = computed(() => isProjectLoading.value || isRendering.value || isExporting.value);
const hasApprovedStoryboard = computed(() =>
  Boolean(project.value && ["storyboard_approved", "voice_ready", "rendered", "exported"].includes(project.value.status)),
);
const hasVoice = computed(() => Boolean(project.value?.voice_config?.audio_path));
const hasCredit = computed(() => Boolean(project.value?.asset?.credit?.trim()));
const hasRenderStale = computed(() => Boolean(project.value?.stale_artifacts.render));
const canRender = computed(() => !isBusy.value && hasApprovedStoryboard.value && hasVoice.value && hasCredit.value);
const previewSource = computed(() =>
  manifest.value?.preview_output_path ? renderPreviewUrl(props.id, manifest.value.updated_at) : "",
);
const finalSource = computed(() =>
  manifest.value?.final_output_path ? exportVideoUrl(props.id, manifest.value.updated_at) : "",
);

onMounted(loadProject);

async function renderPreview(): Promise<void> {
  isRendering.value = true;
  actionMessage.value = "";
  actionError.value = "";
  try {
    manifest.value = await renderProject(props.id);
    await loadProject();
    actionMessage.value = "预览视频已生成。";
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "渲染失败。";
  } finally {
    isRendering.value = false;
  }
}

async function exportFinal(): Promise<void> {
  isExporting.value = true;
  actionMessage.value = "";
  actionError.value = "";
  try {
    manifest.value = await exportProject(props.id);
    await loadProject();
    actionMessage.value = "最终视频已导出。";
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "导出失败。";
  } finally {
    isExporting.value = false;
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

      <section v-if="manifest" class="panel">
        <div class="panel__header">
          <div>
            <p class="eyebrow">Manifest</p>
            <h2>{{ manifest.format }}</h2>
          </div>
        </div>
        <dl class="status-grid status-grid--wide">
          <div>
            <dt>尺寸</dt>
            <dd>{{ manifest.width }} x {{ manifest.height }}</dd>
          </div>
          <div>
            <dt>帧数</dt>
            <dd>{{ manifest.frame_count }}</dd>
          </div>
          <div>
            <dt>Storyboard</dt>
            <dd>v{{ manifest.storyboard_version }}</dd>
          </div>
          <div>
            <dt>Credit</dt>
            <dd>{{ manifest.credit_text }}</dd>
          </div>
        </dl>
      </section>

      <div class="render-videos">
        <VideoPreview :src="previewSource" label="预览视频" />
        <VideoPreview :src="finalSource" label="最终视频" />
      </div>
    </template>
  </main>
</template>

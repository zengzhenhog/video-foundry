<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";

import {
  ApiError,
  approveStoryboard,
  assetPreviewUrl,
  generateStoryboard,
  generateSubtitles,
  getStoryboard,
  saveStoryboard,
} from "../api/client";
import CropPreview from "../components/CropPreview.vue";
import StepNavigation from "../components/StepNavigation.vue";
import StoryboardShotList from "../components/StoryboardShotList.vue";
import { useProject } from "../composables/useProject";
import type {
  ProjectStatus,
  Storyboard,
  StoryboardShot,
  StoryboardUpdateRequest,
  SubtitlesManifest,
} from "../types/project";

const props = defineProps<{
  id: string;
}>();

interface StoryboardDraft {
  format: string;
  fps: number;
  duration_sec: number;
  safe_area: Record<string, number>;
  shots: StoryboardShot[];
}

const { project, isLoading: isProjectLoading, error: projectError, loadProject } = useProject(props.id);
const storyboard = ref<Storyboard | null>(null);
const subtitles = ref<SubtitlesManifest | null>(null);
const selectedShotIndex = ref(0);
const isStoryboardLoading = ref(true);
const isGenerating = ref(false);
const isSaving = ref(false);
const isApproving = ref(false);
const isGeneratingSubtitles = ref(false);
const actionMessage = ref("");
const actionError = ref("");

const draft = reactive<StoryboardDraft>({
  format: "vertical_1080x1920",
  fps: 30,
  duration_sec: 60,
  safe_area: { top: 0.08, right: 0.06, bottom: 0.12, left: 0.06 },
  shots: [],
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
  () =>
    isProjectLoading.value ||
    isStoryboardLoading.value ||
    isGenerating.value ||
    isSaving.value ||
    isApproving.value ||
    isGeneratingSubtitles.value,
);
const hasApprovedScript = computed(() =>
  Boolean(
    project.value &&
      ["script_approved", "storyboard_ready", "storyboard_approved", "voice_ready", "rendered", "exported"].includes(
        project.value.status,
      ),
  ),
);
const canSave = computed(() => !isBusy.value && draft.shots.length > 0);
const canApprove = computed(() => canSave.value);
const canGenerateSubtitles = computed(
  () => !isBusy.value && Boolean(storyboard.value?.approved) && !project.value?.stale_artifacts.storyboard,
);
const isStoryboardStale = computed(() => Boolean(project.value?.stale_artifacts.storyboard));
const isSubtitlesStale = computed(() => Boolean(project.value?.stale_artifacts.subtitles));
const previewSource = computed(() =>
  project.value?.asset?.image_preview_path ? assetPreviewUrl(props.id, project.value.asset.updated_at) : "",
);
const selectedShot = computed(() => draft.shots[selectedShotIndex.value] ?? null);

watch(
  () => draft.shots.length,
  (shotCount) => {
    if (shotCount === 0) {
      selectedShotIndex.value = 0;
      return;
    }
    if (selectedShotIndex.value >= shotCount) {
      selectedShotIndex.value = shotCount - 1;
    }
  },
);

onMounted(refreshPage);

async function refreshPage(): Promise<void> {
  isStoryboardLoading.value = true;
  actionError.value = "";
  try {
    await loadProject();
    applyProjectDefaults();
    await loadExistingStoryboard();
  } finally {
    isStoryboardLoading.value = false;
  }
}

async function loadExistingStoryboard(): Promise<void> {
  try {
    const saved = await getStoryboard(props.id);
    storyboard.value = saved;
    applyStoryboard(saved);
  } catch (caught) {
    if (caught instanceof ApiError && caught.code === "storyboard_not_found") {
      storyboard.value = null;
    } else {
      actionError.value = caught instanceof ApiError ? caught.message : "无法加载分镜。";
    }
  }
}

async function generateCurrentStoryboard(): Promise<void> {
  isGenerating.value = true;
  actionMessage.value = "";
  actionError.value = "";
  try {
    const generated = await generateStoryboard(props.id, { format: project.value?.formats[0] ?? null });
    storyboard.value = generated;
    applyStoryboard(generated);
    await loadProject();
    actionMessage.value = "分镜已生成。";
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "分镜生成失败。";
  } finally {
    isGenerating.value = false;
  }
}

async function saveCurrentStoryboard(options: { silent?: boolean } = {}): Promise<Storyboard | null> {
  isSaving.value = true;
  if (!options.silent) {
    actionMessage.value = "";
  }
  actionError.value = "";
  try {
    const saved = await saveStoryboard(props.id, toStoryboardPayload());
    storyboard.value = saved;
    applyStoryboard(saved);
    await loadProject();
    if (!options.silent) {
      actionMessage.value = "分镜已保存。";
    }
    return saved;
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "分镜保存失败。";
    return null;
  } finally {
    isSaving.value = false;
  }
}

async function approveCurrentStoryboard(): Promise<void> {
  isApproving.value = true;
  actionMessage.value = "";
  actionError.value = "";
  try {
    const saved = await saveCurrentStoryboard({ silent: true });
    if (!saved) {
      return;
    }
    const approved = await approveStoryboard(props.id);
    storyboard.value = approved;
    applyStoryboard(approved);
    await loadProject();
    actionMessage.value = "分镜已批准。";
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "分镜批准失败。";
  } finally {
    isApproving.value = false;
  }
}

async function generateCurrentSubtitles(): Promise<void> {
  isGeneratingSubtitles.value = true;
  actionMessage.value = "";
  actionError.value = "";
  try {
    subtitles.value = await generateSubtitles(props.id);
    await loadProject();
    actionMessage.value = "字幕 SRT 和 VTT 已生成。";
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "字幕生成失败。";
  } finally {
    isGeneratingSubtitles.value = false;
  }
}

function applyProjectDefaults(): void {
  if (!project.value) {
    return;
  }
  draft.format = project.value.formats[0] ?? "vertical_1080x1920";
  draft.duration_sec = project.value.target_duration_sec;
}

function applyStoryboard(saved: Storyboard): void {
  draft.format = saved.format;
  draft.fps = saved.fps;
  draft.duration_sec = saved.duration_sec;
  draft.safe_area = { ...saved.safe_area };
  draft.shots = saved.shots.map((shot) => ({
    ...shot,
    crop_start: [...shot.crop_start] as [number, number, number, number],
    crop_end: [...shot.crop_end] as [number, number, number, number],
  }));
  selectedShotIndex.value = 0;
}

function toStoryboardPayload(): StoryboardUpdateRequest {
  return {
    format: draft.format,
    fps: Number(draft.fps),
    duration_sec: Number(draft.duration_sec),
    safe_area: { ...draft.safe_area },
    shots: draft.shots.map((shot) => ({
      ...shot,
      start_sec: Number(shot.start_sec),
      end_sec: Number(shot.end_sec),
      crop_start: shot.crop_start.map(Number) as [number, number, number, number],
      crop_end: shot.crop_end.map(Number) as [number, number, number, number],
    })),
  };
}
</script>

<template>
  <main class="page-stack">
    <StepNavigation :project-id="id" current="storyboard" />

    <p v-if="projectError" class="form-message form-message--error">{{ projectError }}</p>
    <p v-else-if="isProjectLoading || isStoryboardLoading" class="muted">正在加载分镜...</p>

    <template v-else-if="project">
      <section class="page-header">
        <div>
          <p class="eyebrow">分镜</p>
          <h1>{{ project.name }}</h1>
        </div>
        <span class="status-pill" :class="{ 'status-pill--ok': storyboard?.approved && !isStoryboardStale }">
          {{ storyboard?.approved && !isStoryboardStale ? "已批准" : statusLabels[project.status] }}
        </span>
      </section>

      <section class="panel">
        <div class="panel__header">
          <div>
            <p class="eyebrow">脚本状态</p>
            <h2>{{ hasApprovedScript ? "脚本已批准" : "等待脚本批准" }}</h2>
          </div>
          <span class="status-pill" :class="{ 'status-pill--ok': hasApprovedScript }">
            {{ hasApprovedScript ? "可生成分镜" : "不可生成" }}
          </span>
        </div>
        <dl class="status-grid status-grid--wide">
          <div>
            <dt>Format</dt>
            <dd>{{ draft.format }}</dd>
          </div>
          <div>
            <dt>FPS</dt>
            <dd>{{ draft.fps }}</dd>
          </div>
          <div>
            <dt>时长</dt>
            <dd>{{ draft.duration_sec.toFixed(2) }}s</dd>
          </div>
          <div>
            <dt>版本</dt>
            <dd>{{ storyboard?.version ?? "未生成" }}</dd>
          </div>
        </dl>
      </section>

      <div class="script-actions">
        <button
          class="button button--primary"
          type="button"
          :disabled="isBusy || !hasApprovedScript"
          @click="generateCurrentStoryboard"
        >
          {{ isGenerating ? "正在生成..." : "生成分镜" }}
        </button>
        <button class="button" type="button" :disabled="!canSave" @click="saveCurrentStoryboard()">
          {{ isSaving ? "正在保存..." : "保存分镜" }}
        </button>
        <button class="button button--primary" type="button" :disabled="!canApprove" @click="approveCurrentStoryboard">
          {{ isApproving ? "正在批准..." : "批准分镜" }}
        </button>
        <button class="button" type="button" :disabled="!canGenerateSubtitles" @click="generateCurrentSubtitles">
          {{ isGeneratingSubtitles ? "正在生成..." : "生成字幕" }}
        </button>
      </div>

      <p v-if="!hasApprovedScript" class="form-message form-message--error">
        请先在脚本页批准脚本。
      </p>
      <p v-if="isStoryboardStale" class="form-message form-message--error">
        当前分镜已过期，请重新生成或保存后批准。
      </p>
      <p v-if="isSubtitlesStale" class="form-message form-message--error">
        当前字幕已过期，请在分镜批准后重新生成。
      </p>
      <p v-if="actionMessage" class="form-message form-message--success">{{ actionMessage }}</p>
      <p v-if="actionError" class="form-message form-message--error">{{ actionError }}</p>

      <section v-if="storyboard || draft.shots.length" class="storyboard-layout">
        <CropPreview :image-src="previewSource" :shot="selectedShot" />
        <StoryboardShotList
          v-model="draft.shots"
          v-model:selected-index="selectedShotIndex"
          :disabled="isBusy"
        />
      </section>

      <section v-else class="empty-state">
        <h2>尚未生成分镜</h2>
        <p class="muted">批准脚本后生成第一版分镜。</p>
      </section>
    </template>
  </main>
</template>

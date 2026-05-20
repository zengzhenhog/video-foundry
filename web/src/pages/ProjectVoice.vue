<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import {
  ApiError,
  generateVoice,
  getVoicePresets,
  getVoiceProviders,
  saveVoiceConfig,
  voiceAudioUrl,
} from "../api/client";
import StepNavigation from "../components/StepNavigation.vue";
import VoiceConfigForm from "../components/VoiceConfigForm.vue";
import { useProject } from "../composables/useProject";
import type {
  ProjectStatus,
  VoiceConfig,
  VoiceConfigRequest,
  VoicePreset,
  VoiceProviderInfo,
} from "../types/project";

const props = defineProps<{
  id: string;
}>();

interface VoiceConfigDraft {
  provider: string;
  voice_id: string;
  language: string;
  speed: number;
  volume_gain_db: number;
  style: string | null;
}

const { project, isLoading: isProjectLoading, error: projectError, loadProject } = useProject(props.id);
const providers = ref<VoiceProviderInfo[]>([]);
const presets = ref<VoicePreset[]>([]);
const voiceConfig = ref<VoiceConfig | null>(null);
const isVoiceLoading = ref(true);
const isSaving = ref(false);
const isGenerating = ref(false);
const actionMessage = ref("");
const actionError = ref("");

const draft = reactive<VoiceConfigDraft>({
  provider: "mock",
  voice_id: "mock-narrator",
  language: "zh-CN",
  speed: 1,
  volume_gain_db: 0,
  style: "clear",
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
  () => isProjectLoading.value || isVoiceLoading.value || isSaving.value || isGenerating.value,
);
const hasApprovedScript = computed(() =>
  Boolean(
    project.value &&
      ["script_approved", "voice_ready", "rendered", "exported"].includes(project.value.status),
  ),
);
const isVoiceStale = computed(() => Boolean(project.value?.stale_artifacts.voice));
const canSave = computed(
  () =>
    !isBusy.value &&
    draft.provider.trim().length > 0 &&
    draft.voice_id.trim().length > 0 &&
    draft.language.trim().length > 0,
);
const canGenerate = computed(() => canSave.value && hasApprovedScript.value);
const audioSource = computed(() =>
  voiceConfig.value?.audio_path ? voiceAudioUrl(props.id, voiceConfig.value.updated_at) : "",
);

onMounted(refreshPage);

async function refreshPage(): Promise<void> {
  isVoiceLoading.value = true;
  actionError.value = "";
  try {
    await Promise.all([loadProject(), loadVoiceOptions()]);
    voiceConfig.value = project.value?.voice_config ?? null;
    applyVoiceDefaults();
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "无法加载旁白配置。";
  } finally {
    isVoiceLoading.value = false;
  }
}

async function loadVoiceOptions(): Promise<void> {
  const [loadedProviders, loadedPresets] = await Promise.all([
    getVoiceProviders(),
    getVoicePresets(),
  ]);
  providers.value = loadedProviders;
  presets.value = loadedPresets;
}

async function saveCurrentVoiceConfig(options: { silent?: boolean } = {}): Promise<VoiceConfig | null> {
  isSaving.value = true;
  if (!options.silent) {
    actionMessage.value = "";
  }
  actionError.value = "";
  try {
    const saved = await saveVoiceConfig(props.id, toVoicePayload());
    voiceConfig.value = saved;
    applyVoiceConfig(saved);
    await loadProject();
    if (!options.silent) {
      actionMessage.value = "旁白配置已保存。";
    }
    return saved;
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "旁白配置保存失败。";
    return null;
  } finally {
    isSaving.value = false;
  }
}

async function generateCurrentVoice(): Promise<void> {
  isGenerating.value = true;
  actionMessage.value = "";
  actionError.value = "";
  try {
    const saved = await saveCurrentVoiceConfig({ silent: true });
    if (!saved) {
      return;
    }
    const generated = await generateVoice(props.id);
    voiceConfig.value = generated;
    applyVoiceConfig(generated);
    await loadProject();
    actionMessage.value = "旁白音频已生成。";
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "旁白生成失败。";
  } finally {
    isGenerating.value = false;
  }
}

function applyVoiceDefaults(): void {
  if (voiceConfig.value) {
    applyVoiceConfig(voiceConfig.value);
    return;
  }
  const targetLanguage = project.value?.target_language ?? "zh-CN";
  const defaultPreset =
    presets.value.find((preset) => preset.language === targetLanguage) ?? presets.value[0];
  draft.provider = defaultPreset?.provider ?? providers.value[0]?.id ?? "mock";
  draft.voice_id = defaultPreset?.id ?? "mock-narrator";
  draft.language = defaultPreset?.language ?? targetLanguage;
  draft.speed = 1;
  draft.volume_gain_db = 0;
  draft.style = defaultPreset?.style ?? "clear";
}

function applyVoiceConfig(config: VoiceConfig): void {
  draft.provider = config.provider;
  draft.voice_id = config.voice_id;
  draft.language = config.language;
  draft.speed = config.speed;
  draft.volume_gain_db = config.volume_gain_db;
  draft.style = config.style;
}

function toVoicePayload(): VoiceConfigRequest {
  return {
    provider: draft.provider.trim(),
    voice_id: draft.voice_id.trim(),
    language: draft.language.trim(),
    speed: Number(draft.speed),
    volume_gain_db: Number(draft.volume_gain_db),
    style: draft.style?.trim() || null,
  };
}
</script>

<template>
  <main class="page-stack">
    <StepNavigation :project-id="id" current="voice" />

    <p v-if="projectError" class="form-message form-message--error">{{ projectError }}</p>
    <p v-else-if="isProjectLoading || isVoiceLoading" class="muted">正在加载旁白...</p>

    <template v-else-if="project">
      <section class="page-header">
        <div>
          <p class="eyebrow">旁白</p>
          <h1>{{ project.name }}</h1>
        </div>
        <span
          class="status-pill"
          :class="{ 'status-pill--ok': voiceConfig?.audio_path && !isVoiceStale }"
        >
          {{ voiceConfig?.audio_path && !isVoiceStale ? "可试听" : statusLabels[project.status] }}
        </span>
      </section>

      <section class="panel">
        <div class="panel__header">
          <div>
            <p class="eyebrow">脚本状态</p>
            <h2>{{ hasApprovedScript ? "脚本已批准" : "等待批准" }}</h2>
          </div>
          <span class="status-pill" :class="{ 'status-pill--ok': hasApprovedScript }">
            {{ hasApprovedScript ? "可生成" : "不可生成" }}
          </span>
        </div>
      </section>

      <VoiceConfigForm
        v-model="draft"
        :providers="providers"
        :presets="presets"
        :disabled="isBusy"
      />

      <div class="script-actions">
        <button class="button" type="button" :disabled="!canSave" @click="saveCurrentVoiceConfig()">
          {{ isSaving ? "正在保存..." : "保存配置" }}
        </button>
        <button
          class="button button--primary"
          type="button"
          :disabled="!canGenerate"
          @click="generateCurrentVoice"
        >
          {{ isGenerating ? "正在生成..." : "生成旁白" }}
        </button>
      </div>

      <p v-if="!hasApprovedScript" class="form-message form-message--error">
        请先在脚本页批准脚本。
      </p>
      <p v-if="isVoiceStale" class="form-message form-message--error">
        当前旁白已过期，请重新生成。
      </p>
      <p v-if="actionMessage" class="form-message form-message--success">{{ actionMessage }}</p>
      <p v-if="actionError" class="form-message form-message--error">{{ actionError }}</p>

      <section class="panel voice-player">
        <div class="panel__header">
          <div>
            <p class="eyebrow">试听</p>
            <h2>旁白音频</h2>
          </div>
        </div>

        <audio v-if="audioSource" :src="audioSource" controls preload="metadata" />
        <p v-else class="muted">尚未生成旁白音频。</p>

        <dl class="status-grid status-grid--wide voice-meta">
          <div>
            <dt>Provider</dt>
            <dd>{{ voiceConfig?.provider ?? draft.provider }}</dd>
          </div>
          <div>
            <dt>Voice</dt>
            <dd>{{ voiceConfig?.voice_id ?? draft.voice_id }}</dd>
          </div>
          <div>
            <dt>格式</dt>
            <dd>{{ voiceConfig?.audio_format ?? "未生成" }}</dd>
          </div>
          <div>
            <dt>时长</dt>
            <dd>{{ voiceConfig?.duration_sec ? `${voiceConfig.duration_sec.toFixed(1)}s` : "未生成" }}</dd>
          </div>
        </dl>
      </section>
    </template>
  </main>
</template>

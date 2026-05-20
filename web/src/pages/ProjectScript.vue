<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import {
  ApiError,
  approveScript,
  generateScript,
  getScript,
  saveScript,
} from "../api/client";
import ScriptEditor from "../components/ScriptEditor.vue";
import StepNavigation from "../components/StepNavigation.vue";
import { useProject } from "../composables/useProject";
import type { ProjectStatus, Script, ScriptSegment } from "../types/project";

const props = defineProps<{
  id: string;
}>();

interface ScriptDraft {
  language: string;
  duration_target_sec: number;
  title: string;
  narration: string;
  segments: ScriptSegment[];
  review_notes: string;
}

const { project, isLoading: isProjectLoading, error: projectError, loadProject } = useProject(props.id);
const script = ref<Script | null>(null);
const isScriptLoading = ref(true);
const isGenerating = ref(false);
const isSaving = ref(false);
const isApproving = ref(false);
const actionMessage = ref("");
const actionError = ref("");

const draft = reactive<ScriptDraft>({
  language: "zh-CN",
  duration_target_sec: 60,
  title: "",
  narration: "",
  segments: [],
  review_notes: "",
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
  () => isProjectLoading.value || isScriptLoading.value || isGenerating.value || isSaving.value || isApproving.value,
);
const canGenerate = computed(() => Boolean(project.value?.asset_status.ready_for_script) && !isBusy.value);
const canSave = computed(
  () =>
    !isBusy.value &&
    draft.narration.trim().length > 0 &&
    draft.review_notes.trim().length > 0 &&
    draft.segments.length > 0 &&
    draft.segments.every((segment) => segment.text.trim().length > 0),
);

onMounted(refreshPage);

async function refreshPage(): Promise<void> {
  await loadProject();
  applyProjectDefaults();
  await loadExistingScript();
}

async function loadExistingScript(): Promise<void> {
  isScriptLoading.value = true;
  actionError.value = "";
  try {
    const savedScript = await getScript(props.id);
    script.value = savedScript;
    applyScript(savedScript);
  } catch (caught) {
    if (caught instanceof ApiError && caught.code === "script_not_found") {
      script.value = null;
    } else {
      actionError.value = caught instanceof ApiError ? caught.message : "无法加载脚本。";
    }
  } finally {
    isScriptLoading.value = false;
  }
}

async function generateCurrentScript(): Promise<void> {
  isGenerating.value = true;
  actionMessage.value = "";
  actionError.value = "";
  try {
    const generated = await generateScript(props.id, {
      user_draft: draft.narration.trim() || null,
    });
    script.value = generated;
    applyScript(generated);
    await loadProject();
    actionMessage.value = "脚本已生成。";
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "脚本生成失败。";
  } finally {
    isGenerating.value = false;
  }
}

async function saveCurrentScript(options: { silent?: boolean } = {}): Promise<Script | null> {
  isSaving.value = true;
  if (!options.silent) {
    actionMessage.value = "";
  }
  actionError.value = "";
  try {
    const saved = await saveScript(props.id, toScriptPayload());
    script.value = saved;
    applyScript(saved);
    await loadProject();
    if (!options.silent) {
      actionMessage.value = "脚本已保存。";
    }
    return saved;
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "脚本保存失败。";
    return null;
  } finally {
    isSaving.value = false;
  }
}

async function approveCurrentScript(): Promise<void> {
  isApproving.value = true;
  actionMessage.value = "";
  actionError.value = "";
  try {
    const saved = await saveCurrentScript({ silent: true });
    if (!saved) {
      return;
    }
    const approved = await approveScript(props.id);
    script.value = approved;
    applyScript(approved);
    await loadProject();
    actionMessage.value = "脚本已批准。";
  } catch (caught) {
    actionError.value = caught instanceof ApiError ? caught.message : "脚本批准失败。";
  } finally {
    isApproving.value = false;
  }
}

function applyProjectDefaults(): void {
  if (!project.value) {
    return;
  }
  draft.language = project.value.target_language;
  draft.duration_target_sec = project.value.target_duration_sec;
  draft.title = project.value.asset?.title || project.value.name;
  draft.narration = "";
  draft.segments = [
    {
      start_sec: 0,
      end_sec: project.value.target_duration_sec,
      text: project.value.asset?.description ?? "",
    },
  ];
  draft.review_notes = "人工审核：脚本应只依据已保存的描述、来源 URL、署名和用户草稿。";
}

function applyScript(savedScript: Script): void {
  draft.language = savedScript.language;
  draft.duration_target_sec = savedScript.duration_target_sec;
  draft.title = savedScript.title;
  draft.narration = savedScript.narration;
  draft.segments = savedScript.segments.map((segment) => ({ ...segment }));
  draft.review_notes = savedScript.review_notes;
}

function toScriptPayload() {
  return {
    language: draft.language,
    duration_target_sec: Number(draft.duration_target_sec),
    title: draft.title,
    narration: draft.narration,
    review_notes: draft.review_notes,
    segments: draft.segments.map((segment) => ({
      start_sec: Number(segment.start_sec),
      end_sec: Number(segment.end_sec),
      text: segment.text,
    })),
  };
}
</script>

<template>
  <main class="page-stack">
    <StepNavigation :project-id="id" current="script" />

    <p v-if="projectError" class="form-message form-message--error">{{ projectError }}</p>
    <p v-else-if="isProjectLoading || isScriptLoading" class="muted">正在加载脚本...</p>

    <template v-else-if="project">
      <section class="page-header">
        <div>
          <p class="eyebrow">脚本</p>
          <h1>{{ project.name }}</h1>
        </div>
        <span class="status-pill" :class="{ 'status-pill--ok': script?.approved }">
          {{ script?.approved ? "已批准" : statusLabels[project.status] }}
        </span>
      </section>

      <section class="panel">
        <div class="panel__header">
          <div>
            <p class="eyebrow">来源</p>
            <h2>{{ project.asset?.title || "未命名素材" }}</h2>
          </div>
          <span
            class="status-pill"
            :class="{ 'status-pill--ok': project.asset_status.ready_for_script }"
          >
            {{ project.asset_status.ready_for_script ? "可生成" : "待补齐" }}
          </span>
        </div>
        <dl class="status-grid status-grid--wide">
          <div>
            <dt>描述</dt>
            <dd>{{ project.asset_status.has_description ? "已保存" : "缺失" }}</dd>
          </div>
          <div>
            <dt>来源 URL</dt>
            <dd>{{ project.asset_status.has_source_url ? "已保存" : "缺失" }}</dd>
          </div>
          <div>
            <dt>署名</dt>
            <dd>{{ project.asset_status.has_credit ? "已保存" : "缺失" }}</dd>
          </div>
          <div>
            <dt>图片</dt>
            <dd>{{ project.asset_status.has_original_image ? "已保存" : "缺失" }}</dd>
          </div>
        </dl>
      </section>

      <div class="script-actions">
        <button class="button button--primary" type="button" :disabled="!canGenerate" @click="generateCurrentScript">
          {{ isGenerating ? "正在生成..." : "生成脚本" }}
        </button>
        <button class="button" type="button" :disabled="!canSave" @click="saveCurrentScript()">
          {{ isSaving ? "正在保存..." : "保存" }}
        </button>
        <button class="button button--primary" type="button" :disabled="!canSave" @click="approveCurrentScript">
          {{ isApproving ? "正在批准..." : "批准脚本" }}
        </button>
      </div>

      <p v-if="!project.asset_status.ready_for_script" class="form-message form-message--error">
        请先在素材页补齐图片、描述、来源 URL 和署名。
      </p>
      <p v-if="actionMessage" class="form-message form-message--success">{{ actionMessage }}</p>
      <p v-if="actionError" class="form-message form-message--error">{{ actionError }}</p>

      <ScriptEditor v-model="draft" :disabled="isBusy" />
    </template>
  </main>
</template>

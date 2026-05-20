<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { ApiError, assetPreviewUrl, getProject } from "../api/client";
import BackgroundMusicUploader from "../components/BackgroundMusicUploader.vue";
import ImageUploader from "../components/ImageUploader.vue";
import StepNavigation from "../components/StepNavigation.vue";
import TextInputPanel from "../components/TextInputPanel.vue";
import type { ProjectDetail, ProjectStatus } from "../types/project";

const props = defineProps<{
  id: string;
}>();

const project = ref<ProjectDetail | null>(null);
const isLoading = ref(true);
const error = ref("");

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

const previewUrl = computed(() => {
  if (!project.value?.asset_status.has_preview_image) {
    return "";
  }
  return assetPreviewUrl(project.value.id, project.value.asset?.updated_at);
});

onMounted(loadProject);

async function loadProject(): Promise<void> {
  isLoading.value = true;
  error.value = "";
  try {
    project.value = await getProject(props.id);
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法加载项目。";
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <main class="page-stack">
    <StepNavigation :project-id="id" current="assets" />

    <p v-if="error" class="form-message form-message--error">{{ error }}</p>
    <p v-else-if="isLoading" class="muted">正在加载项目...</p>

    <template v-else-if="project">
      <section class="page-header">
        <div>
          <p class="eyebrow">素材</p>
          <h1>{{ project.name }}</h1>
        </div>
        <span class="status-pill" :class="{ 'status-pill--ok': project.asset_status.ready_for_script }">
          {{ statusLabels[project.status] }}
        </span>
      </section>

      <section class="asset-layout">
        <div class="preview-panel">
          <img v-if="previewUrl" :src="previewUrl" alt="项目图片预览" />
          <div v-else class="preview-placeholder">暂无预览</div>
          <dl class="status-grid">
            <div>
              <dt>图片</dt>
              <dd>{{ project.asset_status.has_original_image ? "已保存" : "缺失" }}</dd>
            </div>
            <div>
              <dt>来源</dt>
              <dd>{{ project.asset_status.has_source_url ? "已保存" : "缺失" }}</dd>
            </div>
            <div>
              <dt>署名</dt>
              <dd>{{ project.asset_status.has_credit ? "已保存" : "缺失" }}</dd>
            </div>
            <div>
              <dt>音乐</dt>
              <dd>{{ project.asset_status.has_background_music ? "已保存" : "可选" }}</dd>
            </div>
          </dl>
        </div>

        <div class="page-stack page-stack--compact">
          <ImageUploader :project-id="project.id" :asset="project.asset" @uploaded="loadProject()" />
          <TextInputPanel :project-id="project.id" :asset="project.asset" @saved="loadProject()" />
          <BackgroundMusicUploader
            :project-id="project.id"
            :music="project.background_music"
            @uploaded="loadProject()"
          />
        </div>
      </section>
    </template>
  </main>
</template>

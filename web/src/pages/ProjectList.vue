<script setup lang="ts">
import { onMounted, ref } from "vue";

import { ApiError, listProjects } from "../api/client";
import StepNavigation from "../components/StepNavigation.vue";
import type { Project, ProjectStatus } from "../types/project";

const projects = ref<Project[]>([]);
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

onMounted(loadProjects);

async function loadProjects(): Promise<void> {
  isLoading.value = true;
  error.value = "";
  try {
    projects.value = await listProjects();
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法加载项目。";
  } finally {
    isLoading.value = false;
  }
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
  }).format(new Date(value));
}
</script>

<template>
  <main class="page-stack">
    <StepNavigation current="projects" />

    <section class="page-header">
      <div>
        <p class="eyebrow">项目</p>
        <h1>项目工作台</h1>
      </div>
      <RouterLink class="button button--primary" to="/projects/new">新建项目</RouterLink>
    </section>

    <p v-if="error" class="form-message form-message--error">{{ error }}</p>
    <p v-else-if="isLoading" class="muted">正在加载项目...</p>

    <section v-else-if="projects.length" class="project-list" aria-label="项目列表">
      <RouterLink
        v-for="project in projects"
        :key="project.id"
        class="project-card"
        :to="`/projects/${project.id}/assets`"
      >
        <span class="status-pill">{{ statusLabels[project.status] }}</span>
        <h2>{{ project.name }}</h2>
        <div class="meta-row">
          <span>{{ project.target_language }}</span>
          <span>{{ project.target_duration_sec }} 秒</span>
          <span>{{ formatDate(project.updated_at) }}</span>
        </div>
      </RouterLink>
    </section>

    <section v-else class="empty-state">
      <h2>还没有项目</h2>
      <RouterLink class="button button--primary" to="/projects/new">新建项目</RouterLink>
    </section>
  </main>
</template>

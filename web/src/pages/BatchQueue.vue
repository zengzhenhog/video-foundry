<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  ApiError,
  enqueueBatch,
  getBatchQueue,
  listProjects,
  pauseBatchItem,
  resumeBatchItem,
  retryBatchItem,
  runBatchQueue,
} from "../api/client";
import NasaSearchPanel from "../components/NasaSearchPanel.vue";
import StepNavigation from "../components/StepNavigation.vue";
import type { BatchItemStatus, BatchQueueItem, Project, ProjectDetail } from "../types/project";

const projects = ref<Project[]>([]);
const queue = ref<BatchQueueItem[]>([]);
const selectedProjectIds = ref<Set<string>>(new Set());
const isLoading = ref(true);
const isQueueing = ref(false);
const error = ref("");
const success = ref("");

const selectedCount = computed(() => selectedProjectIds.value.size);
const projectNames = computed(() => new Map(projects.value.map((project) => [project.id, project.name])));

const batchLabels: Record<BatchItemStatus, string> = {
  pending: "等待中",
  running: "运行中",
  paused: "已暂停",
  succeeded: "已完成",
  blocked: "需审核",
  failed: "失败",
  cancelled: "已取消",
};

onMounted(load);

async function load(): Promise<void> {
  isLoading.value = true;
  error.value = "";
  try {
    const [loadedProjects, loadedQueue] = await Promise.all([listProjects(), getBatchQueue()]);
    projects.value = loadedProjects;
    queue.value = loadedQueue;
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法加载批量队列。";
  } finally {
    isLoading.value = false;
  }
}

function toggleProject(projectId: string, checked: boolean): void {
  const next = new Set(selectedProjectIds.value);
  if (checked) {
    next.add(projectId);
  } else {
    next.delete(projectId);
  }
  selectedProjectIds.value = next;
}

async function enqueueSelected(): Promise<void> {
  if (!selectedCount.value) {
    return;
  }
  isQueueing.value = true;
  error.value = "";
  success.value = "";
  try {
    queue.value = await enqueueBatch({
      project_ids: Array.from(selectedProjectIds.value),
      action: "generate_all",
      max_attempts: 2,
    });
    selectedProjectIds.value = new Set();
    success.value = "已加入批量队列。";
    await refreshQueue();
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法加入队列。";
  } finally {
    isQueueing.value = false;
  }
}

async function refreshQueue(): Promise<void> {
  queue.value = await getBatchQueue();
}

async function runQueueNow(): Promise<void> {
  await queueAction(() => runBatchQueue(), "已继续处理队列。");
}

async function pauseItem(item: BatchQueueItem): Promise<void> {
  await itemAction(() => pauseBatchItem(item.id));
}

async function resumeItem(item: BatchQueueItem): Promise<void> {
  await itemAction(() => resumeBatchItem(item.id));
}

async function retryItem(item: BatchQueueItem): Promise<void> {
  await itemAction(() => retryBatchItem(item.id));
}

async function itemAction(action: () => Promise<BatchQueueItem>): Promise<void> {
  error.value = "";
  try {
    await action();
    await refreshQueue();
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法更新批量任务。";
  }
}

async function queueAction(action: () => Promise<BatchQueueItem[]>, message: string): Promise<void> {
  error.value = "";
  success.value = "";
  try {
    queue.value = await action();
    success.value = message;
    await refreshQueue();
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法处理队列。";
  }
}

async function onImported(_project: ProjectDetail): Promise<void> {
  projects.value = await listProjects();
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
        <p class="eyebrow">批量</p>
        <h1>导入与批量队列</h1>
      </div>
      <button class="button" type="button" @click="load">刷新</button>
    </section>

    <p v-if="error" class="form-message form-message--error">{{ error }}</p>
    <p v-if="success" class="form-message form-message--success">{{ success }}</p>
    <p v-if="isLoading" class="muted">正在加载批量工作台...</p>

    <NasaSearchPanel v-if="!isLoading" @imported="onImported" />

    <section v-if="!isLoading" class="batch-layout">
      <div class="panel">
        <div class="panel__header">
          <div>
            <p class="eyebrow">项目</p>
            <h2>选择批量生成项目</h2>
          </div>
          <button
            class="button button--primary"
            type="button"
            :disabled="!selectedCount || isQueueing"
            @click="enqueueSelected"
          >
            {{ isQueueing ? "加入中..." : `加入队列 (${selectedCount})` }}
          </button>
        </div>

        <div v-if="projects.length" class="batch-projects">
          <label v-for="project in projects" :key="project.id" class="batch-project-row">
            <input
              type="checkbox"
              :checked="selectedProjectIds.has(project.id)"
              @change="toggleProject(project.id, ($event.target as HTMLInputElement).checked)"
            />
            <span>
              <strong>{{ project.name }}</strong>
              <small>{{ project.status }} · {{ formatDate(project.updated_at) }}</small>
            </span>
          </label>
        </div>
        <p v-else class="muted">还没有可加入队列的项目。</p>
      </div>

      <div class="panel">
        <div class="panel__header">
          <div>
            <p class="eyebrow">队列</p>
            <h2>批量任务状态</h2>
          </div>
          <button class="button" type="button" @click="runQueueNow">继续队列</button>
        </div>

        <ul v-if="queue.length" class="batch-queue-list">
          <li v-for="item in queue" :key="item.id">
            <div class="batch-queue-list__main">
              <span class="status-pill" :class="{ 'status-pill--ok': item.status === 'succeeded' }">
                {{ batchLabels[item.status] }}
              </span>
              <strong>{{ projectNames.get(item.project_id) ?? item.project_id }}</strong>
              <small>{{ item.summary || item.action }} · {{ item.attempts }}/{{ item.max_attempts }}</small>
              <small v-if="item.job_id">Job {{ item.job_id }}</small>
              <p v-if="item.error" class="form-message form-message--error">
                {{ item.error.reason }}
              </p>
            </div>
            <div class="script-actions">
              <button
                v-if="item.status === 'pending' || item.status === 'running'"
                class="button"
                type="button"
                @click="pauseItem(item)"
              >
                暂停
              </button>
              <button v-if="item.status === 'paused'" class="button" type="button" @click="resumeItem(item)">
                继续
              </button>
              <button
                v-if="item.status === 'failed' || item.status === 'blocked'"
                class="button"
                type="button"
                @click="retryItem(item)"
              >
                重试
              </button>
              <RouterLink class="button" :to="`/projects/${item.project_id}`">打开</RouterLink>
            </div>
          </li>
        </ul>
        <p v-else class="muted">队列为空。</p>
      </div>
    </section>
  </main>
</template>

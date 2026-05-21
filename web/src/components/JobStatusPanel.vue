<script setup lang="ts">
import { computed } from "vue";

import type { JobRecord, JobStatus } from "../types/project";

const props = defineProps<{
  job: JobRecord | null;
  isPolling: boolean;
}>();

const emit = defineEmits<{
  retry: [];
}>();

const statusLabels: Record<JobStatus, string> = {
  pending: "排队中",
  running: "运行中",
  succeeded: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

const progressPercent = computed(() => Math.round((props.job?.progress ?? 0) * 100));
const canRetry = computed(() => Boolean(props.job?.status === "failed" && props.job.error?.retryable));
</script>

<template>
  <section class="panel job-panel">
    <div class="panel__header">
      <div>
        <p class="eyebrow">任务</p>
        <h2>{{ job ? statusLabels[job.status] : "暂无任务" }}</h2>
      </div>
      <span v-if="job" class="status-pill" :class="{ 'status-pill--ok': job.status === 'succeeded' }">
        {{ progressPercent }}%
      </span>
    </div>

    <template v-if="job">
      <div class="progress-track" aria-label="任务进度">
        <div class="progress-track__bar" :style="{ width: `${progressPercent}%` }"></div>
      </div>
      <p class="muted">{{ isPolling ? "正在刷新任务状态..." : job.summary }}</p>

      <dl v-if="job.error" class="status-grid status-grid--wide">
        <div>
          <dt>Step</dt>
          <dd>{{ job.error.step }}</dd>
        </div>
        <div>
          <dt>Reason</dt>
          <dd>{{ job.error.reason }}</dd>
        </div>
        <div>
          <dt>Retry</dt>
          <dd>{{ job.error.retryable ? "可重试" : "不可重试" }}</dd>
        </div>
        <div>
          <dt>Correction</dt>
          <dd>{{ job.error.suggested_correction || "检查输入后重试" }}</dd>
        </div>
      </dl>

      <div v-if="job.output_paths.length" class="output-list">
        <span v-for="path in job.output_paths" :key="path">{{ path }}</span>
      </div>

      <button v-if="canRetry" class="button" type="button" @click="emit('retry')">重试</button>
    </template>

    <p v-else class="muted">提交渲染或导出后，这里会显示进度、结果和失败诊断。</p>
  </section>
</template>


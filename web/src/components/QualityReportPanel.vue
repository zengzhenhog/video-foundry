<script setup lang="ts">
import { computed } from "vue";

import type { QualityReport } from "../types/project";

const props = defineProps<{
  report: QualityReport | null;
  isLoading: boolean;
  error: string;
}>();

const passedCount = computed(() => props.report?.checks.filter((check) => check.passed).length ?? 0);
const failedCount = computed(() => props.report?.checks.filter((check) => !check.passed).length ?? 0);
</script>

<template>
  <section class="panel quality-panel">
    <div class="panel__header">
      <div>
        <p class="eyebrow">质量门禁</p>
        <h2>{{ report ? (report.passed ? "已通过" : "未通过") : "等待导出" }}</h2>
      </div>
      <span v-if="report" class="status-pill" :class="{ 'status-pill--ok': report.passed }">
        {{ passedCount }} / {{ report.checks.length }}
      </span>
    </div>

    <p v-if="isLoading" class="muted">正在读取质量报告...</p>
    <p v-else-if="error" class="form-message form-message--error">{{ error }}</p>
    <p v-else-if="!report" class="muted">最终导出任务会先生成 quality-report.json，通过后才会标记为已导出。</p>

    <template v-else>
      <dl class="status-grid status-grid--wide">
        <div>
          <dt>Result</dt>
          <dd>{{ report.passed ? "通过" : "失败" }}</dd>
        </div>
        <div>
          <dt>Passed</dt>
          <dd>{{ passedCount }}</dd>
        </div>
        <div>
          <dt>Failed</dt>
          <dd>{{ failedCount }}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{{ new Date(report.created_at).toLocaleString() }}</dd>
        </div>
      </dl>

      <ul class="check-list">
        <li v-for="check in report.checks" :key="check.name" :class="{ 'check-list__item--failed': !check.passed }">
          <span>{{ check.passed ? "通过" : "失败" }}</span>
          <strong>{{ check.name }}</strong>
        </li>
      </ul>
    </template>
  </section>
</template>

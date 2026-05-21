<script setup lang="ts">
import { computed } from "vue";

import { downloadFileUrl } from "../api/client";
import type { DownloadsResponse } from "../types/project";

const props = defineProps<{
  downloads: DownloadsResponse | null;
  isLoading: boolean;
  error: string;
}>();

const groupedFiles = computed(() => props.downloads?.files ?? []);
const missingFiles = computed(() => props.downloads?.missing ?? []);

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
</script>

<template>
  <section class="panel download-panel">
    <div class="panel__header">
      <div>
        <p class="eyebrow">下载</p>
        <h2>{{ groupedFiles.length ? "可下载资源" : "等待导出" }}</h2>
      </div>
      <span v-if="groupedFiles.length" class="status-pill status-pill--ok">
        {{ groupedFiles.length }} 个文件
      </span>
    </div>

    <p v-if="isLoading" class="muted">正在读取下载列表...</p>
    <p v-else-if="error" class="form-message form-message--error">{{ error }}</p>

    <template v-else>
      <div v-if="groupedFiles.length" class="download-list">
        <a
          v-for="file in groupedFiles"
          :key="file.path"
          class="download-link"
          :href="downloadFileUrl(file.url)"
          download
        >
          <span>{{ file.label }}</span>
          <strong>{{ formatBytes(file.size_bytes) }}</strong>
          <small>{{ file.path }}</small>
        </a>
      </div>
      <p v-else class="muted">最终 MP4、字幕、旁白、元数据和质量报告会在这里出现。</p>

      <div v-if="missingFiles.length" class="missing-downloads">
        <p class="eyebrow">缺失推荐文件</p>
        <ul>
          <li v-for="file in missingFiles" :key="file.path">
            <span>{{ file.label }}</span>
            <small>{{ file.path }}</small>
          </li>
        </ul>
      </div>
    </template>
  </section>
</template>

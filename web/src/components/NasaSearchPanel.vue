<script setup lang="ts">
import { ref } from "vue";

import { ApiError, importNasaProject, searchNasa } from "../api/client";
import type { NasaSearchResult, ProjectDetail } from "../types/project";

const emit = defineEmits<{
  imported: [project: ProjectDetail];
}>();

const query = ref("moon");
const targetLanguage = ref("zh-CN");
const targetDurationSec = ref(60);
const results = ref<NasaSearchResult[]>([]);
const isSearching = ref(false);
const importingId = ref("");
const error = ref("");
const success = ref("");

async function submitSearch(): Promise<void> {
  error.value = "";
  success.value = "";
  isSearching.value = true;
  try {
    results.value = await searchNasa(query.value, 8);
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法搜索 NASA 图片。";
  } finally {
    isSearching.value = false;
  }
}

async function importResult(result: NasaSearchResult): Promise<void> {
  error.value = "";
  success.value = "";
  importingId.value = result.nasa_id;
  try {
    const project = await importNasaProject({
      result,
      name: result.title,
      target_language: targetLanguage.value,
      target_duration_sec: targetDurationSec.value,
      formats: ["vertical_1080x1920"],
    });
    success.value = `已导入：${project.name}`;
    emit("imported", project);
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法导入 NASA 项目。";
  } finally {
    importingId.value = "";
  }
}
</script>

<template>
  <section class="panel nasa-panel">
    <div class="panel__header">
      <div>
        <p class="eyebrow">NASA 导入</p>
        <h2>搜索官方图片源</h2>
      </div>
      <button class="button button--primary" type="button" :disabled="isSearching" @click="submitSearch">
        {{ isSearching ? "搜索中..." : "搜索" }}
      </button>
    </div>

    <div class="form-grid">
      <label>
        <span>关键词</span>
        <input v-model.trim="query" type="search" placeholder="moon, nebula, mars" @keyup.enter="submitSearch" />
      </label>
      <label>
        <span>语言</span>
        <input v-model.trim="targetLanguage" type="text" />
      </label>
      <label>
        <span>目标时长</span>
        <input v-model.number="targetDurationSec" min="5" max="3600" type="number" />
      </label>
    </div>

    <p v-if="error" class="form-message form-message--error">{{ error }}</p>
    <p v-if="success" class="form-message form-message--success">{{ success }}</p>

    <div v-if="results.length" class="nasa-results">
      <article v-for="result in results" :key="result.nasa_id" class="nasa-result">
        <img v-if="result.thumbnail_url" :src="result.thumbnail_url" :alt="result.title" loading="lazy" />
        <div v-else class="preview-placeholder">NASA</div>
        <div class="nasa-result__body">
          <div class="meta-row">
            <span>{{ result.nasa_id }}</span>
            <span>{{ result.center ?? "NASA" }}</span>
          </div>
          <h3>{{ result.title }}</h3>
          <p>{{ result.description }}</p>
          <small>{{ result.credit }}</small>
        </div>
        <button
          class="button"
          type="button"
          :disabled="importingId === result.nasa_id"
          @click="importResult(result)"
        >
          {{ importingId === result.nasa_id ? "导入中..." : "导入项目" }}
        </button>
      </article>
    </div>
  </section>
</template>

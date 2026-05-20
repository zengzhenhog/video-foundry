<script setup lang="ts">
import { reactive, watch } from "vue";
import { ref } from "vue";

import { ApiError, saveAssetText } from "../api/client";
import type { Asset } from "../types/project";

const props = defineProps<{
  projectId: string;
  asset: Asset | null;
}>();

const emit = defineEmits<{
  saved: [asset: Asset];
}>();

const form = reactive({
  title: "",
  description: "",
  source_url: "",
  credit: "",
});
const isSaving = ref(false);
const message = ref("");
const error = ref("");

watch(
  () => props.asset,
  (asset) => {
    form.title = asset?.title ?? "";
    form.description = asset?.description ?? "";
    form.source_url = asset?.source_url ?? "";
    form.credit = asset?.credit ?? "";
  },
  { immediate: true },
);

async function submit(): Promise<void> {
  isSaving.value = true;
  message.value = "";
  error.value = "";
  try {
    const asset = await saveAssetText(props.projectId, {
      title: form.title,
      description: form.description,
      source_url: form.source_url || null,
      credit: form.credit,
    });
    message.value = "文案已保存。";
    emit("saved", asset);
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "文案保存失败。";
  } finally {
    isSaving.value = false;
  }
}
</script>

<template>
  <section class="panel">
    <div class="panel__header">
      <div>
        <p class="eyebrow">文案和署名</p>
        <h2>文案</h2>
      </div>
      <span v-if="asset?.credit && asset?.source_url" class="status-pill status-pill--ok">署名完整</span>
    </div>

    <div class="form-grid">
      <label>
        <span>标题</span>
        <input v-model="form.title" type="text" maxlength="240" />
      </label>
      <label>
        <span>来源 URL</span>
        <input v-model="form.source_url" type="url" />
      </label>
      <label class="form-grid__wide">
        <span>描述</span>
        <textarea v-model="form.description" rows="6" />
      </label>
      <label class="form-grid__wide">
        <span>署名</span>
        <input v-model="form.credit" type="text" maxlength="500" />
      </label>
    </div>

    <button class="button button--primary" :disabled="isSaving" @click="submit">
      {{ isSaving ? "正在保存..." : "保存文案" }}
    </button>

    <p v-if="message" class="form-message form-message--success">{{ message }}</p>
    <p v-if="error" class="form-message form-message--error">{{ error }}</p>
  </section>
</template>

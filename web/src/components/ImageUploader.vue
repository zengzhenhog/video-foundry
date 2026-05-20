<script setup lang="ts">
import { ref } from "vue";

import { ApiError, uploadImage } from "../api/client";
import type { Asset } from "../types/project";

const props = defineProps<{
  projectId: string;
  asset: Asset | null;
}>();

const emit = defineEmits<{
  uploaded: [asset: Asset];
}>();

const selectedFile = ref<File | null>(null);
const isUploading = ref(false);
const message = ref("");
const error = ref("");

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] ?? null;
  message.value = "";
  error.value = "";
}

async function submit(): Promise<void> {
  if (!selectedFile.value) {
    error.value = "请先选择图片文件。";
    return;
  }

  isUploading.value = true;
  error.value = "";
  message.value = "";
  try {
    const asset = await uploadImage(props.projectId, selectedFile.value);
    message.value = "图片已保存。";
    emit("uploaded", asset);
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "图片上传失败。";
  } finally {
    isUploading.value = false;
  }
}
</script>

<template>
  <section class="panel">
    <div class="panel__header">
      <div>
        <p class="eyebrow">来源图片</p>
        <h2>图片</h2>
      </div>
      <span v-if="asset?.sha256" class="status-pill status-pill--ok">已保存</span>
    </div>

    <div v-if="asset?.width && asset?.height" class="meta-row">
      <span>{{ asset.width }} x {{ asset.height }}</span>
      <span v-if="asset.image_format">{{ asset.image_format.toUpperCase() }}</span>
    </div>

    <label class="file-drop">
      <input type="file" accept="image/jpeg,image/png,image/webp" @change="onFileChange" />
      <span>{{ selectedFile?.name ?? asset?.original_filename ?? "选择图片" }}</span>
    </label>

    <button class="button button--primary" :disabled="isUploading" @click="submit">
      {{ isUploading ? "正在上传..." : "上传图片" }}
    </button>

    <p v-if="message" class="form-message form-message--success">{{ message }}</p>
    <p v-if="error" class="form-message form-message--error">{{ error }}</p>
  </section>
</template>

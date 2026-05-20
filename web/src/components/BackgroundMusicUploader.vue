<script setup lang="ts">
import { ref } from "vue";

import { ApiError, uploadBackgroundMusic } from "../api/client";
import type { BackgroundMusic } from "../types/project";

const props = defineProps<{
  projectId: string;
  music: BackgroundMusic | null;
}>();

const emit = defineEmits<{
  uploaded: [music: BackgroundMusic];
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
    error.value = "请先选择音频文件。";
    return;
  }

  isUploading.value = true;
  error.value = "";
  message.value = "";
  try {
    const music = await uploadBackgroundMusic(props.projectId, selectedFile.value);
    message.value = "背景音乐已保存。";
    emit("uploaded", music);
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "背景音乐上传失败。";
  } finally {
    isUploading.value = false;
  }
}
</script>

<template>
  <section class="panel">
    <div class="panel__header">
      <div>
        <p class="eyebrow">可选音频</p>
        <h2>背景音乐</h2>
      </div>
      <span v-if="music" class="status-pill status-pill--ok">已保存</span>
    </div>

    <div v-if="music" class="meta-row">
      <span>{{ music.original_filename }}</span>
      <span>{{ music.volume_gain_db }} dB</span>
    </div>

    <label class="file-drop">
      <input type="file" accept=".mp3,.wav,.m4a,.aac,.ogg,audio/*" @change="onFileChange" />
      <span>{{ selectedFile?.name ?? music?.original_filename ?? "选择音频" }}</span>
    </label>

    <button class="button" :disabled="isUploading" @click="submit">
      {{ isUploading ? "正在上传..." : "上传音乐" }}
    </button>

    <p v-if="message" class="form-message form-message--success">{{ message }}</p>
    <p v-if="error" class="form-message form-message--error">{{ error }}</p>
  </section>
</template>

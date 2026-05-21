<script setup lang="ts">
import { computed } from "vue";

import type { StoryboardShot } from "../types/project";

const props = defineProps<{
  imageSrc: string;
  shot: StoryboardShot | null;
}>();

const cropStyle = computed(() => {
  if (!props.shot) {
    return {};
  }
  const [x1, y1, x2, y2] = props.shot.crop_start;
  return {
    left: `${x1 * 100}%`,
    top: `${y1 * 100}%`,
    width: `${Math.max(0, x2 - x1) * 100}%`,
    height: `${Math.max(0, y2 - y1) * 100}%`,
  };
});
</script>

<template>
  <section class="panel crop-preview">
    <div class="panel__header">
      <div>
        <p class="eyebrow">裁切预览</p>
        <h2>{{ shot?.id ?? "选择镜头" }}</h2>
      </div>
      <span v-if="shot" class="status-pill">{{ shot.type }}</span>
    </div>

    <div v-if="imageSrc" class="crop-preview__frame">
      <img :src="imageSrc" alt="素材预览" />
      <span v-if="shot" class="crop-preview__rect" :style="cropStyle"></span>
    </div>
    <div v-else class="preview-placeholder">暂无图片预览</div>

    <p v-if="shot" class="muted">
      {{ shot.start_sec.toFixed(2) }}s - {{ shot.end_sec.toFixed(2) }}s
    </p>
  </section>
</template>

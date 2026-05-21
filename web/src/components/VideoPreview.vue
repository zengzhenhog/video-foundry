<script setup lang="ts">
defineProps<{
  src: string;
  label: string;
}>();
</script>

<template>
  <section class="panel video-preview">
    <div class="panel__header">
      <div>
        <p class="eyebrow">视频预览</p>
        <h2>{{ label }}</h2>
      </div>
    </div>

    <video v-if="src" :src="src" controls preload="metadata"></video>
    <div v-else class="preview-placeholder">暂无视频</div>
  </section>
</template>

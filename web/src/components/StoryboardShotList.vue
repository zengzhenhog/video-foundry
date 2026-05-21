<script setup lang="ts">
import type { StoryboardShot } from "../types/project";

const props = defineProps<{
  modelValue: StoryboardShot[];
  selectedIndex: number;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: StoryboardShot[]];
  "update:selectedIndex": [value: number];
}>();

type CropField = "crop_start" | "crop_end";

function updateShot(index: number, patch: Partial<StoryboardShot>): void {
  const shots = props.modelValue.map((shot, shotIndex) =>
    shotIndex === index ? { ...shot, ...patch } : shot,
  );
  emit("update:modelValue", shots);
}

function updateCrop(index: number, field: CropField, coordinateIndex: number, value: number): void {
  const shot = props.modelValue[index];
  if (!shot) {
    return;
  }
  const crop = [...shot[field]] as [number, number, number, number];
  crop[coordinateIndex] = value;
  updateShot(index, { [field]: crop });
}
</script>

<template>
  <section class="panel storyboard-shots">
    <div class="panel__header">
      <div>
        <p class="eyebrow">镜头列表</p>
        <h2>{{ modelValue.length }} 个镜头</h2>
      </div>
    </div>

    <div class="storyboard-shot-list">
      <article
        v-for="(shot, index) in modelValue"
        :key="shot.id"
        class="storyboard-shot"
        :class="{ 'storyboard-shot--selected': index === selectedIndex }"
      >
        <button
          class="storyboard-shot__selector"
          type="button"
          :disabled="disabled"
          @click="emit('update:selectedIndex', index)"
        >
          <span>{{ shot.id }}</span>
          <strong>{{ shot.start_sec.toFixed(2) }}s - {{ shot.end_sec.toFixed(2) }}s</strong>
        </button>

        <div class="form-grid storyboard-shot__grid">
          <label>
            <span>Start</span>
            <input
              type="number"
              min="0"
              step="0.01"
              :disabled="disabled"
              :value="shot.start_sec"
              @input="updateShot(index, { start_sec: Number(($event.target as HTMLInputElement).value) })"
            />
          </label>
          <label>
            <span>End</span>
            <input
              type="number"
              min="0"
              step="0.01"
              :disabled="disabled"
              :value="shot.end_sec"
              @input="updateShot(index, { end_sec: Number(($event.target as HTMLInputElement).value) })"
            />
          </label>
          <label>
            <span>Type</span>
            <input
              type="text"
              :disabled="disabled"
              :value="shot.type"
              @input="updateShot(index, { type: ($event.target as HTMLInputElement).value })"
            />
          </label>
          <label>
            <span>Easing</span>
            <input
              type="text"
              :disabled="disabled"
              :value="shot.easing"
              @input="updateShot(index, { easing: ($event.target as HTMLInputElement).value })"
            />
          </label>
          <label class="form-grid__wide">
            <span>Caption</span>
            <textarea
              rows="2"
              :disabled="disabled"
              :value="shot.caption"
              @input="updateShot(index, { caption: ($event.target as HTMLTextAreaElement).value })"
            ></textarea>
          </label>
        </div>

        <div class="crop-grid">
          <label v-for="(_, cropIndex) in shot.crop_start" :key="`start-${shot.id}-${cropIndex}`">
            <span>Start {{ cropIndex + 1 }}</span>
            <input
              type="number"
              min="0"
              max="1"
              step="0.001"
              :disabled="disabled"
              :value="shot.crop_start[cropIndex]"
              @input="updateCrop(index, 'crop_start', cropIndex, Number(($event.target as HTMLInputElement).value))"
            />
          </label>
          <label v-for="(_, cropIndex) in shot.crop_end" :key="`end-${shot.id}-${cropIndex}`">
            <span>End {{ cropIndex + 1 }}</span>
            <input
              type="number"
              min="0"
              max="1"
              step="0.001"
              :disabled="disabled"
              :value="shot.crop_end[cropIndex]"
              @input="updateCrop(index, 'crop_end', cropIndex, Number(($event.target as HTMLInputElement).value))"
            />
          </label>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { ScriptSegment } from "../types/project";

interface ScriptEditorValue {
  language: string;
  duration_target_sec: number;
  title: string;
  narration: string;
  segments: ScriptSegment[];
  review_notes: string;
}

defineProps<{
  disabled?: boolean;
}>();

const model = defineModel<ScriptEditorValue>({ required: true });

function addSegment(): void {
  const duration = Number(model.value.duration_target_sec) || 0;
  const last = model.value.segments[model.value.segments.length - 1];
  const start = last ? last.end_sec : 0;
  const end = Math.max(start, duration || start + 5);
  model.value.segments.push({
    start_sec: start,
    end_sec: end,
    text: "",
  });
}

function removeSegment(index: number): void {
  model.value.segments.splice(index, 1);
}

function updateSegment(index: number, patch: Partial<ScriptSegment>): void {
  const current = model.value.segments[index];
  if (!current) {
    return;
  }
  model.value.segments[index] = { ...current, ...patch };
}

function numberFromEvent(event: Event): number {
  return Number((event.target as HTMLInputElement).value);
}

function textFromEvent(event: Event): string {
  return (event.target as HTMLTextAreaElement).value;
}
</script>

<template>
  <section class="panel script-editor">
    <div class="panel__header">
      <div>
        <p class="eyebrow">脚本编辑</p>
        <h2>旁白脚本</h2>
      </div>
      <button class="button" type="button" :disabled="disabled" @click="addSegment">
        添加段落
      </button>
    </div>

    <div class="form-grid">
      <label>
        <span>标题</span>
        <input v-model="model.title" type="text" maxlength="240" :disabled="disabled" />
      </label>
      <label>
        <span>语言</span>
        <input v-model="model.language" type="text" :disabled="disabled" />
      </label>
      <label>
        <span>目标时长（秒）</span>
        <input
          v-model.number="model.duration_target_sec"
          type="number"
          min="1"
          max="3600"
          :disabled="disabled"
        />
      </label>
      <label class="form-grid__wide">
        <span>完整旁白</span>
        <textarea v-model="model.narration" rows="8" :disabled="disabled" />
      </label>
      <label class="form-grid__wide">
        <span>来源审核说明</span>
        <textarea v-model="model.review_notes" rows="4" :disabled="disabled" />
      </label>
    </div>

    <div class="script-segments" aria-label="脚本段落">
      <article v-for="(segment, index) in model.segments" :key="index" class="script-segment">
        <div class="script-segment__header">
          <h3>段落 {{ index + 1 }}</h3>
          <button
            class="button"
            type="button"
            :disabled="disabled || model.segments.length <= 1"
            @click="removeSegment(index)"
          >
            移除
          </button>
        </div>

        <div class="form-grid">
          <label>
            <span>开始</span>
            <input
              :value="segment.start_sec"
              type="number"
              min="0"
              step="0.1"
              :disabled="disabled"
              @input="updateSegment(index, { start_sec: numberFromEvent($event) })"
            />
          </label>
          <label>
            <span>结束</span>
            <input
              :value="segment.end_sec"
              type="number"
              min="0"
              step="0.1"
              :disabled="disabled"
              @input="updateSegment(index, { end_sec: numberFromEvent($event) })"
            />
          </label>
          <label class="form-grid__wide">
            <span>段落文本</span>
            <textarea
              :value="segment.text"
              rows="3"
              :disabled="disabled"
              @input="updateSegment(index, { text: textFromEvent($event) })"
            />
          </label>
        </div>
      </article>
    </div>

    <aside class="script-preview" aria-label="结构化预览">
      <p class="eyebrow">结构化预览</p>
      <ol>
        <li v-for="(segment, index) in model.segments" :key="`preview-${index}`">
          <span>{{ segment.start_sec }}s - {{ segment.end_sec }}s</span>
          <p>{{ segment.text || "未填写" }}</p>
        </li>
      </ol>
    </aside>
  </section>
</template>

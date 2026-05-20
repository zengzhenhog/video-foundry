<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { ApiError, createProject } from "../api/client";
import StepNavigation from "../components/StepNavigation.vue";

const router = useRouter();
const isSaving = ref(false);
const error = ref("");

const form = reactive({
  name: "",
  target_language: "zh-CN",
  target_duration_sec: 60,
  formats: ["vertical_1080x1920"],
});

const formatOptions = [
  { value: "vertical_1080x1920", label: "竖屏 1080 x 1920" },
  { value: "landscape_1920x1080", label: "横屏 1920 x 1080" },
  { value: "square_1080x1080", label: "方形 1080 x 1080" },
];

async function submit(): Promise<void> {
  isSaving.value = true;
  error.value = "";
  try {
    const project = await createProject({
      name: form.name,
      target_language: form.target_language,
      target_duration_sec: Number(form.target_duration_sec),
      formats: form.formats,
    });
    await router.push(`/projects/${project.id}/assets`);
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "项目创建失败。";
  } finally {
    isSaving.value = false;
  }
}
</script>

<template>
  <main class="page-stack">
    <StepNavigation current="projects" />

    <section class="page-header">
      <div>
        <p class="eyebrow">新项目</p>
        <h1>创建项目</h1>
      </div>
    </section>

    <section class="panel panel--narrow">
      <form class="form-grid" @submit.prevent="submit">
        <label class="form-grid__wide">
          <span>名称</span>
          <input v-model="form.name" type="text" required maxlength="120" />
        </label>

        <label>
          <span>语言</span>
          <input v-model="form.target_language" type="text" required />
        </label>

        <label>
          <span>时长</span>
          <input v-model.number="form.target_duration_sec" type="number" min="1" max="3600" required />
        </label>

        <fieldset class="format-fieldset form-grid__wide">
          <legend>输出规格</legend>
          <label v-for="option in formatOptions" :key="option.value" class="checkbox-row">
            <input v-model="form.formats" type="checkbox" :value="option.value" />
            <span>{{ option.label }}</span>
          </label>
        </fieldset>

        <button class="button button--primary" type="submit" :disabled="isSaving || !form.formats.length">
          {{ isSaving ? "正在创建..." : "创建" }}
        </button>
      </form>

      <p v-if="error" class="form-message form-message--error">{{ error }}</p>
    </section>
  </main>
</template>

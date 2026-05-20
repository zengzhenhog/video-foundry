<script setup lang="ts">
defineProps<{
  projectId?: string;
  current: "projects" | "assets" | "script" | "render";
}>();

const steps = [
  { key: "projects", label: "项目" },
  { key: "assets", label: "素材" },
  { key: "script", label: "脚本" },
  { key: "render", label: "渲染" },
] as const;

type StepKey = (typeof steps)[number]["key"];

function isDisabled(key: StepKey, projectId?: string): boolean {
  return key !== "projects" && (key !== "assets" || !projectId);
}

function stepTo(key: StepKey, projectId?: string): string {
  if (key === "projects") {
    return "/projects";
  }
  if (key === "assets" && projectId) {
    return `/projects/${projectId}/assets`;
  }
  return "#";
}
</script>

<template>
  <nav class="step-navigation" aria-label="项目流程">
    <RouterLink
      v-for="step in steps"
      :key="step.key"
      class="step-navigation__item"
      :class="{
        'step-navigation__item--active': step.key === current,
        'step-navigation__item--disabled': isDisabled(step.key, projectId),
      }"
      :to="stepTo(step.key, projectId)"
      :aria-disabled="isDisabled(step.key, projectId)"
      @click="isDisabled(step.key, projectId) && $event.preventDefault()"
    >
      {{ step.label }}
    </RouterLink>
  </nav>
</template>

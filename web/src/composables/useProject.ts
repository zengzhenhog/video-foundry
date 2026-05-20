import { ref } from "vue";

import { ApiError, getProject } from "../api/client";
import type { ProjectDetail } from "../types/project";

export function useProject(projectId: string) {
  const project = ref<ProjectDetail | null>(null);
  const isLoading = ref(false);
  const error = ref("");

  async function loadProject(): Promise<void> {
    isLoading.value = true;
    error.value = "";
    try {
      project.value = await getProject(projectId);
    } catch (caught) {
      error.value = caught instanceof ApiError ? caught.message : "无法加载项目。";
    } finally {
      isLoading.value = false;
    }
  }

  return {
    project,
    isLoading,
    error,
    loadProject,
  };
}

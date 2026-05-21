import { computed, getCurrentInstance, onBeforeUnmount, ref } from "vue";

import { ApiError, getJob } from "../api/client";
import type { JobRecord, JobStatus } from "../types/project";

const TERMINAL_STATUSES = new Set<JobStatus>(["succeeded", "failed", "cancelled"]);

interface UseJobPollingOptions {
  intervalMs?: number;
  onFinished?: (job: JobRecord) => void | Promise<void>;
}

export function useJobPolling(options: UseJobPollingOptions = {}) {
  const intervalMs = options.intervalMs ?? 1200;
  const job = ref<JobRecord | null>(null);
  const error = ref("");
  const isPolling = ref(false);
  const isTerminal = computed(() => Boolean(job.value && TERMINAL_STATUSES.has(job.value.status)));

  let activeJobId: string | null = null;
  let timer: ReturnType<typeof window.setTimeout> | null = null;

  async function start(jobId: string, initialJob?: JobRecord): Promise<void> {
    stop();
    activeJobId = jobId;
    job.value = initialJob ?? null;
    error.value = "";
    isPolling.value = true;
    await pollOnce();
  }

  function stop(): void {
    if (timer) {
      window.clearTimeout(timer);
      timer = null;
    }
    activeJobId = null;
    isPolling.value = false;
  }

  async function pollOnce(): Promise<void> {
    const jobId = activeJobId;
    if (!jobId) {
      return;
    }

    try {
      const nextJob = await getJob(jobId);
      if (activeJobId !== jobId) {
        return;
      }
      job.value = nextJob;
      if (TERMINAL_STATUSES.has(nextJob.status)) {
        isPolling.value = false;
        activeJobId = null;
        await options.onFinished?.(nextJob);
        return;
      }
      timer = window.setTimeout(() => {
        void pollOnce();
      }, intervalMs);
    } catch (caught) {
      if (activeJobId !== jobId) {
        return;
      }
      error.value = caught instanceof ApiError ? caught.message : "任务状态读取失败。";
      isPolling.value = false;
      activeJobId = null;
    }
  }

  if (getCurrentInstance()) {
    onBeforeUnmount(stop);
  }

  return {
    job,
    error,
    isPolling,
    isTerminal,
    start,
    stop,
  };
}

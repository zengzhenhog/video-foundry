<script setup lang="ts">
const upcomingSteps = [
  "Create projects",
  "Add source assets",
  "Review scripts",
  "Render exports",
] as const;
</script>

<template>
  <main class="app-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">VideoFoundry</p>
        <h1>Auto Image workspace</h1>
      </div>
      <span class="status-pill">Foundation ready</span>
    </header>

    <section class="workspace-placeholder" aria-labelledby="workspace-title">
      <div>
        <h2 id="workspace-title">Workbench entry</h2>
        <p>
          This shell is ready for the staged asset, script, voice, storyboard, and render workflows.
        </p>
      </div>
      <ol class="step-list" aria-label="Upcoming workflow steps">
        <li v-for="step in upcomingSteps" :key="step">
          {{ step }}
        </li>
      </ol>
    </section>
  </main>
</template>

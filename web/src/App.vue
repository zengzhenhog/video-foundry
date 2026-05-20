<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink class="brand-link" to="/projects">
        <span class="brand-mark">VF</span>
        <span>
          <span class="eyebrow">video-foundry</span>
          <strong>视频工作台</strong>
        </span>
      </RouterLink>
      <RouterLink class="primary-link" to="/projects/new">新建项目</RouterLink>
    </header>

    <RouterView />
  </div>
</template>


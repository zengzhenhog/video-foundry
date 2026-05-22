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
      <nav class="topbar-actions" aria-label="主导航">
        <RouterLink class="button" to="/batch">批量队列</RouterLink>
        <RouterLink class="primary-link" to="/projects/new">新建项目</RouterLink>
      </nav>
    </header>

    <RouterView />
  </div>
</template>


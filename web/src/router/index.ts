import { createRouter, createWebHistory } from "vue-router";

import ProjectAssets from "../pages/ProjectAssets.vue";
import ProjectCreate from "../pages/ProjectCreate.vue";
import ProjectList from "../pages/ProjectList.vue";
import ProjectScript from "../pages/ProjectScript.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/projects" },
    { path: "/projects", name: "projects", component: ProjectList },
    { path: "/projects/new", name: "project-create", component: ProjectCreate },
    {
      path: "/projects/:id",
      redirect: (to) => ({ name: "project-assets", params: { id: to.params.id } }),
    },
    {
      path: "/projects/:id/assets",
      name: "project-assets",
      component: ProjectAssets,
      props: true,
    },
    {
      path: "/projects/:id/script",
      name: "project-script",
      component: ProjectScript,
      props: true,
    },
  ],
});

export default router;

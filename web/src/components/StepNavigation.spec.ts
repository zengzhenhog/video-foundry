import { RouterLinkStub, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import StepNavigation from "./StepNavigation.vue";

describe("StepNavigation", () => {
  it("显示项目流程并高亮素材步骤", () => {
    const wrapper = mount(StepNavigation, {
      props: { current: "assets", projectId: "prj_123" },
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
        },
      },
    });

    expect(wrapper.text()).toContain("项目");
    expect(wrapper.text()).toContain("素材");
    expect(wrapper.text()).toContain("脚本");
    expect(wrapper.text()).toContain("旁白");
    expect(wrapper.text()).toContain("分镜");
    expect(wrapper.find(".step-navigation__item--active").text()).toBe("素材");
    expect(wrapper.findAllComponents(RouterLinkStub)[2].props("to")).toBe("/projects/prj_123/script");
    expect(wrapper.findAllComponents(RouterLinkStub)[3].props("to")).toBe("/projects/prj_123/voice");
    expect(wrapper.findAllComponents(RouterLinkStub)[4].props("to")).toBe("/projects/prj_123/storyboard");
    expect(wrapper.findAllComponents(RouterLinkStub)[5].props("to")).toBe("/projects/prj_123/render");
  });
});

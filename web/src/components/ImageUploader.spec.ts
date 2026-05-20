import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import ImageUploader from "./ImageUploader.vue";
import { uploadImage } from "../api/client";
import type { Asset } from "../types/project";

vi.mock("../api/client", () => ({
  ApiError: class ApiError extends Error {},
  uploadImage: vi.fn(),
}));

const savedAsset: Asset = {
  schema_version: "1.0",
  project_id: "prj_123",
  title: "",
  source_url: null,
  original_filename: "source.jpg",
  image_original_path: "assets/original.jpg",
  image_preview_path: "assets/preview.jpg",
  image_format: "jpeg",
  description: "",
  credit: "",
  width: 1080,
  height: 1920,
  sha256: "a".repeat(64),
  created_at: "2026-05-20T00:00:00Z",
  updated_at: "2026-05-20T00:00:00Z",
};

describe("ImageUploader", () => {
  it("上传选中的文件并抛出保存后的素材", async () => {
    vi.mocked(uploadImage).mockResolvedValue(savedAsset);
    const wrapper = mount(ImageUploader, {
      props: { projectId: "prj_123", asset: null },
    });
    const file = new File(["image"], "source.jpg", { type: "image/jpeg" });
    const input = wrapper.find<HTMLInputElement>("input[type='file']");

    Object.defineProperty(input.element, "files", {
      value: [file],
      configurable: true,
    });
    await input.trigger("change");
    await wrapper.find("button").trigger("click");

    expect(uploadImage).toHaveBeenCalledWith("prj_123", file);
    expect(wrapper.emitted("uploaded")?.[0]).toEqual([savedAsset]);
  });
});

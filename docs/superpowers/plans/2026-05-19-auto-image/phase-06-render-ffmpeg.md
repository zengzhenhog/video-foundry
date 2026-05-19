# Phase 6：渲染与 FFmpeg 合成

目标：从原图、分镜、旁白、可选背景音乐和字幕生成 MP4。渲染必须只使用确定性裁切、缩放、平移和覆盖层，不得生成式修改原图内容。

## 前置条件

- Phase 5 已完成。
- 项目存在原图、已批准脚本、已批准分镜、字幕文件和旁白音频。

## 允许修改

- `src/auto_image/renderer/**`
- `src/auto_image/ffmpeg/**`
- `src/auto_image/audio/mixer.py`
- `src/auto_image/api/routes/**`
- `src/auto_image/api/main.py` 或 Phase 1 建立的集中 router 聚合文件
- `src/auto_image/shared/**` 中与 render preset 和输出路径相关的内容
- `config/render-presets.json`
- `tests/unit/**`
- `tests/integration/**`
- `web/src/**` 中渲染页所需的最小改动

## 必须新增或修改的文件

- `src/auto_image/renderer/__init__.py`
- `src/auto_image/renderer/crops.py`
- `src/auto_image/renderer/frame_renderer.py`
- `src/auto_image/renderer/subtitle_overlay.py`
- `src/auto_image/renderer/manifest.py`
- `src/auto_image/ffmpeg/__init__.py`
- `src/auto_image/ffmpeg/command_builder.py`
- `src/auto_image/ffmpeg/assembler.py`
- `src/auto_image/audio/mixer.py`
- `src/auto_image/api/routes/render.py`
- `web/src/pages/ProjectRender.vue`
- `web/src/components/VideoPreview.vue`
- 相关测试文件

## 不要做

- 不使用生成式图像或视频模型。
- 不使用 AI 插帧、AI 超分、扩图、重绘或修补。
- 不把任务系统做完整；长任务跟踪留到 Phase 7。Phase 6 可以用同步或简单后台占位方式完成渲染。
- 不实现一键生成控制台。

## 原子执行步骤

建议把本阶段拆成三个连续小轮次执行：

- 6A：crop/easing、帧渲染、字幕和 credit 覆盖、manifest。
- 6B：FFmpeg 命令构建、音频混音、合成。
- 6C：render/export API、最小前端渲染页和端到端验证。

1. 在 `renderer/crops.py` 实现 crop 插值和 easing。输入 start crop、end crop、时间进度，输出当前 crop。
2. 在 `frame_renderer.py` 实现帧渲染：
   - 读取原图。
   - 根据 storyboard shot 和 crop 插值裁切。
   - 缩放到 render preset 尺寸。
   - 写入 `renders/frames/`。
3. 在 `subtitle_overlay.py` 实现字幕和 credit 覆盖。字幕和 credit 必须处于安全区内，credit 在最终视频中可见。
4. 在 `renderer/manifest.py` 生成 `renders/render-manifest.json`，记录原图 hash、format、fps、输出尺寸、使用的 storyboard version、字幕文件、credit 文本与覆盖位置、输出文件和关键帧摘要。该文件是 Phase 7 质量门禁的重要证据。
5. 在 `ffmpeg/command_builder.py` 构建 FFmpeg 命令。命令构建必须可单元测试，不直接执行。
6. 在 `audio/mixer.py` 实现背景音乐参数处理：
   - 默认 `volume_gain_db = -18`
   - 支持 loop。
   - 支持裁剪到视频时长。
   - 支持 fade in 和 fade out。
   - 没有背景音乐时，混音逻辑必须走旁白-only 路径。
7. 在 `ffmpeg/assembler.py` 执行合成：
   - 帧序列或静音视频。
   - 旁白音频。
   - 可选背景音乐。
   - 字幕和 credit。
   - 输出 `renders/preview_{format}.mp4` 和 `exports/final_{format}.mp4`。
8. 实现 API，并完成路由注册：
   - `POST /api/projects/{project_id}/render`
   - `POST /api/projects/{project_id}/export`
9. API 执行前校验必要输入存在：原图、已批准分镜、旁白音频、字幕、credit。背景音乐不存在时不应失败。
10. 前端实现渲染页。第一版至少能触发渲染、显示状态文本、播放生成的视频。
11. 补充测试：
    - crop 插值正确。
    - 帧尺寸符合 preset。
    - FFmpeg 命令包含必要输入和输出。
    - 缺少 credit 或未批准分镜时拒绝渲染。
    - 有背景音乐时命令包含混音参数。
    - 无背景音乐时命令仍能生成旁白-only 输出。
    - render manifest 包含原图 hash、credit 覆盖和输出文件信息。

## 验收标准

- 可生成至少一个 5 秒预览视频。
- 在支持 FFmpeg 的环境中，可生成完整目标时长视频；自动化测试可使用短时长 fixture，完整目标时长作为手工或集成验证记录。
- 输出文件位于 `exports/final_{format}.mp4`。
- 如有背景音乐，背景音乐音量低于旁白，不遮挡旁白。
- 视频必须包含可见 credit。
- `renders/render-manifest.json` 存在，并可用于证明使用了原图 hash、credit 覆盖和确定性渲染规则。
- 渲染逻辑只读取原图，不生成新图像内容。

## 验证命令

```powershell
python -m pytest tests/unit tests/integration
python -m compileall src
ffmpeg -version
```

在 `web/` 目录运行：

```powershell
npm run typecheck
npm run build
```

如果测试环境缺少 FFmpeg，应跳过依赖 FFmpeg 的集成测试或标记 xfail，并在最终回复中明确说明。

## 预期输出

- `projects/{project_id}/renders/preview_{format}.mp4`
- `projects/{project_id}/exports/final_{format}.mp4`
- `projects/{project_id}/renders/render-manifest.json`
- `projects/{project_id}/renders/frames/` 中的渲染帧或临时产物

## 下一阶段入口

Phase 7 将把渲染、导出等长任务纳入 job 系统，补充日志、失败诊断和质量门禁。

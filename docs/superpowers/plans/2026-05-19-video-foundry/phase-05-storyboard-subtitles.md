# Phase 5：分镜与字幕

目标：根据已批准脚本生成可渲染的分镜和字幕。完成后，用户可以在页面查看、编辑并批准分镜，系统可以生成 SRT 和 VTT 文件。

## 前置条件

- Phase 4 已完成。
- 项目存在已批准脚本。
- 如已生成旁白，可使用旁白时长；否则使用脚本目标时长。

## 允许修改

- `src/video_foundry/storyboard/**`
- `src/video_foundry/subtitles/**`
- `src/video_foundry/api/routes/**`
- `src/video_foundry/api/main.py` 或 Phase 1 建立的集中 router 聚合文件
- `src/video_foundry/shared/schemas.py`
- `src/video_foundry/shared/storage.py`
- `config/render-presets.json`
- `tests/unit/**`
- `tests/integration/**`
- `web/src/**`

## 必须新增或修改的文件

- `src/video_foundry/storyboard/__init__.py`
- `src/video_foundry/storyboard/planner.py`
- `src/video_foundry/storyboard/validator.py`
- `src/video_foundry/subtitles/__init__.py`
- `src/video_foundry/subtitles/generator.py`
- `src/video_foundry/api/routes/storyboard.py`
- `src/video_foundry/api/routes/subtitles.py`
- `web/src/pages/ProjectStoryboard.vue`
- `web/src/components/StoryboardShotList.vue`
- `web/src/components/CropPreview.vue`
- 相关测试文件

## 不要做

- 不渲染视频帧。
- 不调用 FFmpeg。
- 不实现拖拽式高级裁切编辑；第一版用表单或 JSON 编辑即可。
- 不允许未批准脚本生成分镜。
- 不允许非法 crop 或时间线进入批准状态。

## 原子执行步骤

1. 在 `storyboard/planner.py` 实现基础 planner：
   - 输入脚本 segments、目标时长、format、fps 和安全区。
   - 输出时间连续、不重叠的 shots。
   - 每个 shot 包含 start_sec、end_sec、type、crop_start、crop_end、easing、caption。
2. planner 第一版可以使用确定性规则，例如按脚本段落分配时长，并使用轻微 push-in 或 pan crop。不得生成式修改图片。
3. 在 `storyboard/validator.py` 实现校验：
   - 时间线从 0 开始连续。
   - shot 不重叠，end 大于 start。
   - crop 坐标均在 `[0, 1]`。
   - crop 宽高大于最小阈值。
   - 最大 zoom 不超过 render preset 阈值。
4. 实现分镜 API，并完成路由注册：
   - `POST /api/projects/{project_id}/storyboard/generate`
   - `GET /api/projects/{project_id}/storyboard`
   - `PUT /api/projects/{project_id}/storyboard`
   - `POST /api/projects/{project_id}/storyboard/approve`
5. 状态规则：
   - 生成或编辑后为 `storyboard_ready`。
   - 批准后为 `storyboard_approved`。
   - 修改已批准分镜时撤销批准，并标记字幕、渲染和导出 stale。
6. 在 `subtitles/generator.py` 实现字幕断句和时间分配。第一版可按 script segments 生成。
7. 实现 `POST /api/projects/{project_id}/subtitles/generate`，输出：
   - `subtitles/subtitles.srt`
   - `subtitles/subtitles.vtt`
   - 如果字幕基于已批准分镜生成，字幕应记录对应 storyboard version，分镜修改后字幕必须 stale。
8. 前端实现分镜页面。至少展示 shot 列表、时间、caption、crop 数值和批准状态。
9. `CropPreview.vue` 第一版可以基于图片预览和 crop 矩形显示基础裁切框，不要求真实渲染效果。
10. 补充测试：
    - shot 时间连续。
    - crop 坐标越界会失败。
    - 最大 zoom 超限会失败。
    - SRT/VTT 格式可生成。
    - 未批准脚本不能生成分镜。

## 验收标准

- `storyboard/storyboard.json` 中所有 shots 时间连续且不重叠。
- 所有 crop 坐标合法。
- SRT 和 VTT 文件可生成。
- 页面能展示每个镜头的时间、字幕和裁切框。
- 未通过 validator 的分镜不能被批准。

## 验证命令

```powershell
python -m pytest tests/unit tests/integration
python -m compileall src
```

在 `web/` 目录运行：

```powershell
npm run typecheck
npm run build
```

## 预期输出

- `projects/{project_id}/storyboard/storyboard.json`
- `projects/{project_id}/subtitles/subtitles.srt`
- `projects/{project_id}/subtitles/subtitles.vtt`
- 前端分镜审核页面

## 下一阶段入口

Phase 6 将使用原图、分镜、字幕、旁白和可选背景音乐生成 MP4。


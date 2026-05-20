# Phase 8：完整审核 UI 与一键生成

目标：形成可使用的视频生产控制台。用户可以从空项目一路完成素材上传、脚本审核、旁白、分镜、渲染、质量报告和 MP4 下载，不需要手动调用后端接口。背景音乐仍为可选输入。

## 前置条件

- Phase 7 已完成。
- 所有核心后端能力都有 API。
- 前端已有各阶段页面和基础组件。

## 允许修改

- `src/video_foundry/api/routes/**`
- `src/video_foundry/api/main.py` 或 Phase 1 建立的集中 router 聚合文件
- `src/video_foundry/jobs/**`
- `src/video_foundry/shared/**` 中与流程状态摘要相关的内容
- `web/src/**`
- `tests/unit/**`
- `tests/integration/**`
- `web` 测试配置和前端测试

## 必须新增或修改的文件

- `src/video_foundry/api/routes/pipeline.py`
- `src/video_foundry/api/routes/downloads.py`
- `web/src/pages/ProjectDetail.vue`
- `web/src/pages/ProjectExport.vue`
- `web/src/components/DownloadLinks.vue`
- `web/src/components/StepNavigation.vue`
- `web/src/composables/useProject.ts`
- `web/src/composables/useJobPolling.ts`
- 相关测试文件

## 不要做

- 不新增 Phase 9 的批量队列、NASA 导入或 SQLite。
- 不绕过脚本批准和分镜批准。
- 不把一键生成做成黑盒；每一步仍要落盘并可审核。
- 不隐藏失败原因。

## 原子执行步骤

1. 整理项目详情页为步骤式工作台。步骤至少包含：素材、脚本、旁白、分镜、渲染、导出。
2. 每个步骤展示：
   - 当前状态。
   - 缺失条件。
   - 可执行操作。
   - 最近错误。
   - 进入对应详情页的入口。
3. 实现 `POST /api/projects/{project_id}/generate-all`，并完成路由注册。内部按顺序执行缺失步骤：
   - 校验素材和 credit。
   - 生成脚本但不自动批准；如果生成后仍缺少批准脚本，job 必须停止在 `needs_script_approval` 或等价状态。
   - 已有批准脚本后生成旁白。
   - 生成分镜但不自动批准；如果生成后仍缺少批准分镜，job 必须停止在 `needs_storyboard_approval` 或等价状态。
   - 已有批准分镜后生成字幕。
   - 渲染和导出。没有背景音乐时走旁白-only 合成路径。
4. 一键生成必须尊重审核门禁。需要人工批准时，job 应停在明确状态，并告诉前端下一步需要用户操作。
5. 实现下载入口：
   - `GET /api/projects/{project_id}/downloads`
   - 返回 MP4、字幕、音频、元数据和质量报告的可下载链接或路径列表。
   - 只返回实际存在且位于项目目录内的文件；缺失的推荐文件应以 `missing` 列表说明，而不是返回失效链接。
6. 前端实现最终预览：
   - 视频播放器。
   - 质量报告摘要。
   - 下载链接。
   - 重新渲染或重试入口。
7. 页面刷新后必须从项目文件和 API 恢复状态，不依赖前端内存。
8. 完善加载态、禁用态、错误态、重试态。按钮应根据后端状态禁用，避免重复提交。
9. 补充测试：
   - generate-all 在缺少批准脚本时停止并提示审核。
   - generate-all 在缺少批准分镜时停止并提示审核。
   - 已满足审批条件时能推进渲染 job。
   - 无背景音乐项目可以完成渲染、质量报告和下载列表。
   - downloads API 返回存在的文件。
   - 前端状态摘要和按钮禁用逻辑。
10. 做一次手工主流程验证，并记录最终回复中实际走通的步骤。

## 验收标准

- 用户可以从空项目一路操作到 MP4 导出。
- 每一步失败都有明确提示。
- 页面刷新后仍能从项目文件恢复状态。
- 不需要手动访问后端接口也能完成主流程。
- 一键生成不会绕过脚本和分镜审核。
- 下载入口能展示最终 MP4、字幕、音频、元数据和质量报告。
- 下载入口不会暴露项目目录之外的路径。

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

如已配置端到端测试：

```powershell
npm run test:e2e
```

手工验证至少走通：

1. 打开前端页面。
2. 创建项目。
3. 上传图片。
4. 输入文案和 credit。
5. 可选上传背景音乐；至少额外验证一次不上传背景音乐也能完成导出。
6. 配置 mock voice。
7. 生成脚本并批准。
8. 生成旁白。
9. 生成分镜并批准。
10. 生成字幕。
11. 渲染并导出视频。
12. 播放 MP4。
13. 检查字幕、旁白、credit 和质量报告；如上传了背景音乐，还要检查混音效果。

## 预期输出

- 完整项目控制台。
- `exports/final_{format}.mp4`
- `exports/quality-report.json`
- 可下载资源列表。

## 下一阶段入口

Phase 9 是生产加固和批量化增强，不属于 MVP 阻塞项。


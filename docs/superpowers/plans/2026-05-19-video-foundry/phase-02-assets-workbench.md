# Phase 2：素材上传与项目工作台

目标：用户可以从页面创建项目，上传图片、输入或上传文案、保存来源 URL 和 credit，并可选上传背景音乐。完成后，项目详情页可以展示图片预览和素材状态。

## 前置条件

- Phase 1 已完成。
- 项目 API、路径解析和 JSON 存储可用。

## 允许修改

- `src/video_foundry/api/routes/**`
- `src/video_foundry/api/main.py` 或 Phase 1 建立的集中 router 聚合文件
- `src/video_foundry/sources/**`
- `src/video_foundry/audio/background_music.py`
- `src/video_foundry/shared/**` 中与 Asset、BackgroundMusic、存储辅助相关的内容
- `pyproject.toml` 和 Python 锁文件，仅限补充上传、图片处理或测试必需依赖
- `tests/unit/**`
- `tests/integration/**`
- `web/src/**`
- `web/package.json` 和前端锁文件，仅限补充本阶段需要的前端依赖和脚本

## 必须新增或修改的文件

- `src/video_foundry/sources/__init__.py`
- `src/video_foundry/sources/upload_importer.py`
- `src/video_foundry/audio/__init__.py`
- `src/video_foundry/audio/background_music.py`
- `src/video_foundry/api/routes/assets.py`
- `web/src/api/client.ts`
- `web/src/types/project.ts`
- `web/src/router/index.ts`
- `web/src/pages/ProjectList.vue`
- `web/src/pages/ProjectCreate.vue`
- `web/src/pages/ProjectAssets.vue`
- `web/src/components/ImageUploader.vue`
- `web/src/components/TextInputPanel.vue`
- `web/src/components/BackgroundMusicUploader.vue`
- `web/src/components/StepNavigation.vue`
- 相关测试文件

## 不要做

- 不生成脚本或调用 LLM。
- 不生成旁白。
- 不生成分镜、字幕或视频。
- 不实现一键生成。
- 不绕过 credit 要求进入后续状态。

## 原子执行步骤

1. 实现图片上传接口 `POST /api/projects/{project_id}/assets/image`，并完成路由注册。保存原文件为 `assets/original.{ext}`，扩展名根据安全白名单和实际内容类型确定。
2. 使用 Pillow 读取图片，记录宽、高和格式。生成 `assets/preview.jpg`，预览图尺寸应适合页面展示，不覆盖原图。若图片无法被 Pillow 解析、尺寸低于 render preset 的最低要求或文件过大，应返回结构化错误。
3. 计算原图 sha256，写入 `metadata/asset.json`。
4. 实现文本和来源信息保存接口 `POST /api/projects/{project_id}/assets/text`。至少保存 title、description、source_url、credit。source_url 或 credit 为空时可以保存草稿，但不得把项目推进到 `asset_ready`，也不得允许进入脚本生成。
5. 实现背景音乐上传接口 `POST /api/projects/{project_id}/assets/background-music`。保存到 `audio/background_music.{ext}`，写入背景音乐元数据。背景音乐是可选输入；没有背景音乐时，项目仍应可进入后续主流程。第一版可以只验证扩展名和文件存在；音频时长可留到 FFmpeg 阶段读取。
6. 实现 `GET /api/projects/{project_id}/assets/preview`，返回图片预览文件。找不到预览时返回结构化错误或 404。
7. 更新项目读取 API，使项目详情包含素材状态摘要：是否有原图、是否有预览、是否有 source_url、是否有 credit、是否有背景音乐。
8. 如果已存在下游脚本、分镜、旁白、字幕、渲染或导出产物，修改图片、description、source_url 或 credit 时必须按 README 状态契约标记下游产物 stale。
9. 前端实现项目列表、项目创建页和素材页。页面流程应能从 `/projects` 到 `/projects/new` 再到 `/projects/:id/assets`。
10. 前端 API 封装集中在 `web/src/api/client.ts`，类型放在 `web/src/types/`。
11. 上传组件必须显示成功、失败、加载状态和后端错误消息。
12. 补充测试：
    - 图片上传后原图、预览和 asset.json 存在。
    - sha256 和尺寸写入正确。
    - 缺少 source_url 或 credit 时项目不能被标记为 `asset_ready`。
    - 背景音乐保存到正确目录。
    - 不上传背景音乐时项目仍可保持有效素材状态。
    - 前端关键组件或 composable 的基础测试。

## 验收标准

- 上传图片后页面可预览。
- `metadata/asset.json` 包含图片尺寸、hash、credit、description、source_url。
- 背景音乐文件保存到项目目录，并能通过项目详情读取状态。
- 不上传背景音乐时，后续脚本、旁白、分镜和渲染流程不应被阻塞。
- 缺少 source_url 或 credit 时，后端不会允许进入后续关键步骤。
- 页面刷新后仍能从后端恢复素材状态。

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

如前端测试已配置：

```powershell
npm run test
```

## 预期输出

- 可通过前端上传图片、保存文案、source_url 和 credit，并可选上传背景音乐。
- 项目目录中生成 `assets/original.*`、`assets/preview.jpg`、`metadata/asset.json`；如上传背景音乐，则生成 `audio/background_music.*`。

## 下一阶段入口

Phase 3 将基于素材和文案实现 AI 脚本生成、编辑和批准。


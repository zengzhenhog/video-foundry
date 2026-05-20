# video-foundry AI 可执行开发详细计划

日期：2026-05-19  
来源文档：`docs/system-design.md`、`docs/system-design.zh-CN.md`  
计划目标：指导 AI 开发代理分阶段实现一个本地优先的视频生成系统。用户可在页面中上传图片、文案、背景音乐，配置 AI 旁白音色，并把视频生成到本地。

## 1. 产品目标

系统应提供一个 Web 工作台，让用户完成以下主流程：

1. 创建视频项目。
2. 上传图片。
3. 输入或上传文案。
4. 上传背景音乐。
5. 配置 AI 旁白音色、语速、音量等参数。
6. 可选调用 AI 生成或改写旁白脚本。
7. 生成分镜、字幕、旁白音频。
8. 渲染并合成视频。
9. 在本地导出 MP4、字幕、音频、元数据和质量报告。

系统采用“本地优先”设计。第一版所有项目产物都保存到仓库下的 `projects/{project_id}` 目录，便于人工检查、失败恢复和后续批量化。

## 2. 关键约束

### 2.1 图片内容不可被生成式修改

渲染器只能对用户上传图片执行确定性的裁切、缩放、平移、淡入淡出、字幕叠加、署名叠加等操作。不得使用 AI 生成、重绘、扩图、修补、替换或改变图片主体内容。

### 2.2 AI 输出必须可审核

AI 生成的脚本、分镜、字幕建议都必须先落盘为结构化文件，然后才能进入下一步。用户可在页面上查看、编辑和批准脚本及分镜。

### 2.3 本地生成优先

视频最终输出到本地文件系统：

```text
projects/{project_id}/exports/
```

外部服务仅用于 LLM 文案生成和 TTS 语音合成。API key 必须通过 `.env` 或本地配置注入，不能写入项目元数据或提交到仓库。

## 3. 推荐技术栈

### 3.1 后端

- Python 3.11+
- FastAPI
- Pydantic v2
- Uvicorn
- Pillow 或 OpenCV
- FFmpeg
- pytest

### 3.2 前端

- Vite
- Vue 3
- TypeScript
- Vue Router
- Vue composables 作为第一阶段状态管理
- Pinia 作为后续可选增强
- Vitest
- Playwright 或浏览器手工验证作为端到端验证补充

### 3.3 存储

第一阶段不强制使用数据库。以项目目录和 JSON 文件作为事实来源。后续 Phase 9 可增加 SQLite 索引，用于项目列表、搜索、任务恢复和批量管理。

## 4. 目标目录结构

AI 开发代理应按以下结构创建代码：

```text
video-foundry/
  docs/
    system-design.md
    system-design.zh-CN.md
    superpowers/
      specs/
        2026-05-19-video-foundry-development-plan-design.md
  src/
    video_foundry/
      __init__.py
      api/
        __init__.py
        main.py
        routes/
        dependencies.py
      ai/
        __init__.py
        base.py
        mock_provider.py
        script_generator.py
      audio/
        __init__.py
        background_music.py
        mixer.py
      ffmpeg/
        __init__.py
        command_builder.py
        assembler.py
      jobs/
        __init__.py
        manager.py
        models.py
        runner.py
      quality/
        __init__.py
        checks.py
        report.py
      renderer/
        __init__.py
        crops.py
        frame_renderer.py
        subtitle_overlay.py
      shared/
        __init__.py
        config.py
        paths.py
        schemas.py
        storage.py
      sources/
        __init__.py
        upload_importer.py
      storyboard/
        __init__.py
        planner.py
        validator.py
      subtitles/
        __init__.py
        generator.py
      voice/
        __init__.py
        base.py
        mock_provider.py
        provider_registry.py
  web/
    index.html
    package.json
    src/
      main.ts
      App.vue
      router/
      api/
      composables/
      components/
      pages/
      styles/
      types/
  config/
    render-presets.json
    voices.example.json
    providers.example.env
  projects/
    .gitkeep
  tests/
    unit/
    integration/
```

## 5. 核心数据模型

所有后端模型必须定义在 `src/video_foundry/shared/schemas.py`，并通过 Pydantic 校验。

### 5.1 Project

字段：

- `id`
- `name`
- `status`
- `target_language`
- `target_duration_sec`
- `formats`
- `created_at`
- `updated_at`
- `current_step`

状态枚举：

```text
draft
asset_ready
script_ready
script_approved
storyboard_ready
storyboard_approved
voice_ready
rendered
exported
failed
```

### 5.2 Asset

字段：

- `project_id`
- `title`
- `source_url`
- `image_original_path`
- `image_preview_path`
- `description`
- `credit`
- `width`
- `height`
- `sha256`
- `created_at`

### 5.3 Script

字段：

- `project_id`
- `language`
- `duration_target_sec`
- `title`
- `narration`
- `segments`
- `review_notes`
- `approved`
- `updated_at`

### 5.4 VoiceConfig

字段：

- `provider`
- `voice_id`
- `language`
- `speed`
- `volume_gain_db`
- `style`
- `settings`
- `audio_path`
- `duration_sec`

### 5.5 BackgroundMusic

字段：

- `file_path`
- `original_filename`
- `duration_sec`
- `volume_gain_db`
- `loop`
- `fade_in_sec`
- `fade_out_sec`

### 5.6 Storyboard

字段：

- `version`
- `format`
- `fps`
- `duration_sec`
- `safe_area`
- `shots`
- `approved`

每个 shot 字段：

- `id`
- `start_sec`
- `end_sec`
- `type`
- `crop_start`
- `crop_end`
- `easing`
- `caption`

### 5.7 RenderJob

字段：

- `id`
- `project_id`
- `type`
- `status`
- `progress`
- `started_at`
- `finished_at`
- `error`
- `output_paths`

### 5.8 QualityReport

字段：

- `project_id`
- `passed`
- `checks`
- `warnings`
- `errors`
- `created_at`

## 6. 项目产物规范

每个项目目录必须稳定落盘：

```text
projects/{project_id}/
  project.json
  assets/
    original.{ext}
    preview.jpg
  metadata/
    asset.json
  script/
    script.md
    script.json
  storyboard/
    storyboard.json
  audio/
    narration.wav
    narration.mp3
    voice.json
    background_music.{ext}
    mix.json
  subtitles/
    subtitles.srt
    subtitles.vtt
  renders/
    silent_{format}.mp4
    preview_{format}.mp4
    frames/
  exports/
    final_{format}.mp4
    quality-report.json
  logs/
    pipeline.log
    error.json
```

## 7. API 设计

FastAPI 应提供以下 REST 接口。每个接口都应返回结构化 JSON 错误，不直接返回未处理异常。

### 7.1 项目

```text
POST /api/projects
GET  /api/projects
GET  /api/projects/{project_id}
DELETE /api/projects/{project_id}
```

### 7.2 素材上传

```text
POST /api/projects/{project_id}/assets/image
POST /api/projects/{project_id}/assets/text
POST /api/projects/{project_id}/assets/background-music
GET  /api/projects/{project_id}/assets/preview
```

### 7.3 脚本

```text
POST /api/projects/{project_id}/script/generate
GET  /api/projects/{project_id}/script
PUT  /api/projects/{project_id}/script
POST /api/projects/{project_id}/script/approve
```

### 7.4 旁白

```text
GET  /api/voice/providers
GET  /api/voice/presets
PUT  /api/projects/{project_id}/voice/config
POST /api/projects/{project_id}/voice/generate
GET  /api/projects/{project_id}/voice/audio
```

### 7.5 分镜和字幕

```text
POST /api/projects/{project_id}/storyboard/generate
GET  /api/projects/{project_id}/storyboard
PUT  /api/projects/{project_id}/storyboard
POST /api/projects/{project_id}/storyboard/approve
POST /api/projects/{project_id}/subtitles/generate
```

### 7.6 渲染、导出、任务

```text
POST /api/projects/{project_id}/render
POST /api/projects/{project_id}/export
POST /api/projects/{project_id}/generate-all
GET  /api/jobs/{job_id}
GET  /api/projects/{project_id}/logs
GET  /api/projects/{project_id}/quality-report
GET  /api/projects/{project_id}/downloads
```

`generate-all` 只是编排入口，内部仍应按脚本、分镜、旁白、字幕、渲染、导出的步骤执行，并在每一步写入产物和日志。

## 8. 前端页面设计

前端位于 `web/`，使用 Vite + Vue + TypeScript。

### 8.1 页面

```text
/projects
/projects/new
/projects/:id
/projects/:id/assets
/projects/:id/script
/projects/:id/voice
/projects/:id/storyboard
/projects/:id/render
/projects/:id/export
```

### 8.2 组件

建议组件：

- `ProjectList.vue`
- `ProjectCreateForm.vue`
- `StepNavigation.vue`
- `ImageUploader.vue`
- `TextInputPanel.vue`
- `BackgroundMusicUploader.vue`
- `VoiceConfigForm.vue`
- `ScriptEditor.vue`
- `StoryboardShotList.vue`
- `CropPreview.vue`
- `JobStatusPanel.vue`
- `VideoPreview.vue`
- `QualityReportPanel.vue`
- `DownloadLinks.vue`

### 8.3 前端执行要求

- 所有 API 类型定义放在 `web/src/types/`。
- API 请求封装在 `web/src/api/client.ts`。
- 复杂页面状态优先封装为 composables，例如 `useProject.ts`、`useJobPolling.ts`。
- 第一版避免过度设计视觉组件库，使用简单、清晰、稳定的工作台布局。
- 页面必须能显示失败步骤、失败原因、重试入口和日志摘要。

## 9. 后端执行阶段

### Phase 0：项目基础设施

目标：建立可启动、可测试的前后端工程。

AI 执行任务：

1. 创建 Python 项目配置。
2. 创建 `src/video_foundry` 包结构。
3. 创建 FastAPI `main.py`。
4. 创建 Vue 3 + TypeScript 前端工程到 `web/`。
5. 创建 `.gitignore`，忽略 `.env`、`projects/*` 的大文件、缓存、虚拟环境、前端构建产物。
6. 创建 `config/render-presets.json`、`config/voices.example.json`、`config/providers.example.env`。
7. 创建基础测试目录。

验收标准：

- 后端服务可启动。
- 前端开发服务器可启动。
- `pytest` 至少能运行空测试或基础健康测试。
- 前端类型检查可运行。

### Phase 1：核心数据模型与本地存储

目标：建立项目目录和 JSON 存储能力。

AI 执行任务：

1. 在 `shared/schemas.py` 定义核心 Pydantic 模型。
2. 在 `shared/paths.py` 实现项目路径解析。
3. 在 `shared/storage.py` 实现 JSON 读写、原子写入、目录创建。
4. 实现 `POST /api/projects`、`GET /api/projects`、`GET /api/projects/{id}`。
5. 每个项目创建时生成 `project.json` 和必要子目录。

验收标准：

- 创建项目后，本地存在完整目录结构。
- 项目信息可通过 API 读取。
- 单元测试覆盖路径生成、JSON 读写、状态枚举校验。

### Phase 2：素材上传与项目工作台

目标：用户可从页面上传图片、文案、背景音乐和 credit。

AI 执行任务：

1. 实现图片上传接口，保存为 `assets/original.{ext}`。
2. 生成 `assets/preview.jpg`。
3. 计算图片宽高和 sha256。
4. 实现文案、credit、source URL 保存到 `metadata/asset.json`。
5. 实现背景音乐上传到 `audio/background_music.{ext}`。
6. 前端实现项目创建、素材上传、图片预览、音乐文件显示。

验收标准：

- 上传图片后页面可预览。
- `asset.json` 包含图片尺寸、hash、credit、description。
- 缺少 credit 时后端拒绝进入后续关键步骤。
- 背景音乐文件能保存并被项目详情读取。

### Phase 3：AI 文案与脚本审核

目标：系统可生成、编辑、保存和批准旁白脚本。

AI 执行任务：

1. 定义 `ai/base.py` provider 接口。
2. 实现 `ai/mock_provider.py`，不依赖外部服务。
3. 实现真实 provider 的配置入口，但第一轮可以只保留适配器骨架。
4. 实现 `script_generator.py`，输入文案、目标时长、语言，输出结构化 Script。
5. 实现脚本生成、读取、编辑、批准 API。
6. 前端实现脚本编辑器、生成按钮、保存按钮、批准按钮。

验收标准：

- mock provider 可生成确定性脚本。
- 用户可编辑脚本并保存。
- 只有批准后的脚本才能进入旁白和分镜生成。
- 测试覆盖脚本 schema、空文案、未批准状态。

### Phase 4：旁白音色与 TTS

目标：系统可配置 voice ID 并生成旁白音频。

AI 执行任务：

1. 定义 `voice/base.py` TTS provider 接口。
2. 实现 `voice/mock_provider.py`，生成测试音频或复制固定测试音频。
3. 实现 `provider_registry.py`，根据配置选择 provider。
4. 实现 `voice.json` 保存。
5. 实现旁白生成 API。
6. 前端实现 provider、voice ID、语速、音量、风格参数表单。
7. 页面支持试听生成后的旁白音频。

验收标准：

- mock TTS 可生成可播放音频文件。
- voice 配置不会保存 API key。
- 未批准脚本时不能生成旁白。
- 测试覆盖 provider 配置解析、缺失 voice ID、音频路径落盘。

### Phase 5：分镜与字幕

目标：生成可渲染的分镜和字幕。

AI 执行任务：

1. 实现 `storyboard/planner.py`，根据脚本段落、时长、格式生成 shots。
2. 实现 `storyboard/validator.py`，校验裁切窗口边界和最大 zoom。
3. 实现字幕断句和 SRT/VTT 生成。
4. 实现分镜生成、读取、编辑、批准 API。
5. 前端实现镜头列表和基础裁切预览。

验收标准：

- `storyboard.json` 中所有 shot 时间连续且不重叠。
- 所有 crop 坐标在 `[0, 1]` 范围内。
- 最大 zoom 不超过配置阈值。
- SRT 和 VTT 文件可生成。
- 页面能展示每个镜头的时间、字幕和裁切框。

### Phase 6：渲染与 FFmpeg 合成

目标：从原图、分镜、旁白、背景音乐生成 MP4。

AI 执行任务：

1. 实现 `renderer/crops.py`，负责 crop 插值和 easing。
2. 实现 `renderer/frame_renderer.py`，根据分镜生成目标尺寸帧。
3. 实现 `renderer/subtitle_overlay.py`，把字幕和 credit 渲染到安全区。
4. 实现 `ffmpeg/command_builder.py`，构建可测试的 FFmpeg 命令。
5. 实现 `ffmpeg/assembler.py`，合并静音视频、旁白、背景音乐和字幕。
6. 实现渲染 API 和导出 API。

验收标准：

- 可生成至少一个 5 秒预览视频。
- 可生成完整目标时长视频。
- 输出文件位于 `exports/final_{format}.mp4`。
- 背景音乐音量低于旁白，不遮挡旁白。
- 视频必须包含可见 credit。
- 测试覆盖 crop 插值、帧尺寸、FFmpeg 命令构建。

### Phase 7：任务系统、日志和质量门禁

目标：长任务可追踪、失败可诊断、导出前有质量报告。

AI 执行任务：

1. 实现 `jobs/manager.py`，维护 job 状态。
2. 实现 `jobs/runner.py`，用本地后台执行器运行长任务。
3. 每个任务写 `logs/pipeline.log`。
4. 失败时写 `logs/error.json`。
5. 实现 `quality/checks.py` 和 `quality/report.py`。
6. 前端实现任务状态轮询、日志摘要、失败重试入口。

验收标准：

- 页面能看到任务进度和最终状态。
- 失败任务包含 step、reason、retryable、suggested_correction。
- 导出前必须生成 `quality-report.json`。
- 未通过质量门禁时不能标记为成功导出。

### Phase 8：完整审核 UI 与一键生成

目标：形成可使用的视频生产控制台。

AI 执行任务：

1. 整理项目详情页为步骤式工作台。
2. 增加“一键生成”按钮，内部按审批状态执行缺失步骤。
3. 增加视频预览、下载入口、质量报告展示。
4. 完善脚本审核、分镜审核、旁白试听、最终预览体验。
5. 增加必要的加载态、禁用态、错误态和重试态。

验收标准：

- 用户可以从空项目一路操作到 MP4 导出。
- 每一步失败都有明确提示。
- 页面刷新后仍能从项目文件恢复状态。
- 不需要手动访问后端接口也能完成主流程。

### Phase 9：批量化与生产加固

目标：增强长期使用能力，不阻塞 MVP。

AI 执行任务：

1. 接入 NASA API 搜索和导入。
2. 增加批量项目队列。
3. 增加 provider 重试和限流。
4. 增加 SQLite 项目索引。
5. 增加并发渲染控制。
6. 增加缓存策略。
7. 增加发布平台集成预留接口。

验收标准：

- 批量任务不会破坏单项目主流程。
- provider 错误有重试和明确日志。
- SQLite 只是索引，不替代项目目录中的事实产物。

## 10. 背景音乐处理要求

背景音乐必须作为可选输入。实现时应遵守：

1. 支持 mp3、wav、m4a 等常见格式，具体由 FFmpeg 能力决定。
2. 上传后保存原文件，不覆盖旁白文件。
3. 合成时默认降低背景音乐音量。
4. 背景音乐短于视频时可 loop。
5. 背景音乐长于视频时裁剪。
6. 支持淡入淡出。
7. 最终混音必须保证旁白清晰。

推荐默认值：

```json
{
  "volume_gain_db": -18,
  "loop": true,
  "fade_in_sec": 1.0,
  "fade_out_sec": 2.0
}
```

## 11. AI provider 设计

LLM 和 TTS 必须通过 provider 接口隔离。业务代码不得直接依赖某个外部 SDK。

### 11.1 LLM provider 接口

能力：

- `generate_script(input) -> Script`
- `generate_storyboard(input) -> Storyboard`

要求：

- 必须有 mock provider。
- 外部 provider 的 API key 只从环境变量读取。
- LLM 输出必须经 Pydantic 校验。
- 校验失败时写错误日志，不进入下一步。

### 11.2 TTS provider 接口

能力：

- `synthesize(text, voice_config) -> VoiceResult`

要求：

- 必须有 mock provider。
- 第一版只支持已有 voice ID。
- 不实现本地声音克隆训练。
- 如果未来接入声音克隆，必须增加用户授权确认和敏感文件清理策略。

## 12. 渲染规则

渲染器必须遵守以下规则：

1. 原图只读。
2. 所有镜头运动来自 crop rectangle 插值。
3. 字幕和 credit 作为覆盖层渲染。
4. 不使用生成式图像或视频模型。
5. 不使用会产生新图像细节的 AI 插帧或 AI 超分。
6. 允许使用同一张原图生成模糊背景，但必须显式配置开启。
7. 竖屏、横屏、方形格式应通过 render preset 控制。

## 13. 质量门禁

导出前必须检查：

1. `assets/original.*` 存在。
2. 图片 hash 已记录。
3. credit 存在。
4. 文案或描述存在。
5. 脚本已批准。
6. 分镜已批准。
7. 所有 crop 坐标合法。
8. 最大 zoom 合法。
9. 旁白音频存在。
10. 背景音乐如存在则可被 FFmpeg 读取。
11. 字幕文件存在。
12. 最终视频包含可见 credit。
13. 导出 MP4 存在且文件大小大于最小阈值。

质量报告输出：

```text
projects/{project_id}/exports/quality-report.json
```

## 14. 测试计划

### 14.1 单元测试

必须覆盖：

- Pydantic schema 校验。
- 项目路径生成。
- JSON 存储。
- crop 坐标校验。
- shot 时间线连续性。
- 字幕断句。
- voice config 校验。
- FFmpeg 命令构建。

### 14.2 集成测试

必须覆盖：

- 创建项目。
- 上传测试图片。
- 保存文案和 credit。
- mock 生成脚本。
- mock 生成旁白。
- 生成分镜。
- 生成字幕。
- 渲染 5 秒预览。
- 导出测试 MP4。

### 14.3 前端测试

建议覆盖：

- 项目创建表单。
- 图片上传组件。
- 脚本编辑器。
- voice 配置表单。
- job 轮询 composable。
- 失败状态展示。

### 14.4 手工验证

第一版交付前必须手工走通：

1. 打开前端页面。
2. 创建项目。
3. 上传图片。
4. 输入文案和 credit。
5. 上传背景音乐。
6. 配置 mock voice 或真实 voice。
7. 生成脚本。
8. 批准脚本。
9. 生成分镜。
10. 批准分镜。
11. 生成视频。
12. 播放 MP4。
13. 检查字幕、旁白、背景音乐、credit 是否存在。

## 15. AI 开发代理执行规则

每次让 AI 执行一个阶段时，应提供：

1. 当前阶段编号。
2. 允许修改的文件范围。
3. 必须新增或修改的文件清单。
4. 不允许跨阶段提前实现的内容。
5. 验收命令。
6. 预期输出文件。

推荐执行提示模板：

```text
请执行 video-foundry 开发计划的 Phase X。

上下文：
- 阅读 docs/system-design.md
- 阅读 docs/superpowers/specs/2026-05-19-video-foundry-development-plan-design.md

本阶段目标：
- ...

允许修改：
- ...

不要做：
- ...

完成后请运行：
- ...

请在最终回复中说明：
- 修改了哪些文件
- 如何验证
- 哪些事项留到下一阶段
```

## 16. 推荐实施顺序

必须按以下顺序执行，除非人为修改计划：

```text
Phase 0 -> Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5 -> Phase 6 -> Phase 7 -> Phase 8 -> Phase 9
```

不得在 Phase 0 直接实现复杂渲染。不得在 Phase 2 直接接真实外部 provider。不得在 Phase 6 之前把一键生成当作完成标准。

## 17. MVP 完成定义

Phase 0 到 Phase 8 完成后，MVP 才算完成。MVP 必须满足：

1. 用户能通过 Vue 页面创建项目。
2. 用户能上传图片、文案、背景音乐。
3. 用户能配置 AI 旁白音色。
4. 用户能生成、编辑、批准脚本。
5. 用户能生成、批准分镜。
6. 系统能生成旁白音频和字幕。
7. 系统能用原图裁切运动生成视频。
8. 系统能合成旁白、背景音乐、字幕和 credit。
9. 系统能导出本地 MP4。
10. 系统能生成质量报告。
11. 失败时页面能展示原因和重试入口。

## 18. 后续扩展

Phase 9 之后可考虑：

- NASA 官方 API 搜索和素材导入。
- 多项目批量生产。
- 多语言脚本和字幕。
- 多 TTS provider 对比试听。
- 分镜裁切框可视化拖拽编辑。
- SQLite 或轻量数据库索引。
- 云端 worker。
- 发布平台导出预设。
- 团队审核和角色权限。

这些扩展不应阻塞本地视频生成主流程。


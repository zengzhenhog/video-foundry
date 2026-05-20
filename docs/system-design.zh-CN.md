# video-foundry 视频生产系统中文说明

版本：0.1  
日期：2026-05-19  
目标目录：`F:\code\video-foundry`  
来源文档：`docs/system-design.md`

## 1. 项目定位

本系统用于把官方发布的詹姆斯·韦伯太空望远镜高清图像，以及与之配套的官方文字说明，制作成带中文旁白的短视频。它不是一个生成式图像或生成式视频系统，而是一个以“真实图像保真”为核心约束的半自动视频生产流水线。

系统允许 AI 参与的部分主要是文字和音频：

- 根据官方说明生成中文旁白脚本。
- 将旁白拆分为镜头节奏和分镜计划。
- 生成字幕、标题、简介、内部审核备注等文本。
- 调用语音合成服务生成旁白音频。
- 汇总元数据、质量报告和导出记录。

系统明确禁止 AI 修改天文图像本身。视频中的运动效果必须来自对原始图像像素的确定性裁切、平移、缩放和淡入淡出，而不是通过 AI 补帧、扩图、重绘或重新生成图像细节。

## 2. 核心原则

### 2.1 图像必须保真

原始图像是整个系统最重要的资产。它必须被原样保存到项目目录中，例如：

```text
projects/{project_id}/assets/original.jpg
```

渲染器只能读取这张原图，并在每一帧中根据分镜里的裁切窗口生成画面。所谓“镜头运动”，本质上是裁切区域随时间变化：

- 起始裁切区域：`crop_start`
- 结束裁切区域：`crop_end`
- 每一帧按缓动函数插值
- 裁切后的图像缩放到目标画布
- 字幕、署名、片尾等覆盖层叠加在画面上方

这意味着视频看起来可以有推近、拉远、横移、局部放大等镜头语言，但画面内容始终来自官方原图，不产生任何新的天体结构或图像细节。

### 2.2 科学表述必须可靠

旁白和字幕只能依据官方说明生成。系统提示词和审核逻辑需要约束大模型：

- 不添加来源中没有的距离、年代、尺寸、天体类型或因果解释。
- 不编造望远镜仪器参数、曝光信息或观测细节。
- 如果官方文本本身带有不确定性，中文脚本也应保留这种不确定性。
- 生成内部审核备注，说明关键科学表述来自哪些官方描述。

对于面向公众的短视频，可以把语言写得更生动，但不能为了戏剧效果引入无来源的科学断言。

### 2.3 版权与署名必须可追溯

每个视频项目都必须保存来源 URL、图片版权信息、署名文本和原始描述。最终视频中也必须出现可见署名，通常放在片尾，也可以在视频角落以小字号展示。

系统设计中推荐参考以下来源：

- NASA Webb 图片库
- NASA Images API 文档
- NASA 媒体使用指南
- ESA/Webb 版权与使用说明

实现时应注意：NASA 素材通常可按 NASA 媒体指南使用，但不能暗示 NASA 对视频或账号背书；ESA/Webb 素材通常要求明确可见的 credit。

## 3. 总体架构

系统推荐采用本地优先架构，先实现为本地服务或本地单机流水线，后续再迁移到服务器或云端 worker。

整体流程如下：

```text
Source Import
  -> Asset Normalization
  -> Script Generation
  -> Storyboard Planning
  -> Voice Generation
  -> Subtitle Generation
  -> Programmatic Rendering
  -> FFmpeg Assembly
  -> Human Review
  -> Export
```

中文解释如下：

1. **来源导入**：用户输入官方图片 URL、说明文字、标题、来源链接和署名。
2. **素材规范化**：下载原图，提取尺寸、格式、色彩信息，生成预览图，并保存元数据。
3. **脚本生成**：基于官方说明生成中文旁白脚本和内部审核备注。
4. **分镜规划**：把脚本拆成若干镜头，并为每个镜头生成裁切窗口和时间段。
5. **语音生成**：用指定 TTS 服务把审核后的脚本转成旁白音频。
6. **字幕生成**：根据语音时间戳或对齐结果生成 SRT 和 WebVTT 字幕。
7. **程序化渲染**：使用 Python 渲染引擎从原图裁切窗口生成视频帧，并输出静音视频。
8. **FFmpeg 合成**：合并视频、旁白、字幕、片尾和可选背景音乐。
9. **人工审核**：检查科学表述、画面构图、字幕可读性和署名。
10. **最终导出**：生成竖屏、横屏或方形 MP4，以及字幕和质量报告。

## 4. 推荐技术选型

### 4.1 Python 项目结构

文档建议使用 Python-first 的项目结构：

```text
src/
  video_foundry/
    api/
    review_ui/
    renderer/
    storyboard/
    ffmpeg/
    voice/
    sources/
    shared/
tests/
  unit/
  integration/
```

这样做的好处是，API、审核 UI、渲染器和共享逻辑可以放在同一个 Python 工程中协同开发，同时又保持职责分离。

推荐模块职责：

- `src/video_foundry/api`：FastAPI API 服务。
- `src/video_foundry/review_ui`：简单审核 UI 或服务端渲染审核页面。
- `src/video_foundry/renderer`：基于 Pillow/OpenCV 的 Python 帧渲染器。
- `src/video_foundry/storyboard`：裁切和分镜规划逻辑。
- `src/video_foundry/voice`：TTS provider 适配器。
- `src/video_foundry/ffmpeg`：FFmpeg 命令构建和合成辅助逻辑。
- `src/video_foundry/sources`：NASA 和手动导入逻辑。
- `src/video_foundry/shared`：schema、配置加载和共享类型。

### 4.2 渲染技术

推荐使用 Python 渲染引擎作为主要渲染器。核心帧生成逻辑可以基于 Pillow 或 OpenCV 实现：每一帧读取原始图像，按分镜中的裁切窗口插值，生成目标画幅，再叠加字幕、credit 和可选覆盖层。

MoviePy 可以作为时间线装配的辅助工具，但图像运动逻辑应尽量保持在显式、可测试的 Python 代码中，避免把关键裁切规则隐藏在难以验证的黑盒流程里。

FFmpeg 用于最后的音视频装配和编码，例如：

- 合并静音视频和旁白音频。
- 添加或烧录字幕。
- 调整音量响度。
- 导出不同画幅和码率的 MP4。

### 4.3 数据校验

建议使用 Pydantic 或 JSON Schema 约束所有流水线产物：

- `asset.json`
- `script.json`
- `storyboard.json`
- `voice.json`
- `quality-report.json`

这对 LLM 输出尤其重要。大模型生成的脚本和分镜不能直接信任，必须经过结构化校验、字段校验和人工确认。

## 5. 模块详细说明

### 5.1 Asset Collector：素材采集器

素材采集器负责接收或查找官方素材。MVP 阶段可以先支持手动输入：

- 图片 URL
- 官方标题
- 官方描述
- 来源 URL
- credit 文本

后续可以接入 NASA Image and Video Library API，通过 `/search`、`/asset/{nasa_id}`、`/metadata/{nasa_id}` 和 `/captions/{nasa_id}` 自动搜索、下载和整理素材。

这个模块的重点不是“找到尽可能多的图”，而是保证素材来源可靠、图片分辨率足够、署名信息完整。

### 5.2 Asset Normalizer：素材规范化器

素材规范化器负责把外部输入变成系统内部统一格式。它需要：

- 保存原始图像。
- 提取宽、高、宽高比、文件类型和色彩配置。
- 生成预览图，供审核 UI 快速显示。
- 检查图片分辨率是否低于阈值。
- 原样保存官方描述和 credit。

推荐输出结构：

```text
projects/{project_id}/assets/original.jpg
projects/{project_id}/assets/preview.jpg
projects/{project_id}/metadata/asset.json
```

其中 `asset.json` 是后续脚本生成、分镜规划、署名渲染和质量报告的基础。

### 5.3 Script Generator：脚本生成器

脚本生成器根据官方文本生成中文旁白。它需要支持不同目标时长，例如 30、45、60、90 秒。

输出内容应包括：

- 中文标题
- 开头 hook
- 主体旁白
- 结束语
- 可选短 caption
- 内部审核备注

设计重点是“有吸引力但不失真”。例如，如果官方说明没有给出距离，就不能为了让旁白更完整而补一个距离值。

脚本生成后应保存两份：

```text
projects/{project_id}/script/script.md
projects/{project_id}/script/script.json
```

`script.md` 方便人工阅读和编辑，`script.json` 方便后续程序读取和校验。

### 5.4 Storyboard Planner：分镜规划器

分镜规划器把旁白拆成镜头。每个镜头包含：

- 起止时间
- 镜头类型
- 起始裁切窗口
- 结束裁切窗口
- 缓动函数
- 对应字幕文本

MVP 支持的镜头类型包括：

- `slow_push_in`：缓慢推近
- `pan_left` / `pan_right`：左右平移
- `pan_up` / `pan_down`：上下平移
- `local_zoom`：局部放大
- `hold`：静止停留
- `pull_back`：拉远
- `crossfade_to_credit`：淡入片尾署名

裁切窗口采用归一化坐标 `[x, y, width, height]`，范围是 `0.0` 到 `1.0`，对应原图的宽高。这种设计可以让分镜逻辑与具体图片像素尺寸解耦。

分镜规划必须避免过度放大。如果原图分辨率不足，局部 zoom 会导致画面模糊，甚至让观众误以为看到了真实细节。因此最大缩放比例需要有配置阈值和质量门禁。

### 5.5 Render Engine：渲染引擎

渲染引擎负责把分镜 JSON 转成视频帧。它的输入是原图、分镜、字幕和渲染配置；输出通常是静音视频。

允许的视觉操作包括：

- 裁切
- 缩放
- 平移
- 轻微旋转
- 淡入淡出
- 添加字幕
- 添加 credit 文本
- 添加非破坏性的轻微粒子覆盖层
- 在明确启用时，用同一张图生成模糊背景或 letterbox 背景

禁止的视觉操作包括：

- 生成式图像修改
- AI 补图、扩图、修补
- AI 视频插帧并生成不存在的细节
- 改变可见结构的 AI 超分
- 移除或替换图中对象
- 改变科学外观的颜色重映射

这里的边界非常关键：渲染器可以改变“观众看到原图的方式”，不能改变“原图里有什么”。

### 5.6 Particle Overlay：粒子覆盖层

粒子效果是可选的，并且默认关闭。它只能作为装饰，不能让观众误以为视频里新增的亮点是真实天体。

如果启用，建议规则是：

- 低透明度
- 慢速漂移
- 位于主图上方或图像边界外
- 对科学敏感内容默认关闭

实现上可以用 Pillow/OpenCV 生成透明粒子覆盖序列，或在 Python 渲染阶段直接合成低透明度点粒子。但 MVP 没有必要把粒子作为核心功能。

### 5.7 Voice Engine：语音引擎

语音引擎负责把审核通过的脚本转成旁白音频。它需要保存：

- TTS 服务商
- voice ID
- 语言
- 语音参数
- 生成音频路径
- 可用时的单词或句子时间戳

文档中列出的候选服务有：

- ElevenLabs：适合创作者工作流和自定义声音。
- Azure AI Speech Custom Neural Voice：适合企业场景，需要更正式的授权和部署控制。
- OpenAI text-to-speech：适合不需要自定义克隆声音的简单内置语音场景。

输出建议：

```text
projects/{project_id}/audio/narration.wav
projects/{project_id}/audio/narration.mp3
projects/{project_id}/audio/voice.json
```

如果涉及声音克隆，系统必须要求用户提供明确授权，并尽量只保存 provider 侧的 voice ID，不在本地长期保存敏感声音素材。

### 5.8 Subtitle Generator：字幕生成器

字幕生成器负责生成 SRT 和 WebVTT。优先使用 TTS 服务返回的时间戳；如果没有，则可以通过语音识别或文本音频对齐来补充。

字幕生成需要考虑：

- 竖屏安全区
- 横屏安全区
- 单行长度
- 每条字幕停留时间
- 与旁白句子的自然断句

输出：

```text
projects/{project_id}/subtitles/subtitles.srt
projects/{project_id}/subtitles/subtitles.vtt
```

### 5.9 Assembler：合成器

合成器使用 FFmpeg 把各类产物组合成最终视频。它需要：

- 合并静音视频和旁白音频。
- 可选合并背景音乐。
- 处理响度标准化。
- 添加字幕。
- 添加片尾 credit。
- 导出多个画幅。

推荐输出：

```text
projects/{project_id}/exports/final_9x16.mp4
projects/{project_id}/exports/final_16x9.mp4
projects/{project_id}/exports/final_1x1.mp4
```

### 5.10 Review UI：人工审核界面

审核 UI 不需要做成完整视频编辑器。它只需要覆盖关键风险点：

- 查看原图和元数据。
- 查看官方描述和 credit。
- 查看 AI 生成的中文脚本。
- 编辑或重新生成脚本。
- 查看分镜裁切框在原图上的位置。
- 调整裁切框和镜头时间。
- 试听旁白。
- 预览渲染结果。
- 审批脚本、分镜和最终导出。

这个 UI 的核心价值是把科学错误、署名遗漏、构图问题和字幕可读性问题挡在最终导出之前。

## 6. 核心数据模型

### 6.1 Asset

`Asset` 描述一个官方图片素材及其来源信息。关键字段包括：

- `id`：素材 ID。
- `title`：官方或规范化标题。
- `source`：来源，例如 NASA、ESA、STScI 或 manual。
- `source_url`：官方页面地址。
- `image_url`：原始图片下载地址。
- `local_original_path`：本地原图路径。
- `description`：官方说明。
- `credit`：署名文本。
- `published_at`：发布时间。
- `width` / `height`：图片尺寸。
- `license_notes`：授权和使用备注。

这个模型既服务于导入，也服务于审核、署名渲染和质量报告。

### 6.2 Production Job

`Production Job` 表示一次视频生产任务。一个素材可以对应多个生产任务，例如同一张图生成 45 秒竖屏版和 60 秒横屏版。

关键字段包括：

- `status`：当前状态，例如 `draft`、`script_ready`、`rendered`、`exported` 或 `failed`。
- `target_language`：目标语言，MVP 默认为 `zh-CN`。
- `target_duration_sec`：目标时长。
- `formats`：输出格式，例如 `9:16` 和 `16:9`。
- `voice_id`：使用的声音。
- `created_at` / `updated_at`：创建和更新时间。

### 6.3 Storyboard

`Storyboard` 是渲染器最重要的输入之一。它定义：

- 帧率
- 总时长
- 安全区
- 镜头列表

安全区用于确保字幕、署名和重要信息不会被平台 UI 或裁切遮挡。竖屏短视频尤其需要重视底部安全区，因为平台控件通常会占用画面底部区域。

## 7. API 设计说明

文档给出了一组初始 REST API：

```text
POST /projects
GET  /projects/{id}
POST /projects/{id}/import
POST /projects/{id}/generate-script
POST /projects/{id}/approve-script
POST /projects/{id}/generate-storyboard
POST /projects/{id}/approve-storyboard
POST /projects/{id}/generate-voice
POST /projects/{id}/render
POST /projects/{id}/export
GET  /projects/{id}/preview
GET  /projects/{id}/downloads
```

这些接口反映了一个“带审批点的流水线”：

1. 创建项目。
2. 导入素材。
3. 生成脚本。
4. 人工批准脚本。
5. 生成分镜。
6. 人工批准分镜。
7. 生成语音。
8. 渲染视频。
9. 导出成品。
10. 提供预览和下载。

审批接口是系统设计中的关键点。它强制把 AI 生成结果和最终发布结果之间隔开，避免未审核内容直接进入视频。

## 8. 配置说明

### 8.1 渲染预设

渲染预设定义输出尺寸、帧率、码率和字幕样式。示例：

```json
{
  "vertical_short": {
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "bitrate": "12M",
    "subtitle_style": "vertical_safe"
  }
}
```

竖屏短视频建议优先支持 `1080x1920`，横屏视频支持 `1920x1080`，方形视频支持 `1080x1080`。

### 8.2 声音预设

声音预设记录 provider、voice ID、语言和相关参数。示例：

```json
{
  "custom_narrator_cn": {
    "provider": "elevenlabs",
    "voice_id": "replace-with-real-id",
    "language": "zh-CN",
    "stability": 0.55,
    "similarity_boost": 0.75
  }
}
```

真实密钥不应写入配置样例或项目元数据。provider key 应通过 `.env` 或本地 secret 文件注入，并加入 `.gitignore`。

## 9. 错误处理策略

系统应该对关键问题快速失败，而不是尝试带病继续。需要失败的情况包括：

- 缺少 credit。
- 缺少 source URL。
- 图片下载失败。
- 图片分辨率低于阈值。
- LLM 输出包含无法从官方文本支持的表述。
- TTS 生成失败。
- Python 渲染引擎或 FFmpeg 渲染失败。

每个失败任务都应写入：

```text
projects/{project_id}/logs/error.json
projects/{project_id}/logs/pipeline.log
```

错误响应应包含：

- 失败步骤。
- 人类可读原因。
- 是否可重试。
- 建议修正方式。

这样审核者或开发者能快速判断是输入问题、服务商问题、配置问题还是渲染问题。

## 10. 质量门禁

最终导出前必须执行质量检查。推荐检查项包括：

- 原始图片存在。
- 原始图片 hash 已记录。
- credit 文本存在。
- source URL 存在。
- 脚本已被用户批准。
- 分镜已被用户批准。
- 每个裁切窗口都在图片边界内。
- 最大 zoom 没有超过配置阈值。
- 字幕位于安全区内。
- 旁白时长与分镜总时长大致匹配。
- 最终视频包含可见 credit。

质量报告建议输出为：

```text
projects/{project_id}/exports/quality-report.json
```

这个报告既可以用于本地排查，也可以作为未来批量生产、团队审核或发布归档的依据。

## 11. 安全与密钥管理

系统会使用 LLM、TTS、可选云存储等外部服务，因此必须明确密钥边界：

- API key 不写入项目元数据。
- API key 不提交到仓库。
- 使用 `.env` 或 `config/providers.local.env`。
- 示例配置只能放占位值。
- 语音克隆必须要求用户授权。
- 本地尽量只保存 provider voice ID，不保存不必要的原始声音文件。

这部分对后续产品化尤其重要，因为视频项目元数据可能会被打包、归档或分享，不能混入任何敏感凭据。

## 12. 测试策略

### 12.1 单元测试

单元测试应覆盖纯逻辑：

- 裁切窗口边界校验。
- 镜头时长和时间轴计算。
- 字幕断行。
- credit 必填校验。
- 脚本 JSON schema 校验。
- provider 配置解析。

这些测试能保证流水线的核心规则稳定。

### 12.2 集成测试

集成测试应覆盖端到端链路的一小段：

- 导入示例素材。
- 用固定脚本生成确定性分镜。
- 渲染 5 秒预览视频。
- 用测试音频合成视频。
- 导出 SRT 和 MP4。

集成测试不需要一开始就覆盖完整生产规模，但必须证明关键模块能够接起来。

### 12.3 视觉回归测试

视觉回归测试用于发现渲染异常：

- 在关键时间点导出帧图。
- 检查尺寸是否正确。
- 检测空白帧或全黑帧。
- 校验裁切区域没有越界。

这对 Python 渲染引擎和 FFmpeg 这类视频流水线很有价值，因为许多问题不会在普通单元测试中暴露。

### 12.4 人工审核

即使自动测试通过，以下内容仍然需要人工审核：

- 科学措辞是否准确。
- credit 是否符合来源要求。
- 镜头构图是否自然。
- 字幕是否可读。
- 旁白语气是否合适。

本系统的定位是“半自动生产”，人工审核是设计的一部分，不是临时补丁。

## 13. MVP 实施路线

### 13.1 Milestone 1：本地流水线

第一阶段目标是跑通最小闭环：

- 手动输入素材。
- 下载图片并保存元数据。
- 生成中文脚本。
- 生成分镜 JSON。
- 使用 Python 生成视频帧，并通过 FFmpeg 编码基础视频。
- 合成旁白和字幕。
- 导出 MP4。

这个阶段可以先不做完整 UI，只要 CLI 或简单接口能稳定产出视频即可。

### 13.2 Milestone 2：审核 UI

第二阶段补齐人工审核体验：

- 项目列表。
- 素材预览。
- 脚本编辑器。
- 分镜裁切预览。
- 视频预览。
- 审批按钮。

这一阶段的目标不是做复杂剪辑器，而是让用户能发现并修正关键问题。

### 13.3 Milestone 3：批量生产

第三阶段引入自动搜索和批处理：

- NASA Images API 搜索。
- 任务队列。
- 批量脚本生成。
- 批量渲染。
- 导出管理。

只有在单条视频链路稳定后，批量化才有意义。

### 13.4 Milestone 4：生产加固

第四阶段面向长期使用：

- provider 重试逻辑。
- 质量报告。
- 云存储选项。
- 团队审核角色。
- 发布平台集成。

这些能力可以提高可靠性和协作效率，但不应阻塞 MVP。

## 14. 开放决策

原设计文档列出了几个需要在实现前明确的问题：

- 是否使用纯 Python 渲染，还是使用 Python 渲染并引入 MoviePy 辅助时间线装配。
- 首个 TTS provider 选择 ElevenLabs、Azure 还是其他服务。
- 首个 LLM provider 和模型选择。
- 第一版是否要做 Web 审核 UI，还是先用 CLI 加预览图。
- NASA API 搜索是否纳入 MVP，还是等手动导入稳定后再做。

建议优先做出最小可运行选择：

- 后端和流水线编排先统一使用 Python，减少跨语言复杂度。
- 渲染用 Python + Pillow/OpenCV 生成帧，合成与编码用 FFmpeg。
- 导入先手动，NASA API 搜索后置。
- 审核 UI 可以在第一条完整流水线跑通后再做。
- 所有 AI 输出都先落盘为 JSON/Markdown，再进入下一步。

## 15. MVP 成功标准

MVP 成功时，用户应能完成以下操作：

1. 用一张官方 Webb 图片和官方说明创建项目。
2. 生成中文旁白脚本。
3. 审核并批准脚本。
4. 生成基于裁切运动的分镜。
5. 用配置好的声音生成 AI 旁白。
6. 渲染 45 到 60 秒的视频，包含字幕和 credit。
7. 导出竖屏和横屏 MP4。
8. 验证天文图像内容没有被 AI 生成、重绘或视觉篡改。

## 16. 推荐的首个开发切入点

建议第一步实现“手动素材输入 -> 本地项目目录 -> 结构化元数据”的基础链路。原因是后续所有模块都依赖稳定的项目目录和数据模型。

首个可交付闭环可以是：

1. 创建 `projects/{project_id}`。
2. 输入图片 URL、标题、官方描述、source URL 和 credit。
3. 下载原图到 `assets/original.jpg`。
4. 生成 `metadata/asset.json`。
5. 校验 source URL、credit、图片尺寸和本地文件 hash。
6. 输出一份导入报告。

完成这个基础后，再接入脚本生成、分镜生成和渲染。这样可以避免一开始就把 LLM、TTS、视频渲染、字幕和 UI 全部耦合在一起。

## 17. 一句话总结

这个系统的本质是一个可信的天文短视频生产流水线：它用 AI 提高文案、分镜和旁白效率，但用严格的数据模型、人工审核和渲染约束确保官方图像不被篡改、科学表述不被编造、来源署名始终可追溯。


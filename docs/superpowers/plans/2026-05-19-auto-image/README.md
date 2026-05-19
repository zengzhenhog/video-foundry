# Auto Image AI 分步执行计划索引

日期：2026-05-19  
来源设计：`docs/superpowers/specs/2026-05-19-auto-image-development-plan-design.md`  
系统设计：`docs/system-design.md`、`docs/system-design.zh-CN.md`

本目录把 Auto Image 开发计划拆成可单独交给 AI 执行的阶段计划文件。每个阶段文件都尽量自包含，包含目标、允许修改范围、必须新增或修改的文件、禁止事项、原子执行步骤、验收标准和验证命令。

## 使用方式

执行任一阶段时，把对应计划文件作为主任务输入，并要求 AI 同时阅读：

- `docs/system-design.md`
- `docs/system-design.zh-CN.md`
- `docs/superpowers/specs/2026-05-19-auto-image-development-plan-design.md`
- 当前阶段之前已经完成的代码和测试

推荐提示：

```text
请执行 docs/superpowers/plans/2026-05-19-auto-image/phase-XX-*.md。

必须遵守该计划文件中的允许修改范围、不要做、验收标准和验证命令。
完成后请说明：
- 修改了哪些文件
- 运行了哪些验证命令以及结果
- 生成了哪些本地产物
- 哪些事项留到下一阶段
```

## 全局执行规则

1. 必须按 Phase 0 到 Phase 9 的顺序执行，除非人工明确调整。
2. 每个阶段只实现本阶段目标，不提前实现后续阶段的复杂功能。
3. 项目目录 `projects/{project_id}` 中的 JSON 和文件产物是事实来源；Phase 9 前不引入数据库。
4. AI 可以生成文本、脚本、分镜建议和旁白音频，但不得生成式修改用户上传图片。
5. API key 只能从 `.env` 或环境变量读取，不得写入项目元数据、日志、测试快照或提交文件。
6. 所有 AI 输出必须先落盘为结构化文件，再进入下一步审核或渲染。
7. FastAPI 接口必须返回结构化 JSON 错误，不暴露未处理异常。
8. 前端第一版优先做稳定工作台，不做营销页，不引入复杂 UI 组件库。
9. 每个阶段必须补充与风险相匹配的测试。
10. 完成阶段前必须运行该阶段计划中的验证命令；无法运行时必须说明原因和替代验证。

## 全局实施契约

这些规则适用于所有阶段。若单个 phase 文件没有重复说明，以本节为准。

### 仓库和依赖

- 执行根目录以当前仓库为准。`docs/system-design.md` 中的旧目标路径只作为历史上下文，不要求切换到其他目录。
- 后端新增运行依赖时，必须同步更新 `pyproject.toml` 和项目已有的锁文件；如果尚未建立锁文件，Phase 0 选择一种包管理方式后后续阶段保持一致。
- 前端使用 Phase 0 选定的包管理器，后续阶段不得混用 npm、pnpm、yarn。新增前端依赖时必须更新对应 lock 文件。
- 后端 MVP 常用依赖应在需要时显式加入依赖声明：FastAPI、Pydantic v2、Uvicorn、pytest、httpx、python-multipart、Pillow。FFmpeg 是系统依赖，不写入 Python 依赖。

### API 和错误响应

- 新增 API 路由时，必须同时完成路由注册。可以在 `src/auto_image/api/main.py` 中注册，也可以在 Phase 1 建立集中 router 聚合；后续阶段沿用同一模式。
- 所有 API 错误返回统一 JSON 结构：

```json
{
  "error": {
    "code": "missing_credit",
    "message": "Credit is required before script generation.",
    "step": "asset_validation",
    "retryable": true,
    "suggested_correction": "Add credit in the asset page.",
    "details": {}
  }
}
```

- API 不返回 Python traceback、绝对本地路径、环境变量值、provider 请求头或密钥。

### 项目状态流转

`Project.status` 是项目主流程状态，不替代每个产物自己的 `approved`、`stale` 或错误字段。修改上游产物时，不必删除旧下游文件，但必须在项目摘要或对应 JSON 中标记下游产物过期。

| 状态 | 进入条件 | 失效或回退规则 |
| --- | --- | --- |
| `draft` | 项目刚创建 | 上传完整素材后可进入 `asset_ready` |
| `asset_ready` | 原图、预览、description 或文案、source_url、credit 已保存 | 修改图片、description、source_url 或 credit 后，脚本、分镜、旁白、字幕、渲染和导出都应标记 stale |
| `script_ready` | 脚本生成或保存，但未批准 | 批准后进入 `script_approved` |
| `script_approved` | 用户批准脚本 | 修改脚本后回到 `script_ready`，并标记旁白、分镜、字幕、渲染和导出 stale |
| `storyboard_ready` | 分镜生成或保存，但未批准 | 批准后进入 `storyboard_approved` |
| `storyboard_approved` | 用户批准分镜 | 修改分镜后回到 `storyboard_ready`，并标记字幕、渲染和导出 stale |
| `voice_ready` | 已批准脚本生成旁白音频 | 修改脚本或 voice 配置后，旁白、渲染和导出 stale |
| `rendered` | 已生成预览或最终视频文件 | 修改素材、脚本、分镜、字幕、旁白或音乐后，渲染和导出 stale |
| `exported` | 质量门禁通过，最终 MP4 和质量报告存在 | 任一上游产物 stale 后不得继续显示为成功导出 |
| `failed` | 当前步骤失败并写入错误信息 | 修复输入并重试后应恢复到最接近的有效上游状态 |

### 项目产物和命名

- 所有项目内 JSON 产物应包含 `schema_version`、`project_id`、`created_at` 或 `updated_at`，路径字段优先使用相对项目目录路径。
- `format` 使用配置 key，例如 `vertical_1080x1920`、`landscape_1920x1080`、`square_1080x1080`。输出文件名使用同一个 key：`final_{format}.mp4`。
- 背景音乐是可选输入。没有背景音乐时，渲染、质量检查和导出仍必须可完成。
- Phase 6 渲染时应输出 `renders/render-manifest.json`，记录使用的原图 hash、format、字幕覆盖、credit 覆盖、输出文件和关键帧元数据。Phase 7 质量门禁用该 manifest 作为“可见 credit”和“未生成式修改图片”的证据之一。

### 测试和夹具

- 后端测试必须使用临时 `projects` 根目录，不污染仓库真实 `projects/`。
- 上传、脚本、旁白、分镜、渲染的集成测试应使用小型固定 fixture，避免依赖真实网络或真实 provider。
- 缺少系统 FFmpeg 时，可以跳过或 xfail 依赖 FFmpeg 的集成测试，但纯函数、命令构建和质量检查测试仍必须运行。
- 每个阶段最终回复必须说明运行了哪些验证命令、哪些命令因环境问题未运行，以及替代验证是什么。

## 阶段文件

| 阶段 | 文件 | 目标 |
| --- | --- | --- |
| Phase 0 | `phase-00-foundation.md` | 创建可启动、可测试的前后端工程骨架 |
| Phase 1 | `phase-01-models-storage.md` | 建立核心 Pydantic 模型、项目目录和 JSON 存储 |
| Phase 2 | `phase-02-assets-workbench.md` | 实现图片、文案、credit、可选背景音乐上传和基础工作台 |
| Phase 3 | `phase-03-script-review.md` | 实现 AI 脚本生成、编辑、保存和批准 |
| Phase 4 | `phase-04-voice-tts.md` | 实现旁白音色配置、mock TTS 和试听 |
| Phase 5 | `phase-05-storyboard-subtitles.md` | 实现分镜、裁切校验、字幕生成和审核 UI |
| Phase 6 | `phase-06-render-ffmpeg.md` | 实现原图裁切渲染、字幕/credit 覆盖和 FFmpeg 合成 |
| Phase 7 | `phase-07-jobs-quality.md` | 实现长任务、日志、失败诊断和质量门禁 |
| Phase 8 | `phase-08-console-generate-all.md` | 完整审核控制台、一键生成、预览和下载 |
| Phase 9 | `phase-09-batch-hardening.md` | 批量化、NASA 导入、SQLite 索引和生产加固 |

## MVP 边界

MVP 由 Phase 0 到 Phase 8 组成。Phase 9 是增强阶段，不应阻塞本地视频生成主流程。判断 MVP 是否完成时，以 Phase 8 的验收标准和源设计文档第 17 节为准。

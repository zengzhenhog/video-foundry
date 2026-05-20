# Phase 1：核心数据模型与本地存储

目标：建立项目目录、核心 Pydantic 模型和 JSON 文件存储能力。完成后，用户可以通过 API 创建项目、列出项目、读取项目，并在本地看到完整项目目录骨架。

## 前置条件

- Phase 0 已完成。
- 后端包可导入，测试命令可运行。

## 允许修改

- `src/video_foundry/shared/**`
- `src/video_foundry/api/main.py`
- `src/video_foundry/api/dependencies.py`
- `src/video_foundry/api/routes/**`
- `tests/unit/**`
- `tests/integration/**`
- `README.md` 中与项目 API 相关的简短说明

## 必须新增或修改的文件

- `src/video_foundry/shared/schemas.py`
- `src/video_foundry/shared/errors.py`
- `src/video_foundry/shared/paths.py`
- `src/video_foundry/shared/storage.py`
- `src/video_foundry/api/dependencies.py`
- `src/video_foundry/api/routes/projects.py`
- `tests/unit/test_schemas.py`
- `tests/unit/test_paths.py`
- `tests/unit/test_storage.py`
- `tests/integration/test_projects_api.py`

## 不要做

- 不实现文件上传。
- 不实现脚本、TTS、分镜、字幕或渲染。
- 不引入数据库。
- 不把项目列表状态缓存在内存中作为事实来源。

## 原子执行步骤

1. 在 `shared/schemas.py` 定义源设计要求的核心模型：`Project`、`Asset`、`Script`、`VoiceConfig`、`BackgroundMusic`、`Storyboard`、`StoryboardShot`、`RenderJob`、`QualityReport`。所有会落盘的 JSON 模型都应包含 `schema_version`，路径字段优先保存相对项目目录路径。
2. 定义项目状态枚举，至少包含：`draft`、`asset_ready`、`script_ready`、`script_approved`、`storyboard_ready`、`storyboard_approved`、`voice_ready`、`rendered`、`exported`、`failed`。
3. 增加项目状态辅助逻辑或注释，明确 README 中的状态流转和 stale 规则。Phase 1 不必实现所有下游 stale 计算，但模型应为后续阶段保留字段或扩展位置。
4. 为模型补充必要的字段校验：
   - 时间和时长不能为负。
   - crop 坐标使用 `[0, 1]` 范围。
   - voice speed、volume gain 等参数有合理边界。
   - `project_id`、job id 等不能包含路径穿越字符。
5. 在 `shared/paths.py` 实现项目路径解析。路径函数必须只返回 `projects/{project_id}` 内的路径，并防止 `..`、绝对路径和非法分隔符。
6. 在 `shared/storage.py` 实现：
   - 创建项目目录和固定子目录。
   - JSON 读取和写入。
   - 原子写入，先写临时文件再替换目标文件。
   - 项目列表扫描，事实来源为 `projects/*/project.json`。
7. 创建项目服务逻辑。可以先放在 `routes/projects.py` 或 shared 辅助函数中，但接口边界要清晰，后续可迁移到 service。
8. 实现 API：
   - `POST /api/projects`
   - `GET /api/projects`
   - `GET /api/projects/{project_id}`
   - 可以为 `DELETE /api/projects/{project_id}` 留路由骨架，但如果实现删除，必须只删除项目目录内文件且测试覆盖。
9. 创建项目时写入 `project.json`，并创建源设计中的必要子目录：`assets`、`metadata`、`script`、`storyboard`、`audio`、`subtitles`、`renders`、`exports`、`logs`。
10. 为 API 增加 README 约定的结构化错误响应。找不到项目、非法 ID、JSON 损坏都应返回明确错误。
11. 补充单元测试和集成测试，使用临时 projects 根目录，不污染真实 `projects/`。

## 验收标准

- 创建项目后，本地存在完整项目目录和 `project.json`。
- 项目 ID 不允许路径穿越。
- 项目列表来自磁盘扫描，不依赖进程内状态。
- JSON 原子写入测试覆盖。
- 项目状态枚举和核心模型校验有测试。
- 落盘 JSON 模型包含 schema version，路径字段不会泄露无必要的绝对路径。
- API 错误为结构化 JSON。

## 验证命令

```powershell
python -m pytest tests/unit tests/integration
python -m compileall src
```

如已配置格式化或 lint 命令，也运行对应命令，并在最终回复中报告。

## 预期输出

- 可创建、读取、列出的本地项目。
- 稳定的项目目录规范。
- 后续阶段可复用的 schema、paths、storage。

## 下一阶段入口

Phase 2 将在项目目录和存储能力上实现图片、文案、credit 和可选背景音乐上传。


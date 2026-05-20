# Phase 0：项目基础设施

目标：建立一个可启动、可测试、目录清晰的前后端工程骨架。完成后，后端可以被导入并提供健康检查，前端可以进行类型检查或构建，测试命令可以运行。

## 上下文

执行前阅读：

- `docs/system-design.md`
- `docs/system-design.zh-CN.md`
- `docs/superpowers/specs/2026-05-19-video-foundry-development-plan-design.md`
- `README.md`

## 允许修改

- `.gitignore`
- `README.md`，仅可补充本地开发命令
- `pyproject.toml`
- Python 锁文件（如项目选择 `uv.lock`、`poetry.lock` 或同类文件）
- `src/video_foundry/**`
- `tests/**`
- `web/**`
- 前端包管理锁文件（按 Phase 0 选定的包管理器生成）
- `config/**`
- `projects/.gitkeep`

## 必须新增或修改的文件

- `pyproject.toml`
- `src/video_foundry/__init__.py`
- `src/video_foundry/api/__init__.py`
- `src/video_foundry/api/main.py`
- `src/video_foundry/api/routes/__init__.py`
- `src/video_foundry/shared/__init__.py`
- `src/video_foundry/shared/config.py`
- `config/render-presets.json`
- `config/voices.example.json`
- `config/providers.example.env`
- `projects/.gitkeep`
- `tests/unit/test_health.py`
- `web/package.json`
- `web/index.html`
- `web/src/main.ts`
- `web/src/App.vue`
- `web/src/styles/` 下的基础样式文件

## 不要做

- 不实现项目创建、上传、脚本生成、TTS、分镜、渲染或任务系统。
- 不接入真实外部 provider。
- 不创建数据库或迁移工具。
- 不把 `.env`、API key、生成视频或缓存文件提交进仓库。

## 原子执行步骤

1. 检查仓库现状，确认当前只有文档和 README 时，不要删除任何已有文件。
2. 创建 Python 包配置，使用 `src` layout，声明 Python 版本和运行依赖：FastAPI、Pydantic v2、Uvicorn。可在 Phase 0 一并加入后续 MVP 必需依赖：`python-multipart`、Pillow、httpx。开发依赖至少包含 pytest。
3. 创建 `src/video_foundry` 包结构。Phase 0 只需要真实导入路径和必要的 `__init__.py`。
4. 在 `api/main.py` 创建 FastAPI app，提供 `GET /api/health`，返回应用名、版本和状态。预留清晰的 router 注册位置，后续阶段新增路由时必须在这里或集中 router 聚合模块中注册。
5. 在 `shared/config.py` 放最小配置对象，包含项目根目录、projects 目录、config 目录。配置可以从环境变量覆盖，但不得读取或打印 API key。
6. 创建配置样例：
- `render-presets.json`：至少包含 `vertical_1080x1920`、`landscape_1920x1080`、`square_1080x1080`，每个 preset 至少包含 width、height、fps、safe_area、max_zoom。
   - `voices.example.json`：包含一个 mock voice。
   - `providers.example.env`：只列变量名和注释，不包含真实值。
7. 创建 `.gitignore`，忽略 `.env`、虚拟环境、Python 缓存、前端依赖、前端构建产物、`projects/*` 下的生成内容，同时保留 `projects/.gitkeep`。
8. 创建 `web/` Vite + Vue 3 + TypeScript 最小工程。首页只需要显示应用壳和后续工作台入口占位。
9. 创建基础测试，至少验证 FastAPI app 可导入和 `/api/health` 返回成功。
10. 更新 README 中的开发命令，保持简短。

## 验收标准

- 后端应用可被测试导入。
- `GET /api/health` 有稳定 JSON 响应。
- 前端工程存在并能执行类型检查或构建脚本。
- 前端包管理器已经固定，后续阶段不得混用其他包管理器。
- 配置样例文件存在且不含真实密钥。
- `.gitignore` 不会忽略文档和源码，但会忽略本地产物。

## 验证命令

在仓库根目录运行：

```powershell
python -m pytest
python -m compileall src
```

在 `web/` 目录运行：

```powershell
npm install
npm run typecheck
npm run build
```

如果本地没有 Node、npm 或 Python 依赖安装失败，必须在最终回复中说明实际阻塞点，并至少完成可运行的 Python 验证或静态导入验证。

## 预期输出

- 可导入的后端包。
- 可安装的前端工程。
- 可保留空目录的 `projects/.gitkeep`。
- 基础测试通过。

## 下一阶段入口

Phase 1 将在此骨架上实现 Pydantic 数据模型、项目目录生成、JSON 存储和项目 API。


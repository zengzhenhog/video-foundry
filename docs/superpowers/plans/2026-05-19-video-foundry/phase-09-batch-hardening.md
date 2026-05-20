# Phase 9：批量化与生产加固

目标：增强长期使用能力，包括 NASA API 导入、批量项目队列、provider 重试和限流、SQLite 索引、并发渲染控制、缓存策略和发布平台集成预留。此阶段不应破坏 Phase 0 到 Phase 8 的单项目主流程。

## 前置条件

- Phase 8 已完成。
- MVP 主流程可以从页面完成本地 MP4 导出。

## 允许修改

- `src/video_foundry/sources/**`
- `src/video_foundry/jobs/**`
- `src/video_foundry/ai/**`
- `src/video_foundry/voice/**`
- `src/video_foundry/shared/**`
- `src/video_foundry/api/routes/**`
- `src/video_foundry/api/main.py` 或 Phase 1 建立的集中 router 聚合文件
- `pyproject.toml`、Python 锁文件、`web/package.json` 和前端锁文件，仅限本阶段子任务必需依赖
- `web/src/**`
- `tests/unit/**`
- `tests/integration/**`
- 新增 SQLite 索引相关模块，但不得替代项目目录事实来源

## 必须新增或修改的文件

按实际子任务选择，建议拆成更小 PR 或更小 AI 执行轮次：

- `src/video_foundry/sources/nasa_api.py`
- `src/video_foundry/jobs/queue.py`
- `src/video_foundry/jobs/concurrency.py`
- `src/video_foundry/shared/index_store.py`
- `src/video_foundry/shared/cache.py`
- `src/video_foundry/api/routes/imports.py`
- `src/video_foundry/api/routes/batch.py`
- `web/src/pages/BatchQueue.vue`
- `web/src/components/NasaSearchPanel.vue`
- 相关测试文件

## 不要做

- 不把 SQLite 变成项目事实来源。项目 JSON 和文件产物仍然是事实来源。
- 不让批量任务绕过单项目审核门禁。
- 不把 provider 错误吞掉。
- 不把外部 API 响应中的大文件或密钥写进仓库。
- 不改变 Phase 8 已走通的单项目主流程。

## 原子执行步骤

建议把 Phase 9 再拆成 4 个独立执行轮次。

### 9A：NASA API 搜索与导入

1. 实现 `sources/nasa_api.py`，封装 NASA API 搜索和资产元数据解析。
2. 实现导入接口，允许从 NASA 结果创建项目并填充 source URL、title、description、credit。
3. 图片下载应保留原始来源信息，并写入 `metadata/asset.json`。
4. 前端实现搜索面板和导入按钮。
5. 测试使用 mock HTTP，不依赖真实网络。

### 9B：批量队列和并发控制

1. 实现批量项目队列，只调度已有单项目流程。
2. 增加并发渲染限制，避免多个 FFmpeg 任务抢占资源。
3. 批量任务必须能暂停、失败重试和继续。
4. 前端增加批量队列页，展示每个项目状态。
5. 测试队列顺序、并发上限和失败隔离。

### 9C：provider 重试、限流和缓存

1. 为 LLM 和 TTS provider 增加重试策略。
2. 增加限流和退避，不要在失败时无限重试。
3. 增加可清理缓存，缓存 key 不得包含 API key。
4. 日志中记录 provider 错误摘要，但不记录敏感头或密钥。
5. 测试重试次数、限流触发和缓存命中。

### 9D：SQLite 索引和发布预留

1. 增加 SQLite 索引，用于项目列表、搜索、任务恢复和批量管理。
2. 索引内容必须可从 `projects/{project_id}` 重建。
3. 启动时提供索引重建或修复函数。
4. 增加发布平台集成的接口占位，但不接入真实发布服务。
5. 测试索引重建、项目删除后的索引一致性和 API 查询。

## 验收标准

- 批量任务不会破坏单项目主流程。
- provider 错误有重试、限流和明确日志。
- SQLite 只是索引，不替代项目目录中的事实产物。
- NASA 导入保留 source URL、description 和 credit。
- 并发渲染受控，失败项目不会阻塞所有项目。

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

如加入端到端或批量测试，运行对应命令并在最终回复中说明。

## 预期输出

- NASA 搜索和导入能力。
- 批量队列 UI 和 API。
- provider 重试、限流和缓存。
- SQLite 项目索引。
- 发布平台接口预留。

## 后续扩展

Phase 9 完成后，可以继续单独规划多语言脚本、TTS provider 对比试听、裁切框拖拽编辑、云端 worker、团队审核和权限系统。


# Phase 7：任务系统、日志和质量门禁

目标：让长任务可追踪、失败可诊断，并在导出前生成质量报告。完成后，页面可以看到任务进度、失败原因、日志摘要和重试入口。

## 前置条件

- Phase 6 已完成。
- 渲染和导出 API 可以生成视频。

## 允许修改

- `src/auto_image/jobs/**`
- `src/auto_image/quality/**`
- `src/auto_image/api/routes/**`
- `src/auto_image/api/main.py` 或 Phase 1 建立的集中 router 聚合文件
- `src/auto_image/shared/schemas.py`
- `src/auto_image/shared/storage.py`
- `tests/unit/**`
- `tests/integration/**`
- `web/src/**`

## 必须新增或修改的文件

- `src/auto_image/jobs/__init__.py`
- `src/auto_image/jobs/models.py`
- `src/auto_image/jobs/manager.py`
- `src/auto_image/jobs/store.py`
- `src/auto_image/jobs/runner.py`
- `src/auto_image/quality/__init__.py`
- `src/auto_image/quality/checks.py`
- `src/auto_image/quality/report.py`
- `src/auto_image/api/routes/jobs.py`
- `src/auto_image/api/routes/logs.py`
- `src/auto_image/api/routes/quality.py`
- `web/src/composables/useJobPolling.ts`
- `web/src/components/JobStatusPanel.vue`
- `web/src/components/QualityReportPanel.vue`
- 相关测试文件

## 不要做

- 不引入外部队列系统。
- 不引入数据库作为 job 事实来源。
- 不重写渲染管线；只把已有管线纳入任务执行和质量检查。
- 不做批量队列；留到 Phase 9。

## 原子执行步骤

1. 在 `jobs/models.py` 定义 job 状态和错误结构。状态至少包含 pending、running、succeeded、failed、cancelled。
2. 在 `jobs/manager.py` 实现本地 job 管理：
   - 创建 job。
   - 查询 job。
   - 更新进度。
   - 记录 output_paths。
   - 将 job 状态落盘到 `logs/jobs/{job_id}.json`，避免进程重启后完全丢失结果。
3. 在 `jobs/runner.py` 实现本地后台执行器。可以使用线程池或 FastAPI BackgroundTasks，第一版不需要分布式。
4. 所有长任务写 `logs/pipeline.log`。日志需要包含 step、时间、状态和摘要。
5. 失败时写 `logs/error.json`，结构包含 step、reason、retryable、suggested_correction。
6. 实现质量检查：
   - 原图存在。
   - hash 已记录。
   - credit 存在。
   - source_url 存在。
   - 文案或描述存在。
   - 脚本已批准。
   - 分镜已批准。
   - crop 坐标合法。
   - 最大 zoom 合法。
   - 旁白音频存在。
   - 旁白音频时长与 storyboard 时长大致匹配，允许配置化容差。
   - 背景音乐如存在则可读取。
   - 字幕文件存在。
   - 字幕安全区检查通过或 render manifest 提供覆盖层证据。
   - `renders/render-manifest.json` 存在，并证明最终视频包含可见 credit 覆盖。
   - 导出 MP4 存在且文件大小大于最小阈值。
7. 实现 `quality/report.py` 生成 `exports/quality-report.json`。
8. 调整 render/export API，让它们返回 job id，并通过任务系统执行。
9. 实现 API：
   - `GET /api/jobs/{job_id}`
   - `GET /api/projects/{project_id}/logs`
   - `GET /api/projects/{project_id}/quality-report`
   并完成路由注册。
10. 前端实现 job 轮询 composable、任务状态面板、日志摘要、失败重试入口和质量报告展示。
11. 补充测试：
    - job 状态转换。
    - 失败写 error.json。
    - 质量门禁失败时不能标记 exported。
    - 成功导出前生成 quality report。
    - 缺少 render manifest 或 manifest 中缺少 credit 覆盖时质量检查失败。
    - 进程重启后可从 `logs/jobs/{job_id}.json` 读取已完成或失败的 job 摘要。
    - 前端轮询能在成功和失败时停止。

## 验收标准

- 页面能看到任务进度和最终状态。
- 失败任务包含 step、reason、retryable、suggested_correction。
- 导出前必须生成 `quality-report.json`。
- 未通过质量门禁时不能标记为成功导出。
- 日志可以通过 API 读取并在前端展示摘要。
- job 状态以项目目录内文件为事实来源，不能只保存在内存里。

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

- `projects/{project_id}/logs/pipeline.log`
- `projects/{project_id}/logs/error.json`，仅失败时
- `projects/{project_id}/logs/jobs/{job_id}.json`
- `projects/{project_id}/exports/quality-report.json`
- job 查询接口和前端任务面板

## 下一阶段入口

Phase 8 将把已有页面整合成完整步骤式控制台，并实现一键生成和下载入口。

# Phase 3：AI 文案与脚本审核

目标：系统可以根据项目素材生成结构化旁白脚本，用户可以在页面编辑、保存并批准脚本。完成后，只有批准后的脚本才能进入旁白和分镜阶段。

## 前置条件

- Phase 2 已完成。
- 项目已有图片、description 或文案、source URL 和 credit。

## 允许修改

- `src/video_foundry/ai/**`
- `src/video_foundry/api/routes/**`
- `src/video_foundry/api/main.py` 或 Phase 1 建立的集中 router 聚合文件
- `src/video_foundry/shared/schemas.py`
- `src/video_foundry/shared/storage.py`
- `tests/unit/**`
- `tests/integration/**`
- `web/src/**`

## 必须新增或修改的文件

- `src/video_foundry/ai/__init__.py`
- `src/video_foundry/ai/base.py`
- `src/video_foundry/ai/mock_provider.py`
- `src/video_foundry/ai/script_generator.py`
- `src/video_foundry/api/routes/script.py`
- `web/src/pages/ProjectScript.vue`
- `web/src/components/ScriptEditor.vue`
- `web/src/composables/useProject.ts`
- 相关测试文件

## 不要做

- 不接入真实 LLM SDK，除非只添加 provider 骨架且不作为默认路径。
- 不生成旁白音频。
- 不生成分镜或字幕。
- 不允许未批准脚本进入后续状态。
- 不把 prompt、API key 或外部响应原文无边界写入日志。
- 不生成没有官方描述依据的距离、日期、对象类型、因果关系或观测细节。

## 原子执行步骤

1. 在 `ai/base.py` 定义 LLM provider 接口。接口至少包含 `generate_script(input) -> Script`，可以预留 `generate_storyboard` 但不实现业务调用。
2. 定义脚本生成输入对象，包含项目 ID、标题、描述、source URL、credit、目标语言、目标时长和可选用户草稿。
3. 在 `ai/mock_provider.py` 实现确定性 mock provider。相同输入应输出相同脚本，便于测试。
4. 在 `script_generator.py` 实现编排逻辑：
   - 读取项目和素材元数据。
   - 校验素材完整性、source URL 和 credit。
   - 构造 provider 输入时明确要求脚本只依据官方描述和用户草稿，不添加无来源事实。
   - 调用 provider。
   - 使用 Pydantic 校验输出。
   - 写入 `script/script.json` 和 `script/script.md`。
   - 在 `review_notes` 或等价字段中保存来源约束摘要，例如哪些事实来自 source description，哪些信息因缺少来源而未使用。
5. 实现 API：
   - `POST /api/projects/{project_id}/script/generate`
   - `GET /api/projects/{project_id}/script`
   - `PUT /api/projects/{project_id}/script`
   - `POST /api/projects/{project_id}/script/approve`
6. 更新项目状态流：
   - 生成或保存未批准脚本后为 `script_ready`。
   - 批准后为 `script_approved`。
   - 修改已批准脚本时必须撤销批准，回到 `script_ready`。
7. 前端实现脚本页。页面需要有生成、编辑、保存、批准按钮，并清楚显示当前批准状态。
8. `ScriptEditor.vue` 支持多段 narration 或 segment 展示，第一版可以用文本区域和结构化预览，不必做复杂富文本。
9. 补充测试：
   - mock provider 输出确定。
   - 空 description 或缺 credit 时生成失败。
   - 保存脚本会更新 JSON 和 Markdown。
   - 修改已批准脚本会撤销批准。
   - 未批准脚本时后续状态保护函数返回失败。
   - provider 输出缺少 grounding notes 或包含明显无来源字段时会被拒绝或标记为需要人工审核。

## 验收标准

- 用户可在前端生成、编辑、保存和批准脚本。
- `script/script.json` 与 `script/script.md` 都会落盘。
- 未批准脚本不能进入旁白和分镜阶段。
- mock provider 不依赖网络和外部密钥。
- 脚本 JSON 包含可供人工审核的 source grounding 或 review notes。
- API 错误可被前端显示。

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

- `projects/{project_id}/script/script.json`
- `projects/{project_id}/script/script.md`
- 前端脚本审核页面

## 下一阶段入口

Phase 4 将在脚本批准状态上实现 voice 配置和 mock TTS 旁白音频生成。


# Phase 4：旁白音色与 TTS

目标：系统可以保存旁白音色配置，并基于已批准脚本生成可播放的旁白音频。第一版必须提供 mock TTS，不依赖外部服务。

## 前置条件

- Phase 3 已完成。
- 项目存在已批准脚本。

## 允许修改

- `src/auto_image/voice/**`
- `src/auto_image/api/routes/**`
- `src/auto_image/api/main.py` 或 Phase 1 建立的集中 router 聚合文件
- `src/auto_image/shared/schemas.py`
- `src/auto_image/shared/storage.py`
- `config/voices.example.json`
- `tests/unit/**`
- `tests/integration/**`
- `web/src/**`

## 必须新增或修改的文件

- `src/auto_image/voice/__init__.py`
- `src/auto_image/voice/base.py`
- `src/auto_image/voice/mock_provider.py`
- `src/auto_image/voice/provider_registry.py`
- `src/auto_image/api/routes/voice.py`
- `web/src/pages/ProjectVoice.vue`
- `web/src/components/VoiceConfigForm.vue`
- 相关测试文件

## 不要做

- 不实现声音克隆训练。
- 不把 API key 保存到 `voice.json`、项目元数据或前端状态。
- 不把真实 provider 作为默认依赖。
- 不生成分镜、字幕或视频。

## 原子执行步骤

1. 在 `voice/base.py` 定义 TTS provider 接口。接口至少包含 `synthesize(text, voice_config) -> VoiceResult`。
2. 定义 `VoiceResult`，包含音频路径、时长、格式和 provider 元信息。不要包含密钥。
3. 在 `voice/mock_provider.py` 实现 mock TTS。可生成简单 WAV 测试音，也可复制固定测试音频；必须保证测试环境不依赖网络。
4. 在 `provider_registry.py` 根据配置选择 provider。默认 provider 为 mock。真实 provider 可以保留骨架，但必须通过环境变量启用。
5. 实现 voice 配置保存，并完成路由注册：
   - `PUT /api/projects/{project_id}/voice/config`
   - 写入 `audio/voice.json`
   - 校验 provider、voice_id、language、speed、volume_gain_db、style。
6. 实现 provider 和 preset 查询：
   - `GET /api/voice/providers`
   - `GET /api/voice/presets`
7. 实现旁白生成：
   - `POST /api/projects/{project_id}/voice/generate`
   - 只允许已批准脚本。
   - 输出 `audio/narration.wav` 或 `audio/narration.mp3`。
   - 更新 `audio/voice.json` 中的音频路径和时长。
   - 项目状态推进到 `voice_ready`。
   - 若重新生成旁白或修改 voice 配置，必须按 README 状态契约标记渲染和导出 stale。
8. 实现音频读取接口 `GET /api/projects/{project_id}/voice/audio`。
9. 前端实现 voice 页面，包含 provider、voice ID、语速、音量、风格字段，保存和生成按钮，以及 audio 试听控件。
10. 补充测试：
    - 未批准脚本时生成旁白失败。
    - 缺失 voice ID 时保存失败。
    - mock TTS 生成可存在且非空的音频文件。
    - `voice.json` 不包含 API key 字段。
    - provider registry 默认选择 mock。

## 验收标准

- 已批准脚本可以生成可播放音频文件。
- `audio/voice.json` 保存 voice 配置和音频元数据。
- API key 不落盘。
- 前端可保存配置并试听生成后的旁白。
- 所有错误可被页面显示。

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

- `projects/{project_id}/audio/voice.json`
- `projects/{project_id}/audio/narration.wav` 或 `narration.mp3`
- 前端 voice 配置和试听页面

## 下一阶段入口

Phase 5 将根据已批准脚本生成分镜，并生成 SRT/VTT 字幕。

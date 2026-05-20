# video-foundry
video-foundry 帮助创作者把可信来源图片和文案快速制作成旁白短视频。第一版提供项目创建、图片上传、脚本生成、分镜审核、TTS 旁白、字幕、背景音乐、视频合成和本地 MP4 导出能力。

## Local development

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m uvicorn video_foundry.api.main:app --reload
```

```powershell
cd web
npm install
npm run typecheck
npm run build
npm run dev
```

## Project API

Phase 1 exposes disk-backed project metadata endpoints:

```text
POST /api/projects
GET  /api/projects
GET  /api/projects/{project_id}
```

Projects are stored under `projects/{project_id}` with `project.json` plus fixed
artifact directories for later phases. API errors use the structured
`{"error": {...}}` response shape.


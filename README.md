# video-foundry
VideoFoundry 帮助创作者把可信来源图片和文案快速制作成旁白短视频。第一版提供项目创建、图片上传、脚本生成、分镜审核、TTS 旁白、字幕、背景音乐、视频合成和本地 MP4 导出能力。

## Local development

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m uvicorn auto_image.api.main:app --reload
```

```powershell
cd web
npm install
npm run typecheck
npm run build
npm run dev
```

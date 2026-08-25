# 文案与模板矩阵视频 Skill v1.7.3

本安装包包含两个独立功能：

1. **文案一键成片**：完整文案理解、语义分镜、素材库/AI 素材、可选阿里配音、字幕、音效、BGM、转场、首帧封面和最终 MP4。
2. **模板成片（默认）**：上文字—中素材—下文字，只使用客户素材或素材库中状态为“可使用”的素材，禁止 AI 生成；默认无配音，支持单条、多版本和批量生成，并可输出批次耗时报告。

详细输入格式、示例和功能边界见 `功能介绍.md`。

v1.7.0 在 v1.6.0 的时长、素材数量、视频优先、A/B 和 BGM 规则上增加了 12 套原创视觉模板、稳定 `template_id`、4 个内置 OFL 中文字体家族和同一目录驱动的批量校验。它还修复中英混排空格丢失，以及 50/60fps 素材在模糊背景分支提前结束的问题。12 条旧版案例、素材库个人连接和“模板成片禁止 AI 生成”规则保持不变。

v1.7.1 将模板成片设为默认入口。未明确指定功能时直接使用 `text-media-text`；只有明确提出完整文案成片、口播配音、语义分镜或保留长文案为完整视频时，才使用功能一。

v1.7.2 将原本的 `native-bold` 默认版式登记为第 13 个稳定模板“默认原生大字”，默认项目直接使用 `template_id: native-bold`。

v1.7.3 要求每台新电脑在首次安装前连接并验证自己的素材库。安装器会运行 `material_library.py inspect`；未连接、索引不可读或索引为空时，首次安装会停止。已有安装升级时保留原有个人连接，不要求重复配置。

安装包不含 API 密钥、服务器密码、SSH 密钥或素材库原始文件；仅包含公开案例成片和预览图。

安装包中的 `assets/examples/text-media-text` 包含公开案例成片，`assets/fonts` 包含模板运行所需字体，因此 v1.7.1 压缩包体积会明显大于旧版。

## Windows 一键安装

1. 完整解压 ZIP，不要直接在压缩包里运行脚本。
2. 在解压目录打开 PowerShell。
3. 先连接这台电脑自己的素材库。连接本地或挂载目录：

```powershell
python .\script-to-matrix-video\scripts\material_library.py connect --root "D:\media\your-library"
```

或者连接已经配置 SSH 密钥的远程素材库：

```powershell
python .\script-to-matrix-video\scripts\material_library.py connect --host YOUR_SSH_ALIAS --user YOUR_USER --remote-root /absolute/library/path
```

4. 确认连接：

```powershell
python .\script-to-matrix-video\scripts\material_library.py inspect
```

5. 执行安装：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

如果电脑已有旧版，使用 `-Force`。安装器会先把旧 Skill 移到带时间戳的备份目录：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Force
```

安装完成后重启 Codex。

## 必要环境

- Python 3.10 或更高版本；
- FFmpeg，且 `ffmpeg` 和 `ffprobe` 位于 `PATH`；
- 使用 AI 图片时，Codex 环境需要图片生成能力；
- 使用阿里配音时，需要本机环境变量 `DASHSCOPE_API_KEY`；
- 远程素材库需要 OpenSSH 和已配置的 SSH 密钥或 Agent。

安装器不会安装 FFmpeg，也不会复制或保存 API 密钥、SSH 密钥或服务器密码。
覆盖旧版本前，安装器会先校验 13 套模板目录、4 个字体文件、许可证和 SHA-256；分享包不完整时会停止，不会先移动现有 Skill。

## 素材库连接（首次安装必需）

推荐使用上面的 `connect` 命令。它会先读取非空的 `index.jsonl`，验证成功后才把非敏感连接信息保存到个人配置。也可以在受管理的电脑上使用环境变量连接本地或挂载目录：

```powershell
$env:MATRIX_MATERIAL_LIBRARY_ROOT = "D:\media\huangque-media"
```

远程 SSH 只读访问：

```powershell
$env:MATRIX_MATERIAL_LIBRARY_HOST = "media.example.com"
$env:MATRIX_MATERIAL_LIBRARY_USER = "media-reader"
$env:MATRIX_MATERIAL_LIBRARY_REMOTE_ROOT = "/srv/huangque-media"
```

无论采用哪种配置方式，都必须验证：

```powershell
python "$env:USERPROFILE\.codex\skills\script-to-matrix-video\scripts\material_library.py" inspect
```

`connect` 命令默认在 `%USERPROFILE%\.codex\script-to-matrix-video\material-library.json` 中写入非敏感连接信息：

```json
{
  "host": "material-library-ssh-alias",
  "user": "media-reader",
  "remote_root": "/srv/huangque-media"
}
```

然后在 `%USERPROFILE%\.ssh\config` 中为这个别名配置 `HostName`、`User` 和 `IdentityFile`。个人配置、Skill 和分享包都不能包含密码或私钥内容。每台同事电脑需要使用自己的 SSH 私钥，并由服务器授权对应公钥。

连接配置优先级为：命令行参数、`MATRIX_MATERIAL_LIBRARY_*` 环境变量、个人 JSON 配置。执行上面的 `inspect` 命令后返回素材数量和状态统计，即表示 Skill 已经可以直接调用素材库；否则首次安装和首次渲染都会停止。

请优先使用只读服务器账号和 SSH 密钥，不要把密码写入个人配置、环境示例、项目文件、Skill 或聊天内容。

## 使用入口

默认模板成片（无需写功能名）：

```text
使用 $script-to-matrix-video，围绕“AI 工作流”写一条观点反差型文案并直接出视频。
```

文案一键成片：

```text
使用 $script-to-matrix-video 的“文案一键成片”功能，把下面文案制作成9:16矩阵视频，素材库优先，缺失素材用AI图片，BGM自动，直接输出MP4：……
```

模板成片：

```text
使用 $script-to-matrix-video 的“模板成片”功能。上方标题：……；下方副标题：……；不要配音，中间只能使用客户素材或素材库中状态为“可使用”的素材，禁止AI生成；生成2个版本，BGM自动。
```

模板批量成片：

```text
使用 $script-to-matrix-video 的“模板成片”批量功能，提取这些截图/表格中的文案；只允许客户素材或素材库素材，禁止AI生成；每条生成2个版本，同时生成并记录总时间和每条耗时。
```

默认输出 1080×1920、30 fps、H.264/AAC 通用竖屏母版，可用于抖音、小红书、视频号和快手。明确写“不要 BGM”时会关闭背景音乐。

## 手动安装或其他系统

把完整的 `script-to-matrix-video` 文件夹复制到：

- Windows：`%USERPROFILE%\.codex\skills\script-to-matrix-video`
- macOS/Linux：`~/.codex/skills/script-to-matrix-video`

先运行 `scripts/material_library.py connect` 和 `inspect`，再安装 Python 依赖并重启 Codex。更完整的配置和排错说明位于 Skill 内的 `references/installation.md`。

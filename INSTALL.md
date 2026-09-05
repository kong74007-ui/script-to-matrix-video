# 文案与模板矩阵视频 Skill v1.9.0

本安装包包含两个独立功能：

1. **文案一键成片**：完整文案理解、语义分镜、素材库/AI 素材、可选阿里配音、字幕、音效、BGM、转场、首帧封面和最终 MP4。
2. **模板成片（默认）**：上文字—中素材—下文字，禁止 AI 生成素材；主站 HQ CLI 路径支持当前网站模板、平台素材库、公共/个人复刻音色、语速和单条/批量生成，本地路径继续支持内置模板与客户素材。

详细输入格式、示例和功能边界见 `功能介绍.md`。

v1.7.0 在 v1.6.0 的时长、素材数量、视频优先、A/B 和 BGM 规则上增加了 12 套原创视觉模板、稳定 `template_id`、4 个内置 OFL 中文字体家族和同一目录驱动的批量校验。它还修复中英混排空格丢失，以及 50/60fps 素材在模糊背景分支提前结束的问题。12 条旧版案例、素材库个人连接和“模板成片禁止 AI 生成”规则保持不变。

v1.7.1 将模板成片设为默认入口。未明确指定功能时直接使用 `text-media-text`；v1.9.0 起，明确的模板配音也留在模板成片，只有完整文案、逐镜口播、语义分镜或语音同步字幕才使用功能一。

v1.7.2 将原本的 `native-bold` 默认版式登记为第 13 个稳定模板“默认原生大字”，默认项目直接使用 `template_id: native-bold`。

v1.7.3 要求每台新电脑在首次安装前连接并验证自己的素材库。安装器会运行 `material_library.py inspect`；未连接、索引不可读或索引为空时，首次安装会停止。已有安装升级时保留原有个人连接，不要求重复配置。

v1.7.4 取消标题、固定 CTA 和浮层文字的透明度渐入。文字从显示的第一帧直接达到完整不透明度，末尾短暂渐出、缩放弹入和素材转场不受影响。

v1.7.5 将默认 `native-bold` 更新为左对齐数据型排版：自动拆分小标题、超大主数字、对比结论和底部 CTA；没有数字时使用左对齐标题回退。播放器预览信息与进度线不会进入成片。

v1.8.0 将当前确认的模板集整理为 8 套标准 FFmpeg 模板和 17 套 HyperFrames 参考排版模板，默认恢复为 `black-left-bold`。新增参考模板稳定 ID、五层文字输入、批量渲染脚本、17 条 MP4 案例和 17 张首帧 JPG。

v1.8.1 将 17 套参考模板的时长改为每条任务自动随机 8–15 秒，并固定要求 3 段不同的视频素材。用户不填写时长；准备脚本记录随机值，确保同一任务 dry-run 与正式渲染一致。

v1.8.3 重做美业粉白私域运营参考模板：取消圆角素材卡，并修复随机时长下最后一段素材黑屏。

v1.8.4 进一步贴合美业参考图：重做粉白宋体效果、放大顶部主标题，并把底部两行改为错位排版。

v1.8.5 为美业模板内置 `Noto Serif SC` 可变宋体，使用真实 600/700 字重替代小薇体的合成加粗，避免不同电脑出现字形和粗细偏差。

v1.8.6 为美业模板四层文字增加约 3° 轻微右倾，并在 Windows 上隐藏 HyperFrames、浏览器和 FFmpeg 渲染子进程窗口，避免批量渲染弹出多个黑窗。

v1.9.0 新增已上线的黄雀主站 HQ CLI 0.15.4 模板成片路径。它实时读取网站模板和账号音色，支持 120 字配音文案、公共/个人复刻音色、0.5–2.0 语速、配音时自动关闭 BGM、音频决定成片时长，以及共享配音缓存的 2–5 条批量任务。所有付费操作仍先报价再确认，原本地渲染能力保持不变。

安装包不含 API 密钥、服务器密码、SSH 密钥或素材库原始文件；仅包含公开案例成片和预览图。

安装包中的 `assets/examples/text-media-text` 包含 26 套公开案例成片和首帧预览，`assets/fonts` 包含模板运行所需字体，因此 v1.8.x 压缩包体积会明显大于旧版。

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
- 使用 18 套 `ref-` 参考排版模板时，需要 Node.js 和 npm；渲染脚本固定调用 HyperFrames `0.8.17`；
- 使用 AI 图片时，Codex 环境需要图片生成能力；
- 使用阿里配音时，需要本机环境变量 `DASHSCOPE_API_KEY`；
- 远程素材库需要 OpenSSH 和已配置的 SSH 密钥或 Agent。
- 使用主站当前模板成片时，需要 HQ CLI `0.15.4+` 和已登录的黄雀账号；主站自行管理素材库与配音凭证，不需要把这些凭证写入 Skill。

安装器不会安装 FFmpeg，也不会复制或保存 API 密钥、SSH 密钥或服务器密码。
覆盖旧版本前，安装器会先校验 8 套标准模板、18 套参考模板、26 组案例文件、5 个字体文件、许可证和 SHA-256；分享包不完整时会停止，不会先移动现有 Skill。

## 素材库连接（本地渲染路径必需）

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

连接配置优先级为：命令行参数、`MATRIX_MATERIAL_LIBRARY_*` 环境变量、个人 JSON 配置。执行上面的 `inspect` 命令后返回素材数量和状态统计，即表示本地渲染路径可以调用素材库；否则安装器和本地渲染会停止。主站 HQ CLI 路径使用账号平台素材库，不读取这份本地配置。

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

主站模板成片配音：

```text
使用 $script-to-matrix-video 调用黄雀主站当前模板成片。先读取当前模板和 ready 音色；使用我的个人复刻音色，语速1.2，配音文案不超过120字。先展示点数报价，等我确认后再提交；生成后只查询原任务。
```

完整 HQ CLI 参数与恢复规则见 `script-to-matrix-video/references/hosted-template-cli.md`。

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

# Script to Matrix Video

一个面向中文矩阵引流内容的 Codex Skill，输出可直接发布的 9:16 MP4。

当前版本：`v1.9.0`

## 两个独立功能

默认入口是 `text-media-text` 模板成片。用户未指定功能、只说“出个视频”、只给主题，或提供标题/CTA、截图、表格时，直接进入模板成片；明确要求“模板成片配音”时仍留在模板成片。只有要求完整文案成片、语义分镜、逐镜口播或语音同步字幕时，才进入文案一键成片。

### 1. 文案一键成片

输入完整客户文案，自动完成全文理解、语义分镜、素材检索、AI 图片补缺、可选阿里云 CosyVoice 配音、字幕、音效、BGM、转场、首帧封面和最终 MP4 渲染。

### 2. `text-media-text` 模板成片（默认）

输入上方标题和下方副标题/CTA，生成“上文字—中素材—下文字”的竖屏视频。默认无配音；使用主站 HQ CLI 时可选择公共或个人复刻音色、设置语速，并让成片时长跟随配音。支持单条、多版本和批量生成。

模板成片只允许使用客户素材或已审核素材库中的图片和视频，禁止 AI 生成素材。主站路径使用账号平台素材库，本地路径使用已连接的本地/SSH 素材库；两者都不会用 AI 素材填充。

## 当前主站模板成片

当本机已有已登录的 HQ CLI `0.15.4+`，或用户要求使用网站当前模板、平台素材库、公共音色、个人复刻音色或语速调节时，Skill 优先调用主站能力。它会实时读取模板和音色目录，不把仓库内置模板 ID 当成线上目录。

- 单条：`matrix-template-generate`
- 批量：`matrix-template-batch-generate`，数量 2–5；仅用于实时目录允许批量的模板
- 配音：可选 `voiceover.text`、`voiceover.voice`、`voiceover.voice_scope`、`voiceover.speed`
- 文案：配音文案最多 120 字，语速 0.5–2.0
- 音频：开启配音时自动关闭 BGM，最终时长跟随实际配音
- 批量配音：共享同一音频缓存，重试复用原批次和原任务
- 付费边界：先报价并展示点数，用户明确确认后才执行带 `--confirm` 的提交

完整命令、参数和恢复规则见 [主站模板成片 CLI 合同](script-to-matrix-video/references/hosted-template-cli.md)。仓库内置的 26 套模板和本地渲染器继续保留，用于离线渲染、客户本地素材或模板源码定制；主站任务失败后不会静默切换到本地重新生成。

模板成片总时长硬性不低于 8 秒，常规范围为 8–15 秒。无配音时按以下公式计算：

```text
目标时长 = max(8秒, 文字阅读时间 + 1.5秒)
```

阅读速度按每秒约 5 个可见中文字符、字母或数字估算。渲染器会再次计算并把过短清单延长到完整的文案阅读时长，不会把所有视频都固定成 8 秒。

例外：18 套 `ref-` 参考排版不让用户填写时长。每条新任务自动随机生成 8–15 秒整数时长，并记录到准备清单；同一次任务重跑保持一致。每条固定使用 3 段不同的素材库视频并按总时长均分。选择它们时仍必须先把长文案压缩或拆条，不能为了塞字而破坏已确认的字号和层级。

模板素材采用视频优先策略：8–10 秒至少使用 2 个不同素材，10–15 秒至少 3 个，默认至少包含 1 个素材库视频。只有两次视频检索均无合适结果并写明原因时，才允许纯图片成片。批量开启 BGM 时会轮换曲库：2–3 条成片至少 2 首，4 条及以上至少 3 首，相邻成片不得使用同一首。

批量渲染前必须运行 `scripts/validate_template_batch.py`，它会阻止单素材、无理由纯图片、A/B 素材重复、BGM 未轮换以及时长不足的任务进入渲染。

## 26 套可复用视觉模板

`text-media-text` 现在包含两组稳定模板：8 套黑白字体排版标准模板，以及 18 套根据已确认案例保留下来的 HyperFrames 参考排版模板。默认仍是黑底左排粗体 `black-left-bold`；参考模板 ID 使用 `ref-01-...` 到 `ref-18-...`，覆盖 AI 沙龙、城市圈层、女性成长、同城活动、OPC 招募、美业私域和强 CTA 等排版。

```json
{"layout": {"template_id": "black-left-bold"}}
```

8 套标准模板位于 `script-to-matrix-video/assets/templates/catalog.json`，使用 FFmpeg 渲染；18 套参考排版位于 `script-to-matrix-video/assets/templates/reference-typography-17/`，使用固定版本 HyperFrames 渲染，并由 `scripts/render_reference_typography.py` 统一准备素材与批量输出。完整 ID、输入字段和适用场景见 [参考排版模板目录](script-to-matrix-video/references/reference-typography-templates.md)。

8 套标准模板支持 `emphasis.v1` 语义重点；18 套参考模板直接固定五层文字的字号、颜色、描边和层级，输入 `top1`/`top2`/`top3` 与 `bottom1`/`bottom2` 即可复用，不在渲染期间调用模型。

Skill 自带 `Noto Sans SC`、`Noto Serif SC`、`ZCOOL XiaoWei`、`Ma Shan Zheng`、`ZCOOL KuaiLe` 五个 OFL 中文字体家族，并自动交给对应渲染器加载，不依赖运行电脑碰巧安装了什么字体。详细选择建议见 [视觉模板目录](script-to-matrix-video/references/style-templates.md)。

v1.7.0 同时修复了两项真实批量问题：中英混排会保留英文词间空格；`blurred-media` 使用 50/60fps 素材时会先统一到项目帧率，不再因 `-frames:v` 提前结束。

v1.7.1 将模板成片设为 Skill 默认路由：没有明确模式时不再询问二选一；只给主题时可先生成上方标题和下方 CTA，再使用客户或素材库素材直接成片。v1.9.0 起，模板配音继续留在功能二，完整文案和语义分镜仍由功能一处理。

v1.7.2 把原本的默认 `native-bold` 版式登记为第 13 个稳定模板“默认原生大字”。默认项目现在直接使用 `template_id: native-bold`，保持白色粗体、黄红重点词、模糊素材背景和无分隔线。

v1.7.3 将个人素材库连接设为首次安装硬门槛。新电脑必须先用 `material_library.py connect` 保存本机连接并通过 `inspect`，安装器才会完成首次安装；Skill 在首次渲染前也会复核连接。升级已有安装不会要求重复建档。

v1.7.4 取消所有标题、固定 CTA 和浮层文字的透明度渐入。文字从出现的第一帧即为完全不透明；短暂渐出、可选缩放弹入和素材转场保持不变。

v1.7.5 重做了当时的 `native-bold` 数据版式。后续模板精简将默认恢复为 `black-left-bold`，避免旧模板被静默恢复。

v1.8.0 新增 17 套经过成片验证的 HyperFrames 参考排版模板，保存完整模板源文件、稳定 ID、批量渲染脚本、17 条 MP4 案例和 17 张首帧预览；原有 8 套标准模板继续保留。

v1.8.1 将 17 套参考模板从固定 8 秒改为每条任务自动随机 8–15 秒；随机结果写入准备清单并在同一任务内复用。每条参考模板统一使用 3 段不同视频素材，按随机总时长自动均分。

v1.8.2 新增 `ref-18-beauty-private-domain`：粉白双色美业私域标题，并补齐第 18 条 MP4/JPG 案例与安装校验。

v1.8.3 将第 18 套改为直角全画幅素材，移除误带入的圆角应用卡片；参考模板输入视频会先在任务目录循环补足到 15 秒，固定渲染后再按随机 8–15 秒精确裁切，避免最后一段素材黑屏。

v1.8.4 重新校准第 18 套的字体与坐标：粉色主标题放大并上移，白色副标题改用同款宋体，底部两行采用左起、右移的错位排版，同时收紧描边和阴影层次。

v1.8.5 将第 18 套从浏览器合成加粗的装饰宋体换成内置 `Noto Serif SC` 真实 600/700 字重，并按参考图重新收紧字距、描边和硬阴影；示例 MP4/JPG 同步更新。

v1.8.6 为第 18 套顶部和底部文字统一增加约 3° 的轻微右倾，保留原字号、分行和坐标；同时修复 Windows 批量渲染时 HyperFrames、浏览器与 FFmpeg 子进程弹出黑色控制台窗口的问题。

v1.9.0 同步已上线的黄雀主站模板成片能力：新增 HQ CLI 0.15.4 托管路径，支持实时模板目录、平台素材库、公共/个人复刻音色、0.5–2.0 语速、120 字配音文案、配音时关闭 BGM、音频决定成片时长，以及单条/批量报价确认和原任务恢复。原有本地渲染器及 26 套内置模板不删除。

PR 会运行零付费模板回归，校验标准模板目录、参考模板清单、字体、示例文件和批量输入规则。

## 模板案例视频

仓库现在为全部 26 套模板保存了可直接查看的 MP4 和第一帧 JPG：8 套标准模板案例，以及 18 套参考排版案例。参考排版案例为 1080×1920、H.264/AAC；新任务时长随机为 8–15 秒。

- [查看案例文案与 A/B 视频索引](script-to-matrix-video/references/template-examples.md)
- [打开案例视频目录](script-to-matrix-video/assets/examples/text-media-text/)

案例只用于展示成片效果和校准布局，不会作为新客户视频的素材重复使用。

## 素材库能力

使用仓库内置本地渲染器前必须连接自己的本地或 SSH 素材库，连接成功后可以完成：

- 索引读取和状态统计；
- 按完整文案语义检索图片、视频和 BGM；
- 只选择状态为“可使用”的记录；
- 将选中素材复制到当前视频项目；
- 保存素材库 `record_id` 和来源路径。

连接参数可以来自命令行、`MATRIX_MATERIAL_LIBRARY_*` 环境变量，或个人配置文件：

```text
~/.codex/script-to-matrix-video/material-library.json
```

个人配置只保存主机别名、用户名和素材库目录。密码、SSH 私钥、API 密钥和素材文件不会进入 Skill 或仓库。本地路径未通过 `inspect` 前不会开始成片；主站路径不读取这些本地连接，配置方式见 [安装说明](INSTALL.md)。

## Windows 安装

```powershell
git clone https://github.com/kong74007-ui/script-to-matrix-video.git
cd script-to-matrix-video
python .\script-to-matrix-video\scripts\material_library.py connect --root "D:\media\your-library"
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

远程素材库可把连接命令替换为：

```powershell
python .\script-to-matrix-video\scripts\material_library.py connect --host YOUR_SSH_ALIAS --user YOUR_USER --remote-root /absolute/library/path
```

覆盖旧版本并保留时间戳备份：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Force
```

安装完成后重启 Codex。

## 运行环境

- Python 3.10+
- FFmpeg 和 FFprobe
- 阿里配音需要本机环境变量 `DASHSCOPE_API_KEY`
- 远程素材库需要 OpenSSH 和已授权的 SSH 密钥
- 主站模板成片需要已登录的 HQ CLI `0.15.4+`；服务端管理素材库和配音凭证
- AI 图片能力只用于文案一键成片，不用于模板成片

## 使用示例

默认模板成片：

```text
使用 $script-to-matrix-video，围绕“AI 工作流”写一条观点反差型文案并直接出视频。
```

主站模板成片配音：

```text
使用 $script-to-matrix-video 调用黄雀主站当前模板成片。使用我的个人复刻音色，语速 1.2，不要 BGM；先把模板、音色和点数报价给我确认，再生成。上方标题：……；下方 CTA：……；配音文案：……
```

文案一键成片：

```text
使用 $script-to-matrix-video 的“文案一键成片”功能，把下面文案制作成9:16矩阵视频，优先使用素材库，BGM自动，直接输出MP4：……
```

模板批量成片：

```text
使用 $script-to-matrix-video 的“模板成片”批量功能，提取这些截图中的文案，每条生成2个版本；只使用客户素材或素材库素材，禁止AI生成；不要配音，BGM自动，并记录总时间和单条耗时。
```

更完整的功能边界和输入格式见 [功能介绍](功能介绍.md)。

## 仓库结构

```text
script-to-matrix-video/   Skill 本体
  assets/fonts/           5 个开源中文字体家族及许可证
  assets/templates/       8 套标准模板与 18 套 HyperFrames 参考排版模板
  assets/examples/        26 套模板案例视频与首帧预览图
  references/hosted-template-cli.md  主站 HQ CLI 参数、报价和恢复合同
install.ps1               Windows 安装器
INSTALL.md                完整安装与连接配置
功能介绍.md               两个独立功能的说明
```

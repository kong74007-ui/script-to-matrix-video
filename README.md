# Script to Matrix Video

一个面向中文矩阵引流内容的 Codex Skill，输出可直接发布的 9:16 MP4。

当前版本：`v1.8.7`

> ## ⚠️ 黄雀主站现状（2026-09-10 起，先读这段）
>
> 黄雀主站上「模板成片」已平台化：由主站矩阵模板能力（matrix-template-*，20 个模板）在渲染机集群出片，成片子 Agent（hq-compose）用 `hq capabilities` / `hq run` 调用；本地渲染器（本仓库 `scripts/` 与下方两功能描述）在主站**已退役**，仅保留作离线参考、模板资产源与外部环境自渲染。
>
> **训练子 Agent 请读 `script-to-matrix-video/SKILL.md`（平台版正文）+ `references/production-platform.md`（平台对接完整规范）**；模板目录/语义断句/时长/素材/批量/交付红线均以这两份为准。生产模板目录 20 个：full-overlay-bold、poster-split（2 个 FFmpeg）+ ref-01~ref-17（17 个 HyperFrames 参考排版）+ nine-grid-reveal（九宫格开场）。
>
> 下方「两个独立功能」为本地渲染器时代的说明，仅归档参考。

2026-09-10 模板更新：新增独立的 `nine-grid-reveal` 九宫格开场·全屏展示，固定 12 秒，标题与 CTA 从首帧显示至结尾，并随模板保存和复用已授权同步到仓库的参考 BGM。

2026-09-10 后续同步：新增 `triple-strip-shutter` 三横屏开场·光栅快切和 `yellow-banner-zoom` 黄条标题·变幅冲击，两套源模板与各自绑定 BGM 经用户本次授权公开同步至 GitHub。精简后当时仓库共 21 套模板（18 套参考排版 + 3 套独立动效），原 8 套标准模板及其案例已移除。

## 两个独立功能

2026-09-11 新增离线源模板 **[三屏旋展甩切·红黄粗体（fan-whip-static）](script-to-matrix-video/references/fan-whip-static.md)**：1080×1920、30 fps、377 帧，红字奶白描边标题/CTA、黄色副标题，文字从首帧静态显示；保留三横屏旋展、甩切动效与原 BGM。模板和绑定音频已获仓库所有者公开同步授权，不包含客户素材。新增后仓库离线资产为 **22 套（18 ref + 4 动效）**。此更新不部署主站，平台数量仍以实时目录为准。

后续保存新模板同时更新本机与 GitHub，见 [维护同步规则](script-to-matrix-video/references/template-publishing.md)。

默认入口是 `text-media-text` 模板成片。用户未指定功能、只说“出个视频”、只给主题，或提供标题/CTA、截图、表格时，直接进入模板成片；只有明确要求完整文案成片、口播配音、语义分镜或保留长文案为完整视频时，才进入文案一键成片。

### 1. 文案一键成片

输入完整客户文案，自动完成全文理解、语义分镜、素材检索、AI 图片补缺、可选阿里云 CosyVoice 配音、字幕、音效、BGM、转场、首帧封面和最终 MP4 渲染。

### 2. `text-media-text` 模板成片（默认）

输入上方标题和下方副标题/CTA，生成“上文字—中素材—下文字”的竖屏视频。默认无配音，支持单条、多版本和批量生成，并记录批次与单条耗时。

模板成片只允许使用客户素材或素材库中状态为“可使用”的图片和视频，禁止 AI 生成素材。没有合适素材时返回 `material_missing`，不会使用无关素材填充。

离线参考排版每条随机 8–15 秒，使用 3 个不同的已审核视频；批量 BGM 保留轮换规则。四套独立动效模板保留各自固定时间线与绑定音乐。FFmpeg 通用渲染器保留用于文案成片和自定义清单，不再提供原 8 个标准模板。

## 22 套可复用视觉模板（离线资产）

原 8 套标准 FFmpeg 模板已删除。保留 18 套 HyperFrames 参考排版，以及 `nine-grid-reveal`、`triple-strip-shutter`、`yellow-banner-zoom`、`fan-whip-static` 四套独立动效模板。

离线默认改为 **`ref-15-tianjin-monochrome`（天津黑白极简）**，可替换任意主题文案。使用参考包的 rows 格式和 `scripts/render_reference_typography.py`，不把 ref ID 传给 FFmpeg 渲染器。完整 ID 与五层文字输入见 [参考排版说明](script-to-matrix-video/references/reference-typography-templates.md)。

`assets/templates/catalog.json` 仅保存空标准目录和移除 ID，用于拒绝旧调用。参考模板及字体文件、四套动效和绑定 BGM 均保留。**线上平台目录仍实时读取，本次未部署或修改服务器。**

### 九宫格开场·全屏展示

指定 `nine-grid-reveal` 或“九宫格开场接全屏展示”即可使用。模板固定为 1080×1920、30 fps、12 秒，标题和底部 CTA 从第 0 帧保持到结尾；九格按固定顺序显现，3.2 秒切全屏，并在 6.3、9 秒切换后续素材。输入 `title`、`tagline`、9 条独立 `grid` 视频和 3 条 `main` 视频；全屏素材可以复用九格素材，只允许客户提供或素材库中状态为“可使用”的视频。

模板绑定 `assets/audio/reference-bgm.m4a`，准备脚本校验 SHA-256 后原样复制，不随机选曲、不参与批量 BGM 轮换。使用 `scripts/prepare_nine_grid.py` 在新项目目录准备，再用 HyperFrames `0.8.33` 检查并渲染；原有 18 套参考排版继续使用 `0.8.29`。完整输入、素材时长和出片流程见 [九宫格模板说明](script-to-matrix-video/references/nine-grid-reveal.md)。

### 三横屏开场·光栅快切

指定 `triple-strip-shutter` 即可使用。模板固定 1080×1920、30 fps、17.6 秒（528 帧）：前三条横向视频带同时播放，随后进入五段全屏素材与固定光栅快切。`title`、`subtitle`、`ctaLine1`、`ctaLine2` 四层文字可替换，并从首帧保持到结尾；三条 `opening` 和五条 `main` 视频只能使用客户提供或素材库状态为“可使用”的视频，禁止 AI 素材。

模板源与绑定 BGM 经用户本次授权公开同步；音乐随模板复用，不随机选曲或参与批量轮换。使用 `scripts/prepare_triple_strip.py` 准备新项目，再由 HyperFrames `0.8.33` 检查和渲染。字段上限、素材去重及固定切点见 [三横屏模板说明](script-to-matrix-video/references/triple-strip-shutter.md)。

### 黄条标题·变幅冲击

指定 `yellow-banner-zoom` 即可使用。模板固定 1080×1920、30 fps、302 帧（约 10.0667 秒）：首尾为横向视频带与同素材模糊背景，中段全屏，切换时保留变幅与径向冲击。可替换 `title`、`subtitle1`、`subtitle2`、`sourceLabel`、`body`、`cta` 六个文字字段，非空文字均从首帧保持到结尾；输入三条不同的客户视频或素材库状态为“可使用”的视频，禁止 AI 素材。

模板源与绑定 BGM 经用户本次授权公开同步；音乐随模板复用，不随机选曲或参与批量轮换。使用 `scripts/prepare_yellow_banner.py` 准备新项目，再由 HyperFrames `0.8.33` 检查和渲染。字段约束、固定帧数与出片流程见 [黄条标题模板说明](script-to-matrix-video/references/yellow-banner-zoom.md)。两套新模板均不使用标准模板阅读时长公式或参考排版的随机 8–15 秒规则。

Skill 自带 `Noto Sans SC`、`Noto Serif SC`、`ZCOOL XiaoWei`、`Ma Shan Zheng`、`ZCOOL KuaiLe` 五个 OFL 中文字体家族，并自动交给对应渲染器加载，不依赖运行电脑碰巧安装了什么字体。详细选择建议见 [视觉模板目录](script-to-matrix-video/references/style-templates.md)。

v1.7.0 同时修复了两项真实批量问题：中英混排会保留英文词间空格；`blurred-media` 使用 50/60fps 素材时会先统一到项目帧率，不再因 `-frames:v` 提前结束。

v1.7.1 将模板成片设为 Skill 默认路由：没有明确模式时不再询问二选一；只给主题时可先生成上方标题和下方 CTA，再使用客户或素材库素材直接成片。完整文案、配音和语义分镜仍可通过明确指令进入功能一。

v1.7.2 把原本的默认 `native-bold` 版式登记为第 13 个稳定模板“默认原生大字”。默认项目现在直接使用 `template_id: native-bold`，保持白色粗体、黄红重点词、模糊素材背景和无分隔线。

v1.7.3 将个人素材库连接设为首次安装硬门槛。新电脑必须先用 `material_library.py connect` 保存本机连接并通过 `inspect`，安装器才会完成首次安装；Skill 在首次渲染前也会复核连接。升级已有安装不会要求重复建档。

v1.7.4 取消所有标题、固定 CTA 和浮层文字的透明度渐入。文字从出现的第一帧即为完全不透明；短暂渐出、可选缩放弹入和素材转场保持不变。

v1.7.5 重做了当时的 `native-bold` 数据版式。该历史默认后来已移除，当前离线默认见上文。

v1.8.0 新增 17 套经过成片验证的 HyperFrames 参考排版模板，保存完整模板源文件、稳定 ID、批量渲染脚本、17 条 MP4 案例和 17 张首帧预览；当时保留的 8 套标准模板现已移除。

v1.8.1 将 17 套参考模板从固定 8 秒改为每条任务自动随机 8–15 秒；随机结果写入准备清单并在同一任务内复用。每条参考模板统一使用 3 段不同视频素材，按随机总时长自动均分。

v1.8.2 新增 `ref-18-beauty-private-domain`：粉白双色美业私域标题，并补齐第 18 条 MP4/JPG 案例与安装校验。

v1.8.3 将第 18 套改为直角全画幅素材，移除误带入的圆角应用卡片；参考模板输入视频会先在任务目录循环补足到 15 秒，固定渲染后再按随机 8–15 秒精确裁切，避免最后一段素材黑屏。

v1.8.4 重新校准第 18 套的字体与坐标：粉色主标题放大并上移，白色副标题改用同款宋体，底部两行采用左起、右移的错位排版，同时收紧描边和阴影层次。

v1.8.5 将第 18 套从浏览器合成加粗的装饰宋体换成内置 `Noto Serif SC` 真实 600/700 字重，并按参考图重新收紧字距、描边和硬阴影；示例 MP4/JPG 同步更新。

v1.8.6 为第 18 套顶部和底部文字统一增加约 3° 的轻微右倾，保留原字号、分行和坐标；同时修复 Windows 批量渲染时 HyperFrames、浏览器与 FFmpeg 子进程弹出黑色控制台窗口的问题。

v1.8.7 将参考排版模板的 HyperFrames 固定版本从 `0.8.17` 升级到 `0.8.29`，提升 Windows 批量渲染、中文字体、音频时长、嵌套素材和 Studio 热更新的稳定性。

PR 会运行零付费模板回归，校验标准模板目录、参考模板清单、字体、示例文件、批量输入规则，以及九宫格绑定音频的完整性和复用行为。Windows 安装器在复制 Skill 前执行同样的九宫格校验。

## 模板案例视频

仓库保留 18 套参考排版的 MP4 和第一帧 JPG；原 8 套标准模板案例已移除。参考排版案例为 1080×1920、H.264/AAC；新任务时长随机为 8–15 秒。四套独立动效模板提供可复用源模板和绑定 BGM，未将客户视频打包成公开案例。

- [查看案例文案与 A/B 视频索引](script-to-matrix-video/references/template-examples.md)
- [打开案例视频目录](script-to-matrix-video/assets/examples/text-media-text/)

案例只用于展示成片效果和校准布局，不会作为新客户视频的素材重复使用。

## 素材库能力

Skill 首次安装必须连接自己的本地或 SSH 素材库，连接成功后可以完成：

- 索引读取和状态统计；
- 按完整文案语义检索图片、视频和 BGM；
- 只选择状态为“可使用”的记录；
- 将选中素材复制到当前视频项目；
- 保存素材库 `record_id` 和来源路径。

连接参数可以来自命令行、`MATRIX_MATERIAL_LIBRARY_*` 环境变量，或个人配置文件：

```text
~/.codex/script-to-matrix-video/material-library.json
```

个人配置只保存主机别名、用户名和素材库目录。密码、SSH 私钥、API 密钥和客户视频不会进入 Skill 或仓库；九宫格绑定 BGM 已获授权公开，三横屏与黄条标题的绑定 BGM 经用户本次授权同步。新电脑未通过 `inspect` 前不会开始成片，配置方式见 [安装说明](INSTALL.md)。

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
- HyperFrames 模板需要 Node.js/npm；参考排版固定 `0.8.29`，前三套独立动效模板固定 `0.8.33`，`fan-whip-static` 固定 `0.8.34`
- 阿里配音需要本机环境变量 `DASHSCOPE_API_KEY`
- 远程素材库需要 OpenSSH 和已授权的 SSH 密钥
- AI 图片能力只用于文案一键成片，不用于模板成片

## 使用示例

默认模板成片：

```text
使用 $script-to-matrix-video，围绕“AI 工作流”写一条观点反差型文案并直接出视频。
```

文案一键成片：

```text
使用 $script-to-matrix-video 的“文案一键成片”功能，把下面文案制作成9:16矩阵视频，优先使用素材库，BGM自动，直接输出MP4：……
```

模板批量成片：

```text
使用 $script-to-matrix-video 的“模板成片”批量功能，提取这些截图中的文案，每条生成2个版本；只使用客户素材或素材库素材，禁止AI生成；不要配音，BGM自动，并记录总时间和单条耗时。
```

九宫格成片：

```text
使用 $script-to-matrix-video 的 nine-grid-reveal 模板，标题“输入公司名称”，底部“品质｜细节｜诚信｜口碑”；使用我提供的9条视频，保留模板固定BGM，直接输出12秒MP4。
```

更完整的功能边界和输入格式见 [功能介绍](功能介绍.md)。

## 仓库结构

```text
script-to-matrix-video/   Skill 本体
  assets/fonts/           5 个开源中文字体家族及许可证
  assets/templates/       18 套参考排版及 4 套独立动效模板
  assets/examples/        18 套参考排版案例视频与首帧预览图
install.ps1               Windows 安装器
INSTALL.md                完整安装与连接配置
功能介绍.md               两个独立功能的说明
```

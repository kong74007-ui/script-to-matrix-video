# 黄条标题·变幅冲击

独立模板 ID：`yellow-banner-zoom`。仅在用户明确选择这个 ID 或“黄条标题·变幅冲击”时使用。源码位于 `assets/templates/yellow-banner-zoom/`，由 `scripts/prepare_yellow_banner.py` 准备任务，再用固定的 HyperFrames `0.8.33` 渲染。该模板不加入标准 `catalog.json` 或 `ref-*` 清单，也不改变普通任务的默认模板。

## 固定画面与时序

画布固定为 1080×1920、30 fps，共 302 帧，准确时长为 `302/30` 秒（约 10.066667 秒）。零起始帧区间的右端不包含在当前段内：

| 素材槽位 | 输出帧区间 | 帧数 | 画面结构 |
| --- | --- | --- | --- |
| `media[0]` | `[0, 86)` | 86 | 横向视频带与同素材模糊背景 |
| `media[1]` | `[86, 183)` | 97 | 全屏视频 |
| `media[2]` | `[183, 302)` | 119 | 横向视频带与同素材模糊背景 |

切点固定在第 86、183 帧，302 为结束边界；不要用四舍五入后的秒数累计时长。素材缩放与径向冲击效果按模板时序运行，六层文案保持独立静态。标题为黄条黑字，副标题和底部 CTA 为黄字黑描边，来源标签和正文为白字。所有非空文字从第 0 帧到第 301 帧保持完整不透明度，不渐入、不随素材模糊或提前退场。

字体、径向冲击效果和画面观感是对用户参考的近似复现；固定段落切点与总帧数可以精确核验，不声称逐像素相同。不要自动更换字体、布局或动效来容纳超长文案。

## 可替换输入

任务 JSON 可替换六个文字字段；未提供的字段沿用模板默认值。字符限制如下：

| 字段 | 最长字符数 | 可空 | 用途 |
| --- | --- | --- | --- |
| `title` | 12 | 否 | 黄条主标题 |
| `subtitle1` | 16 | 否 | 第一行副标题 |
| `subtitle2` | 16 | 是 | 第二行副标题 |
| `sourceLabel` | 8 | 是 | 素材来源/场景短标签 |
| `body` | 90 | 否 | 正文，最多三个显式 LF 换行；自动换行后缩字适配固定信息框 |
| `cta` | 24 | 是 | 底部行动提示 |

`body` 的字符上限不计 LF 换行；其他字段不接受换行。所有字段均拒绝制表符、CR 和其他控制字符。文字超限时按用户原意缩短文案，再准备任务。空可选字段不会自动补写新信息。

`media` 必须恰好包含三条不同源视频。源文件只能来自用户直接提供的视频，或素材库中状态为 `可使用` 的记录；不使用 AI 图片/视频，也不使用图片兜底。按主 Skill 现有规则检查本机素材库连接并筛选语义相关素材。

每条记录使用本地 `path`；可选 `source_start` 为非负秒数，默认 0。相对路径以任务 JSON 所在目录为基准。用户素材使用 `source: "user"`；素材库记录使用 `source: "library"`、`status: "可使用"` 和真实 `record_id`。同一视频改名或更换入点不算不同来源，帮助脚本会同时检查解析后的路径和源文件 SHA256。源视频必须覆盖 `source_start + 槽位帧数/30`，不足时重新选取合格素材或报告缺失，不循环、不冻结尾帧、不补黑帧。

以下示例假定用户已提供三个不同的本地视频；请替换为实际文件，不创建这些文件的占位副本：

```json
{
  "title": "让品质被看见",
  "subtitle1": "记录每一份认真",
  "subtitle2": "用细节回应期待",
  "sourceLabel": "实景记录",
  "body": "把每一步做好\n让用心成为看得见的细节",
  "cta": "欢迎留言了解",
  "media": [
    {"path": "media/a.mp4", "source": "user", "source_start": 0},
    {"path": "media/b.mp4", "source": "user", "source_start": 0},
    {"path": "media/c.mp4", "source": "user", "source_start": 0}
  ]
}
```

不要添加 `bgm` 或 `boundBgm` 任务字段；脚本会拒绝这类覆盖。时长、帧率和素材段落也由模板固定，不套用标准模板阅读时长公式或 `ref-*` 随机时长规则。

## 原 BGM 固定绑定

模板保存从用户本地参考中提取的原音轨，绑定信息位于 `template.json` 的 `boundBgm`：

```json
{
  "path": "assets/audio/bound-bgm.m4a",
  "sha256": "7822689569adca0db3ca2113cb17d2a0ace947a2af8d220a6e96f2b9cfe8db8f",
  "duration": 10.053991,
  "start": 0,
  "volume": 1
}
```

准备阶段校验实际音频 SHA256 和时长，再逐字节复制到任务目录。实际时长应与绑定值相差不超过 0.002 秒，绑定时长应在 302/30 秒的 0.1 秒以内。音轨约比视频短 0.013 秒是原参考的时长差，不拉伸、不循环；准备阶段不重新编码，最终 MP4 由渲染器编码为 AAC。不添加淡入淡出、增益或额外音乐。它不参与自动选曲或批量 BGM 轮换。

缺失、损坏或校验不符时修复模板的原绑定音轨，不能临时换曲。用户明确要求换曲或静音时按单独定制处理。用户已于 2026-09-10 要求将完整模板及绑定 BGM 同步到公开 GitHub 仓库；该授权说明只记录用户的发布指示，不代替音乐权利证明。迁移模板时连同绑定音频复制，不依赖原参考视频仍在原路径。

## 准备与渲染

在 Skill 目录运行准备脚本，输出路径必须是尚不存在、且位于模板目录之外的新任务目录：

```powershell
python scripts/prepare_yellow_banner.py --task "D:/video-jobs/yellow-banner/task.json" --output "D:/video-jobs/yellow-banner/prepared"
```

可用 `--template-dir` 指定该模板的本地副本；FFmpeg 或 FFprobe 不在 `PATH` 时传入 `--ffmpeg <ffmpeg.exe>` 和 `--ffprobe <ffprobe.exe>`。所有输入验证通过后才创建输出目录，已有输出不覆盖。失败任务目录保留供诊断，重试使用新目录。

脚本复制模板依赖，将三个任务视频分别归一化为 `assets/media/01.mp4`、`02.mp4`、`03.mp4`，均为 1080×1920、30 fps、静音 H.264/Rec.709 SDR，帧数分别为 86、97、119。横向前景和模糊背景由模板构图实现。模板附带的演示视频或私人参考视频不会复制到新任务。`variables.json` 保存替换文案，`provenance.json` 保存实际源路径、记录 ID、源窗口、转换参数和音频校验值。

输入色彩转换复用 `prepare_triple_strip.py` 已验证的分支：HLG 使用 FFmpeg `libplacebo` 的 BT.2390，设置 `peak_detect=0`；验证过的 SDR 不做 HDR tone mapping，PQ 沿用共享的 PQ 转换。未知色彩元数据或相机 LOG 会被拒绝，应提供正确标记的 SDR 主文件。HLG 缺少 `libplacebo` 支持时报错，不静默改换算法。出片时仍须检查肤色、高光和源素材观感。

进入生成的任务目录运行固定版本命令，先检查项目，检查通过后渲染：

```powershell
Set-Location "D:/video-jobs/yellow-banner/prepared"
$env:PRODUCER_PAGE_NAVIGATION_TIMEOUT_MS="60000"
npx --yes hyperframes@0.8.33 check --json
npx --yes hyperframes@0.8.33 render --output renders/video.mp4 --fps 30 --quality high --workers 2 --browser-timeout 60 --sdr
```

不要向 Skill 模板目录写入任务素材、缓存或成片。Windows 下以隐藏窗口运行 CLI、浏览器和 FFmpeg 子进程。渲染后用 FFprobe 验证 1080×1920、30 fps、302 帧、H.264 视频和 AAC 音频，并实际检查第 0、85、86、182、183、301 帧及冲击效果附近帧，确认六层非空文字始终可见、三段素材顺序正确、无补黑或素材缺失。

本次测试成片保存于任务目录的 `renders/yellow-banner-demo.mp4`，不作为 Skill 内置示例分发。交付前应确认实际文件和最终探测结果，不能仅凭模板和脚本存在就报告成片完成。

自然语言使用示例：

```text
使用 $script-to-matrix-video 的“黄条标题·变幅冲击”模板，替换这六层文案，从已审核视频里选三条不同素材，保留原绑定 BGM、302 帧节奏和首尾横屏/中段全屏布局，文字从首帧一直显示到结尾，输出 MP4。
```

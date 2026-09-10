# 三横屏开场·光栅快切

> ⚠️ 本地渲染器文档（主站已退役，2026-09-10）：以下内容仅作离线参考，黄雀主站生产走平台矩阵模板能力，见 SKILL.md 与 legacy-local-renderer.md。

独立模板 ID：`triple-strip-shutter`。仅在用户明确指定这个 ID 或“三横屏开场·光栅快切”时使用。模板源位于 `assets/templates/triple-strip-shutter/`，不加入标准 `catalog.json` 或 `ref-*` 清单；普通模板任务继续使用既有默认入口。

## 固定设计与时序

画面为 1080×1920、30 fps、17.6 秒，共 528 帧。开场三条横向视频带同时显示 3.9 秒，随后使用五个全屏素材槽位和固定光栅快切。帧编号从 0 开始，区间右端不包含在当前段内：

| 段落 | 输出帧区间 | 帧数 | 时长 |
| --- | --- | --- | --- |
| `opening[0..2]` 同时播放 | `[0, 117)` | 117 | 每条 3.9 秒 |
| `main[0]` | `[117, 199)` | 82 | 82/30 秒 |
| `main[1]` | `[199, 281)` | 82 | 82/30 秒 |
| `main[2]` | `[281, 363)` | 82 | 82/30 秒 |
| `main[3]` | `[363, 445)` | 82 | 82/30 秒 |
| `main[4]` | `[445, 528)` | 83 | 83/30 秒 |

切点严格保留在 117、199、281、363、445 帧，528 为结束边界。不要用四舍五入后的秒数累计时长，也不要套用 `ref-*` 的随机时长或标准模板阅读时长公式。

文字使用白色粗斜体、蓝粉错位轮廓和蓝色下划线。四个可替换字段为 `title`（最多 10 字符）、`subtitle`（最多 18 字符）、`ctaLine1` 和 `ctaLine2`（各最多 14 字符）。四层文字从第 0 帧一直显示到第 527 帧，保持完整不透明度，不做文字渐入或提前退场。文字超限时缩短文案并保留原意，不缩小或改动固定模板排版来强塞长文。

复刻边界：关键帧和段落切点精确固定；字体外观、旋转角度及视觉处理属于对本地参考的近似复现，不声称逐像素相同。首帧开始持续显示全部文字是用户对原参考的明确覆盖要求，优先于参考视频中可能存在的延迟出现。

## 输入与素材

先按主 Skill 的现有规则验证素材库连接。任务 JSON 使用顶层四个文字字段、`opening` 三项和 `main` 五项，共八个媒体槽位。素材只能来自用户提供的视频或状态为“可使用”的素材库记录，禁止 AI 生成图片或视频，也不使用图片兜底。

每条素材记录包含本地 `path` 和以秒计的 `source_start`；素材库记录同时保留 `source: "library"`、`status: "可使用"` 和真实 `record_id`。用户直接提供的文件使用 `source: "user"`，不要伪造素材库 ID。相对素材路径以任务 JSON 所在目录为基准。

三条 `opening` 必须是不同原视频。五条 `main` 至少来自三个不同原素材，可复用开场素材；同一个文件改名或更换入点不算不同原素材。每段源文件必须覆盖 `source_start` 加上该槽位所需时长。素材不足时重新选取合格视频或报告缺失，不循环补时、不冻结尾帧，不允许因源片段提前结束产生黑帧。

完整任务示例（将示例路径和记录 ID 换成本机真实已审核记录）：

```json
{
  "title": "输入公司名称",
  "subtitle": "让每一份用心被看见",
  "ctaLine1": "专注品质与服务",
  "ctaLine2": "欢迎留言了解",
  "opening": [
    {"path": "media/a.mp4", "source": "library", "status": "可使用", "record_id": "asset-a", "source_start": 0},
    {"path": "media/b.mp4", "source": "library", "status": "可使用", "record_id": "asset-b", "source_start": 0},
    {"path": "media/c.mp4", "source": "library", "status": "可使用", "record_id": "asset-c", "source_start": 0}
  ],
  "main": [
    {"path": "media/a.mp4", "source": "library", "status": "可使用", "record_id": "asset-a", "source_start": 4},
    {"path": "media/b.mp4", "source": "library", "status": "可使用", "record_id": "asset-b", "source_start": 4},
    {"path": "media/c.mp4", "source": "library", "status": "可使用", "record_id": "asset-c", "source_start": 4},
    {"path": "media/a.mp4", "source": "library", "status": "可使用", "record_id": "asset-a", "source_start": 7},
    {"path": "media/b.mp4", "source": "library", "status": "可使用", "record_id": "asset-b", "source_start": 7}
  ]
}
```

任务不需要 `bgm` 字段。输入也不提供随机时长或帧率覆盖。

## 绑定音乐与本机参考

原参考 BGM 随本机模板保存并固定绑定，具体文件路径和校验值以 `template.json` 为准。准备时校验并原样复制音频，保留已有节奏、起点、速度和音量，不随机选曲、不参加批量音乐轮换，不自动叠加淡入淡出或重新编码。音频缺失或损坏时修复模板资源，不临时换一首歌。

用户明确要求换曲或静音时，作为单独定制处理。该音轨来自用户提供的参考，用户已于 2026-09-10 要求将完整模板及绑定 BGM 同步到公开 GitHub 仓库。该授权说明只记录用户的发布指示，不代替音乐权利证明。Skill 不包含参考视频或客户素材视频，也不保存素材库凭据。迁移模板时连同绑定音频复制，不要求重新寻找原参考视频。

## 准备与出片

在 Skill 目录运行帮助脚本，输出必须使用尚不存在的新任务目录：

```powershell
python scripts/prepare_triple_strip.py --task "D:/video-jobs/triple-strip/task.json" --output "D:/video-jobs/triple-strip/prepared"
```

FFmpeg 或 FFprobe 不在 `PATH` 时，可显式传入 `--ffmpeg <ffmpeg.exe>` 和 `--ffprobe <ffprobe.exe>`。不要向 Skill 模板源目录写入任务素材或渲染结果。

HLG 素材采用本模板已对比确认的 FFmpeg `libplacebo` / BT.2390 转为 Rec.709 SDR，关闭逐帧峰值检测（`peak_detect=0`），不再使用先前偏白的 Mobius 转换。HLG 输入需要 FFmpeg 带 `libplacebo` 且运行环境可用；缺少支持时报错，不静默退回旧算法。SDR 素材不套 HDR tone mapping，其他模板的转换规则不受此次修正影响。转换参数和源色彩信息写入 `provenance.json`；色彩标签正确不代表视觉正常，需对比同入点的画面，确认高光细节与肤色。该转换不声称恢复先前缓存中已丢失的 Dolby Vision 动态元数据。

准备完成后进入生成项目，按该项目 `package.json` 固定的 HyperFrames 版本执行 `check --snapshots --json`，通过后渲染 1080×1920、30 fps 的 H.264/AAC MP4。保持模板 17.6 秒时间线；不得通过尾部黑帧、循环或改变音乐速度凑时长。Windows 下以隐藏窗口运行 CLI、浏览器和 FFmpeg 子进程。

自然语言使用示例：

```text
使用 $script-to-matrix-video 的“三横屏开场·光栅快切”模板，标题“输入公司名称”，副标题“让每一份用心被看见”，底部两行“专注品质与服务”“欢迎留言了解”。从已审核视频中选择素材，保留模板绑定BGM和17.6秒节奏，四层文字从首帧保持到结尾，直接输出MP4。
```

## 验证

检查第 0、116、117、198、199、280、281、362、363、444、445、527 帧，确认三横屏开场、五段素材切换和四层文字持续显示。精确段落边界按上表验收，字体与旋转按视觉近似说明验收；不要将两者混为逐像素复刻。确认输出为 528 帧、17.6 秒、H.264/AAC，绑定音轨非静音且与模板校验值一致，没有循环补片或意外黑帧，并保留实际素材路径、入点和来源记录。

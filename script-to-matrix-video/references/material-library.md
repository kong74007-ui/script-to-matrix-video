# 素材库与素材策略（主站现行）

> 旧版「本地/SSH 素材库 + inspect 自检」流程已随本地渲染器退役，见 `legacy-local-renderer.md`。主站现状：素材全部由渲染服务按策略自动选取，Agent 不挑素材。

## 素材策略 huangque-bookends-pexels-middle-v1

- **头尾（bookends）**：黄雀自有素材库（feishu-video-* 等上传素材，`可使用` 状态）。
- **中间（middle）**：Pexels 视频（`pexels_china_query` 中文检索，如「中国女性聚会」「中国健康生活」），按文案主题词检索；来源含 pexels-video-* 记录（provider_video_id、source_url）。
- 切片：每段 2~3 秒（`/v1/select` 只收 2~3s 的 clip_duration_seconds）；同一任务内素材互不重复。
- 段数：ref 模板 3~5 段；九宫格 9 段 + 3 全屏；FFmpeg 模板按文案时长决定素材个数。

## 素材清单（material_manifest）纪律

- 是渲染服务的**审计清单**（record_id/sha256/media_type/match_level/provider/clip_*），不是给用户的素材来源列表。
- 主站已剥掉第三方署名字段（provider_url/contributor_url）。
- **红线**：绝不把清单里的 pexels/素材来源链接当「成片链接」贴给用户（任务 8007/8010 实录：客户点开看不到自己的成片）。成片只贴 result.video_url。

## 用户自带素材（user_materials）

- 通道尚未开通（2026-09-10 实测 400「不支持的参数」）。主站 bridge 已实现 upload_id→sha256→`/v1/user-assets` 推送、渲染服务也支持 `[{"sha256","media_type"}]`，只等 CLI 目录开放。
- 现状处置：只试一次；被拒降级 ChatCut 剪辑出同款并如实说明（见 SKILL.md §5）。

## BGM

- 无配音：默认开，服务端从素材池选 BGM（`server-bgm-*`）。
- 配音：默认关（voiceover 时 bgm 默认 false）；开则 bgm_volume 默认 0.2（0~1）。
- 九宫格：绑定 BGM（bgm_mode=bound），可关（bgm_optional=true）。

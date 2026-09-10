# 平台对接完整规范（production platform contract）

本文档是「模板成片」平台能力的主站实现规范快照（2026-09-10 线上代码核对），供子 Agent 训练与故障排查。实现代码：主站 `server/content_domains/matrix_template_video.py` + `matrix_template_semantics.py`（dapeng-server `/home/ubuntu/huangque-main-site/`）；渲染服务 `source/api.py`（云端 `/opt/huangque/matrix-template-video/`，代码不在 git）；中转器 `render-relay/relay.py`（dapeng-server）。

## 1. 能力与 schema（hq CLI 目录）

- `matrix-template-templates`：读模板目录（id/name/description/tags/engine/font_mode/font_selectable/variant/duration_mode/required_visuals/required_visuals_max/bgm_mode/bgm_optional/semantic_layout）+ 字体目录（value="" 自动搭配 + bundled/private 字体）。
- `matrix-template-generate` 必填 `top_text(2~60) bottom_text(2~80) template_id`；可选 `font_family(≤80)`、`voiceover`、`user_materials`（目录 schema 未宣传该字段，见 §6）。
- `matrix-template-batch-generate` 同上 + `count(2~5)`。**批量只对非字体锁定模板（full-overlay-bold / poster-split）开放**：ref-01~ref-17 与 nine-grid-reveal（HyperFrames+字体锁定）平台直接拒绝，报「HyperFrames 模板暂仅支持单条生成」；要 N 条只能逐条 generate 且每条文案必须不同（平台按「能力+参数」5 分钟去重，同参数第二次只返回同一 job_id、ok=false 属正常提示），或如实告知一次只能出一条。
- `voiceover = {text(1~120)★, voice(1~128)★, voice_scope(public|personal), speed(0.5~2.0, 0.1 步进)}`；voice 从 voices 的 ready 项复制 voice_key。
- **无 duration 字段**；时长服务端算。第一段调用返回报价（generation:quote），内测期运行时自动确认直出。
- 模板目录回写：子 Agent 拿到的目录条目可能带 `source=cached`（平台目录接口故障时运行时自动用磁盘缓存兜底），照常用、不要反复重试平台接口（2026-09-10 曾因目录结果被截断导致永远只看到 19 个模板、找不到 nine-grid-reveal——已修：matrix-template-templates 后处理用未截断原始 payload 回写，source=platform 且不把 semantic_layout 塞进上下文）。

## 2. 主站校验顺序（validate_payload）

1. 文案归一（连续空白折叠）与长度校验（顶 2~60、底 2~80）。
2. template_id 必须在实时目录里。
3. font_family 只在 font_selectable 模板上校验（2 个 FFmpeg）；ref/nine-grid 忽略。
4. voiceover 走 cosyvoice 校验（音色归属 + 版本指纹）；配音时 bgm 默认 false，开则 bgm_volume 默认 0.2。
5. bgm 布尔；bgm_mode=bound 且 bgm_optional≠true 的模板不可关 BGM（nine-grid bgm_optional=true，可关）。
6. duration 若传：7~15（占位校验，CLI 不传）；duration_mode=fixed_12 时强制 12.0。
7. user_materials（§6）。
8. batch 参数：batch_id 32hex、batch_index/batch_size 1~5。
9. hyperframes 模板必须走语义排版：先 preflight（渲染服务真字体回显校验），再落 payload；preflight 返回的 duration 是权威时长（authoritative_duration）。

## 3. 语义排版（semantic_layout v1）

- 契约：`{version:1, model, source_sha256, top1_end, top_break_after, bottom_break_after}`；`source_sha256 = sha256(top + "\0" + bottom)`（原文改一个字即失效）。
- 生成：gpt-4.1-mini（`MATRIX_TEMPLATE_SEMANTIC_MODEL`）首次；失败/放不下换 gpt-4.1 修复（`_repair_prompt`：先拆完整短语块再换算索引；每块 2~8 字、≤10；`|`/句末标点后必须断；禁拆双字词/地名/行业词/动宾短语/数字组合/英文词）。
- 归一：断点必须是完整语义边界（标点、非数字短语内部、非保护后缀），并自动并入「明显边界」（，。！？；：、,.!?;:|｜ 空格）。
- 校验：渲染服务 `_normalize_reference_semantic_layout` + preflight 真字体排版回显；top1_end 必须是 top1 在自己字号/宽度/行数内排得下的最早安全边界（`_nearest_safe_top1_end`，可回退到更早断点重试 3 个候选）。
- 层结构：top1（开场钩子）/ top2（说明，无 top3 时 4 行）/ top3（补充，部分 variant 有）/ bottom2（行动文案）；每层 font_size_px/font_weight/max_width_px/max_lines 由渲染服务按 variant 从模板 CSS 实测返回（v01~v17 各有合同值）。
- 语义排版失败文案：首提交「AI 断句失败，视频任务未创建且未扣点，请重试」；已冻结重放「AI 断句结果未通过生成校验，视频任务失败并将自动退点」。

## 4. 时长规则（渲染服务 _duration / _reference_duration）

- FFmpeg：`_duration = max(8.0, 可见字符数/5 + 1.5)`（可见字符=中日韩/ASCII 字母数字），上限 15，超出报「文案过长，请缩短标题或行动文案」。
- ref：`_reference_duration = 8 + sha256(job_id:template_id)%8` → 8~15 随机整数，任务内锁定；模板变量声明 duration min=8，引擎 `--strict-variables` 校验（7 秒必失败——2026-09-10 双修复：`_duration` 下限 7→8 + `_reference_duration` 随机段 7+%9 → 8+%8）。
- nine-grid：固定 12.0。
- 配音：主站 cosyvoice 合成 mp3（缓存 24h）→ 成片下载后 ffmpeg 混音（视频流 copy、AAC 192k、时长截到口播实测、bgm 音量衰减）；校验 h264/aac/1080x1920/时长差 ≤0.12s。
- preflight 的 `duration_mode`：fixed_12（nine-grid）/ random_integer_7_15（ref，旧字样，实际 8~15）/ copy_length（FFmpeg）。

## 5. 素材与渲染

- 策略 `huangque-bookends-pexels-middle-v1`：头尾黄雀素材库、中间 pexels（china_query 中文检索）；切片 2~3s（/v1/select 只收 2~3）；ref 3~5 段（required_visuals=3, max=5）、nine-grid 9 段。
- 素材清单（material_manifest）：record_id/sha256/media_type/match_level/provider/clip_*；第三方署名字段 provider_url/contributor_url 主站剥掉；**绝不当成片链接给用户**。
- 渲染引擎：FFmpeg（concurrency 5）、HyperFrames（并发 2，slot 600s、总 900s）；nine-grid 用 0.8.33、ref 用 0.8.16。
- 黑屏检测：成片持续黑屏 → 失败「模板成片存在持续黑屏」。
- 成片统一 1080x1920、30fps、H.264/AAC。

## 6. user_materials 通道（截至 2026-09-10：未开通）

- 主站 bridge 已实现：`_normalize_user_materials`（1~20 条、media_type image|video、upload_id 或 sha256）→ `resolve_user_materials` 把 upload_id 读成字节、算 sha256、`upload_user_asset` 推到渲染服务 `/v1/user-assets`（X-HQ-Asset-Sha256 头）→ payload 用 `{sha256, media_type, clip_start_seconds?}` 提交。
- 渲染服务 `_user_materials` 支持 `[{"sha256":"<64hex>","media_type":"image"|"video"}]` 并透传挑选/渲染。
- 但 hq CLI 提交层目前**拒收 user_materials**（400「不支持的参数」）——目录 schema 未宣传该字段。**只试一次**，被拒降级 ChatCut 剪辑出同款并如实说明。

## 7. 渲染链路（中转器 pull 协议）

- 主站 `MATRIX_TEMPLATE_API_URL=https://huangquechuanmei.com/render-relay`（content.env）。
- 中转器（render-relay，dapeng-server 8213/nginx）：
  - 黄雀侧（RELAY_API_TOKEN）：POST /v1/jobs 入队（202 + job_id）；GET /v1/jobs/<id> 状态；GET /v1/files/<id>.mp4 从 COS 流式取回；GET /health 转发上游 health 并回显 templates 数（落在 {2,15,19,20} 才算 ok，否则主站判整条渠道未就绪）；/v1/templates、/v1/preflight、/v1/user-assets 直接转发上游（云端渲染服务）。
  - 节点侧（NODE_TOKEN）：POST /v1/claim 认领（支持 RELAY_PRIORITY_NODES 优先级，高优先级节点最近 20s 内来过就让位）；POST /v1/report {ok,result|error} 或 /v1/result/<id>（原始字节，中转器落盘 + 传 COS `huangque/render/<id>.mp4`）。
  - 失联回收：claimed 超 CLAIM_TIMEOUT(2400s) 回 pending。
- 节点（tang/yuelei，办公室 GPU 机）跑同一份渲染服务 api.py（8212），本地渲染后回传；生产渲染不再在云端执行（云端只当目录/预检上游）。
- 健康口径：health.ok && templates∈{2,15,19,20}；material_library_ready / pexels_material_ready 标志。

## 8. 主站任务生命周期（jobs.db kind=matrix_template_video）

- payload 冻结语义排版与字体出身；`_matrix_runtime` 记录 phase（queued/submitting/provider_queued/rendering/delivering/muxing_voiceover/synthesizing_voiceover）、provider_job_id、deadline_at、last_progress_at。
- 恢复：provider 已提交则按 provider_job_id 续查；提交态网络错误（400/401/403/404/422 外）置 submission_unknown 重放；provider 终态 failed 且为权威失败 → MatrixTemplateProviderFailed → 任务失败。
- 超时：TOTAL_TIMEOUT 默认 1200s、JOB_TIMEOUT 默认 1200s、POLL_INTERVAL 3s。
- 成品：下载到主站 OUT_DIR `video/matrix_template_<job_id>.mp4`，`video_url=public_url(..., private=True)`（相对 `/api/v4/render/...`）；响应含 type/mode/provider/provider_task_id/status/duration/width/height/template_id/font_selection/font_files/file_size/material_manifest（剥署名）/voiceover（若有）。

## 9. 失败类与账务

- 报价：pricing `video.matrix_template`（内测期运行时自动确认、不实际扣点）。
- 失败类：Variable validation failed（已修）、持续黑屏、Pexels 素材文件读取失败（云端网络问题，2026-09-10 晚起云端连不上 pexels；生产节点不受影响）、HTTP 400（参数）、超时。
- 生成失败的任务平台按规则退点（内测期无实际扣费）；Agent 不得代平台承诺赔付，如实转述错误。

## 10. 关键配置环境变量（仅排查用，勿泄露）

主站：`MATRIX_TEMPLATE_API_URL`（=render-relay）、`MATRIX_TEMPLATE_API_TOKEN`、`MATRIX_TEMPLATE_SEMANTIC_MODEL`（默认 gpt-4.1-mini）、`MATRIX_TEMPLATE_SEMANTIC_REPAIR_MODEL`（默认 gpt-4.1）。
渲染服务：`MATRIX_TEMPLATE_DATA_ROOT`、`MATRIX_TEMPLATE_SKILL_ROOT`（FFmpeg 目录源）、`MATRIX_TEMPLATE_REFERENCE_SKILL_ROOT`（ref 包源）、`MATRIX_TEMPLATE_NINE_GRID_ROOT`、`PEXELS_API_KEY`、`MATRIX_TEMPLATE_HYPERFRAMES_*`、`MATRIX_TEMPLATE_CONCURRENCY`。
中转器：`RELAY_UPSTREAM`（云端渲染服务地址）、`RELAY_UPSTREAM_TOKEN`、`RELAY_API_TOKEN`（主站侧）、`RELAY_NODE_TOKEN`（节点侧）、`RELAY_PRIORITY_NODES`、`RELAY_CLAIM_TIMEOUT`、COS 系。

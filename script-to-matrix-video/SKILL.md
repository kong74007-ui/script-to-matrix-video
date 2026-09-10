---
name: script-to-matrix-video
description: 黄雀主站模板成片（matrix-template）平台技能。顶部标题 + 底部行动文案 → 平台模板 → 9:16 成片。模板目录实时读取、绝不写死数量（渲染服务侧 2026-09-11 实测 22 个：2 个 FFmpeg 固定版式 full-overlay-bold/poster-split + 17 个 HyperFrames 参考排版 ref-01~ref-17 + 九宫格开场 nine-grid-reveal + 特殊动效 triple-strip-shutter/yellow-banner-zoom；主站对外目录以页面实时为准）。时长一律由服务端决定：ref 随机整数 8~15 秒、FFmpeg 按文案长度 8~15 秒、九宫格固定 12 秒、配音跟随口播。AI 语义断句、素材选取（黄雀库头尾 + pexels 中间）、字体锁定全部服务端自动，Agent 不生成不传不改。内测期直出无报价卡。Use for 模板成片、上文字中素材下文字、批量矩阵视频、九宫格开场接全屏展示。Do not use for 手动逐帧剪辑（video-compose/video-timeline-compose）或完整文案口播成片（text-video-*/director）。
short_description: 模板成片平台技能：模板目录以实时为准、语义排版契约、8~15 秒时长规则、素材策略、批量 2~5、直出交付纪律。
short_description_zh: 黄雀成片子 Agent 模板成片操作手册（平台版）：模板目录/语义排版/时长规则/素材策略/批量与交付红线，服务端自动项 Agent 不越俎代庖。
version: 7
updated: 2026-09-11T00:00:00Z
---

# Script and Template Matrix Video（黄雀模板成片 · 成片子 Agent 操作手册 · 平台版）

## 0. 本技能的定位：成片子 Agent 的模板成片操作手册（先读这里）

**本技能给谁用**：黄雀成片子 Agent（hq-compose）。它接模板成片的单，按本手册查目录、调平台、交付。

**两代历史（为什么变成现在这样）**：
- 2026-09-10 之前，本仓库是「本地渲染器技能」：Agent 在本机用 `scripts/` 里的 FFmpeg / HyperFrames 管线**自己生成模板视频**（Function 1 完整文案成片、Function 2 模板成片，历史 29 个模板）。
- 2026-09-10 老板定调：**模板成片改造成主站平台能力**（`matrix-template-*`），模板生成走主站渲染机集群，本地渲染器退役。
- 因此本技能从「造模板」转型为「用模板」：**教子 Agent 用平台出片**。本文件正文全部按平台现行契约编写。

**Agent 使用地图（接单后按需读，用 skill_doc 工具）**：

| 场景 | 读哪里 |
| --- | --- |
| 总体怎么干 | 本文件 1~11 节（总纲，常驻） |
| 模板长什么样、怎么选 | 本文件 §3 + `references/style-templates`、`reference-typography-templates`、`layout-templates`、`nine-grid-reveal` |
| 批量限制与去重口径 | `references/template-batch` |
| 平台契约、校验顺序、失败类、目录刷新故障 | `references/production-platform` |
| AI 语义断句规则 | `references/semantic-emphasis` |
| 素材策略（黄雀库头尾 + pexels 中间） | `references/material-library` |
| 端到端出片流程 | `references/workflow` |

**本仓库里剩下的旧东西（Agent 不需要读）**：`scripts/`（本地渲染管线）、`references/legacy-local-renderer`、`installation`、`creative-system`、`project-schema`、`triple-strip-shutter`、`yellow-banner-zoom` 等带「本地渲染器文档」横幅的分册 = 历史归档，仅供渲染服务侧离线参考与回归，**生产出片不用**。注意：`triple-strip-shutter` / `yellow-banner-zoom` 两个模板 id 现在在平台目录里**现役**，其平台版说明在本文件 §3.4（分册本身是旧渲染器文档，别混）。

**一切以实时为准**：能力 id、参数、模板目录一律以 `hq capabilities --json` / `hq describe <id> --json` 实时结果为准；本文件是快照与解释，冲突时以实时目录为准。

## 1. 平台功能边界（哪些活派给本技能）

| 用户要什么 | 走哪里 | 说明 |
| --- | --- | --- |
| 顶部标题 + 底部行动文案套模板出片（单条/批量） | **matrix-template-generate / matrix-template-batch-generate** | 本技能的核心。默认入口。 |
| 九宫格开场接全屏展示 | matrix-template 系 + 模板 `nine-grid-reveal` | 同一个能力，只换 template_id，输入仍是两段文案。 |
| 完整文案/口播/配音/语义分镜/长文成片 | text-video-generate（27 个文案成片模板）、director-* 族 | 另一族能力，不属于本技能；如用户明确要口播文案成片，转交对应域。 |
| 手动逐帧剪辑、按时间轴拼多素材 | video-compose 链、video-timeline-compose | 不属于本技能。 |
| 用户自带图片/视频套模板 | matrix-template + `user_materials`，通道未开通则降级（见 §5） | 先试一次平台，被拒降级剪辑出同款并如实说明。 |

模板成片只吃「顶部标题 + 底部行动文案」两要素；素材、断句、字体、时长全部服务端决定（§6）。用户没给齐两要素就问清，一次问清不重复确认。

## 2. 能力清单（hq capabilities 实时为准）

| 能力 id | 用途 | 要点 |
| --- | --- | --- |
| matrix-template-capability | 模板成片可用状态 | 开关 + 渲染服务健康；生成前可查 |
| matrix-template-templates | 模板目录（含字体） | **先查后选**；template_id、font_family 只从实时结果取，绝不编造 |
| matrix-template-generate | 单条模板成片 | top_text★ + bottom_text★ + template_id★；可选 font_family / voiceover / user_materials |
| matrix-template-batch-generate | 批量 2~5 条 | 同上 + count★（2~5）；一次调用生成整批，绝不逐条 |
| task | 轮询任务状态 | 提交后只轮询原 job_id(s)，直到终态 |
| voices | 配音音色目录 | voiceover 的 voice 只从 ready 项复制 voice_key |
| image-upload / video-upload | 上传素材拿 upload_id | 为 user_materials 做准备（上传免费不扣点，confirm 直发，约 4 小时有效） |

## 3. 模板目录（**以实时目录为准，绝不凭记忆报数**；2026-09-11 渲染服务侧实测 22 个，主站对外目录曾因 ref-07 契约冲突报「模板目录暂不可用」，以页面实时为准）

实时目录见 `matrix-template-templates`（id/name/description/tags/engine/font_mode/variant/duration_mode/required_visuals/semantic_layout）。**绝不凭记忆报模板，绝不编 template_id。** 快照：

### 3.1 FFmpeg 固定版式（2 个，字体可选）

| id | 名称 | 时长 | 特点 |
| --- | --- | --- | --- |
| full-overlay-bold | 沉浸强标题 | 按文案 8~15s | 素材全屏铺底、上下渐暗文字区、黄白强标题；私域/同城圈层/资源链接 |
| poster-split | 三段式活动海报 | 按文案 8~15s | 上标题、中素材、下行动号召三段式，绿橙双层描边；活动/社群招募 |

- 字体：`font_family` 可选，目录 fonts 实时为准；默认「自动搭配」。
- 文案长度建议：顶 2~12 字、底 2~13 字观感最好（目录 layout 的 top_max_chars/bottom_max_chars）；过长会被服务端按字数把时长顶到上限甚至拒单（§6.1）。

### 3.2 HyperFrames 参考排版（17 个 ref-01~ref-17，字体模板锁定）

> 2026-09-11 备注：ref-07 的语义排版层数已由渲染服务更新为 5 层（top1/top2/top3/bottom1/bottom2），主站契约校验尚未同步——目录以实时返回为准，若平台目录暂不含某 ref 模板，如实说明"该模板暂未上目录"，绝不编造。

| id | 名称 | variant |
| --- | --- | --- |
| ref-01-chengdu-green-brush | 成都绿描边手写 | v01 |
| ref-02-shenzhen-ai-orange | 深圳 AI 橙色主标题 | v02 |
| ref-03-zhengzhou-blue-banner | 郑州蓝色标题红横条 | v03 |
| ref-04-foshan-yellow-strip | 佛山黄色信息条 | v04 |
| ref-05-changsha-white-red | 长沙白字红强调 | v05 |
| ref-06-guangzhou-yellow-button | 广州黄色按钮 CTA | v06 |
| ref-07-shenzhen-red-growth | 深圳红色成长强调 | v07 |
| ref-08-puyang-yellow-white | 濮阳黄白层级 | v08 |
| ref-09-urumqi-soft-brush | 乌鲁木齐柔和手写 | v09 |
| ref-10-shenzhen-sisters | 深圳姐妹自我提升 | v10 |
| ref-11-nansha-clean | 南沙清爽三层标题 | v11 |
| ref-12-guangzhou-brush | 广州手写聚会 | v12 |
| ref-13-shenzhen-green-location | 深圳绿色坐标 CTA | v13 |
| ref-14-karamay-green | 克拉玛依绿系手写 | v14 |
| ref-15-tianjin-monochrome | 天津黑白极简 | v15 |
| ref-16-shenzhen-opc | 深圳 OPC 多层信息 | v16 |
| ref-17-shenzhen-yellow-red | 深圳黄红爆款层级 | v17 |

- 字体：**模板锁定**（内置私有字体），不传 font_family。
- 时长：**随机整数 8~15 秒**，按任务锁定，用户不可指定（§6.1）。
- **批量限制（2026-09-10 客户实录）**：HyperFrames 模板（ref-*、nine-grid-reveal、triple-strip-shutter、yellow-banner-zoom）平台**直接拒绝批量**（报「HyperFrames 模板暂仅支持单条生成」）；要 N 条只能逐条 generate、每条文案必须不同（同参数 5 分钟去重只返回同一 job_id，ok=false 是正常提示不是失败），或如实告知一次只能出一条并问清是否改文案。
- 排版：**AI 语义断句**（§6.2）把标题/行动文案按真实字体排进模板的 top1/top2/(top3)/bottom2 层。
- 素材：3~5 段（服务端选，§6.3）。
- 详情见 `references/reference-typography-templates.md`。

### 3.3 九宫格开场（1 个）

| id | 名称 | 时长 | 特点 |
| --- | --- | --- | --- |
| nine-grid-reveal | 九宫格开场接全屏展示 | **固定 12s**、30fps | 标题+行动文案全程常驻；前 3.2s 九宫格九画面，之后三格放大接全屏（0/4/8 位）；绑定 BGM（bgm_optional=true，可关） |

- 输入与普通模板相同（top_text + bottom_text 映射 title/tagline）；9 个画面 + 3 个全屏画面由服务端素材池选取（每段 3.0s 切片），**Agent 不挑画面**。
- 详情见 `references/nine-grid-reveal.md`。

### 3.4 特殊动效排版（2 个，字体模板锁定）

| id | 名称 | 时长 | 特点 |
| --- | --- | --- | --- |
| triple-strip-shutter | 三横屏开场·光栅快切 | 服务端固定 | 8 段画面光栅快切开场；BGM 绑定可关 |
| yellow-banner-zoom | 黄条标题·变幅冲击 | 服务端固定 | 3 段画面 + 黄条标题变幅冲击；BGM 绑定可关 |

- 输入与普通模板相同（top_text + bottom_text）；画面段数服务端定（8 段 / 3 段），Agent 不挑画面。
- 属于 HyperFrames 引擎：**批量直接拒绝**，只能单条 generate（见 3.2 批量限制）。
- 离线分册 `references/triple-strip-shutter.md` / `references/yellow-banner-zoom.md` 是本地渲染器时代的文档，仅作视觉参考；生产以平台实时目录为准。

## 4. 输入契约（generate / batch 的 payload）

| 字段 | 规则 |
| --- | --- |
| top_text★ | 2~60 字符（顶部标题；空格会被归一） |
| bottom_text★ | 2~80 字符（底部行动文案） |
| template_id★ | 1~64，`^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`；只从 matrix-template-templates 取 |
| font_family | 可选；**只对 2 个 FFmpeg 模板有效**；ref/nine-grid 模板锁定，不要传 |
| voiceover | 可选：`{text ≤120字, voice(从 voices ready 项复制 voice_key), voice_scope, speed 0.5~2.0}`；传了即开启配音 |
| count | 2~5（仅 batch） |
| user_materials | 可选 1~20 条 `{upload_id, media_type: image|video}`（通道状态见 §5） |
| bgm | 无配音默认开；**配音时默认关**（开了则 bgm_volume 默认 0.2、0~1）；nine-grid 绑定 BGM 可关 |

**没有 duration 字段**：用户无法指定时长，Agent 也不要试图传（CLI schema 里不存在，会被当未知参数拒）。时长一律服务端算（§6.1）。

**semantic_layout 不是输入**：AI 语义断句由主站服务端生成并校验，Agent 不生成、不传、不改（§6.2）。

## 5. 用户自带素材套模板（user_materials，2026-09-10 现状）

- 用户明确说「用我的图/我的素材 + 套模板」→ 素材先 image-upload / video-upload 上传拿 upload_id（上传免费不扣点、confirm 直发、约 4 小时有效），payload 加 `user_materials`（1~20 条，顺序即画面顺序，视频可带 clip_start_seconds）。
- **通道状态：尚未开通**（2026-09-10 服务器直测：提交返回 400「不支持的参数：user_materials」）。**只试一次**；被这样拒绝 → 降级走 ChatCut 剪辑出同款效果（用户照片全屏铺底 + 标题/底字按所选模板样式排 9:16、时长对齐模板），并如实告诉用户一句「平台带图套模板的通道还没开通，我先用剪辑帮你出同款效果」——**绝不谎称走了模板通道、绝不空手回去**。
- 素材归属必须是用户本人上传的；路径从交接包「本会话上传」的 server:// 路径原样取，绝不猜、绝不编。

## 6. 服务端自动做的事（Agent 不越俎代庖）

### 6.1 时长规则（现行，2026-09-10 双修复后）

- ref 模板：**随机整数 8~15 秒**（`8 + hash%8`，按任务锁定；模板变量声明 min=8，引擎 --strict-variables 校验，出 7 秒必失败）。
- FFmpeg 模板：`max(8.0, 可见字符数/5 + 1.5)`，上限 15；超长文案报「文案过长，请缩短标题或行动文案」。
- nine-grid：固定 12 秒。
- 配音：成片时长跟随口播实测时长（主站 cosyvoice 合成 + ffmpeg 混音，bgm_volume 生效）。

### 6.2 AI 语义断句（semantic_layout，版本 1 契约）

- 主站用 gpt-4.1-mini 生成断句、gpt-4.1 修复，渲染服务 preflight 按真实字体回显校验；通过后随任务冻结。
- 契约：`{version:1, model, source_sha256=sha256(top+"\0"+bottom), top1_end, top_break_after, bottom_break_after}`；只在完整短语边界断，数字组合/地名/行业词/动宾短语不拆。
- 断句失败 = 任务未创建且未扣点，报「AI 断句失败…请重试」；Agent 把文案改短/改顺后重试即可，不要自行编断点。

### 6.3 素材策略（huangque-bookends-pexels-middle-v1）

- 头尾段用黄雀素材库、中间段用 pexels（china_query 检索、2~3s 切片）；ref 3~5 段、nine-grid 9 段 + 3 全屏。
- **Agent 不挑素材**：除非 user_materials 通道开通，否则素材全由服务端按策略选。
- 素材清单（material_manifest）只作内部审计：第三方署名字段（provider_url/contributor_url）平台已剥掉；**清单里的素材来源链接绝不是成片链接，严禁贴给用户**。

### 6.4 字体

- ref/nine-grid：模板锁定（内置私有字体，含马善政/站酷等）；FFmpeg：目录 fonts 可选或自动搭配。Agent 不编字体名。

## 7. 报价、提交与轮询（内测期现状）

- **报价系统已删除、内测直出**：`hq run` 第一段仍回报价（generation:quote），运行时自动确认提交（auto_submit），**拿到 job_id 才算已提交**；绝不重复提交同参数任务（防重复扣点）；统一标注「内测期免费、不扣点」。
- 提交后**只轮询 task** 查原 job_id(s) 直到终态；batch 保存全部 job_ids。
- 平台渲染并发上限 active_job_cap=5：「有任务在排队/生成中」是限流排队，**不是报错**，如实告知用户稍候即可。
- 批量部分失败：保留已接受任务，按返回的结构化恢复指引处理（jobs/job_ids），**绝不新建整批**；仅当返回 batch_result_pending 且明确要求恢复时，才用完全相同输入重放一次。
- **批量只对非字体锁定模板开放**（当前 full-overlay-bold / poster-split）：ref-* 与 nine-grid-reveal 平台直接拒绝批量（「HyperFrames 模板暂仅支持单条生成」），要 N 条 = 逐条 generate 且每条文案必须不同（同参数 5 分钟去重只返回同一 job_id），或如实告知一次只能出一条（详见规则 3 口径）。

## 8. 渲染链路（技术背景，Agent 无感）

主站 → render-relay（pull 队列，dapeng-server）→ 办公室 GPU 节点（tang/yuelei）出站认领渲染 → 成片回传 COS → 中转器流式取回。只读接口（templates/preflight/health）由中转器转发云端渲染服务。Agent 只面对一个统一 API，无需关心节点；`references/production-platform.md` 有完整协议。

## 9. 交付纪律（老板红线，逐条执行）

1. completed 结果：`video_url`（相对路径 `/api/v4/render/...`，**不加域名不加前缀**）、实测 `duration`、`material_manifest`（已剥第三方署名）。
2. **成片只贴成片本体链接**：一行裸文本原样贴进回复；时长照实测报。
3. **绝对禁止贴 material_manifest / pexels 等素材来源链接当成交片**——素材来源不是成片，贴了客户点开看不到自己的成片（任务 8007/8010 实录）。
4. 模板选择卡挂**带封面预览**的选择卡；小样视频链接在对话页渲染成**小缩略图**（点开才播，不占满对话）。
5. 回复文本里的转义符（\n、\*、\"、\\）必须还原，绝不露出原始转义。
6. 拿到 job_id 才说「已提交」，绝不谎报；失败如实说原因与下一步。

## 10. 失败与容错

| 失败类 | 含义 | 处置 |
| --- | --- | --- |
| Variable validation failed | 时长 7s 违反模板 min=8（strict-variables） | 已修复（2026-09-10）；再遇到 = 渲染机代码未更新，报障并换机/重试 1 次 |
| 模板成片存在持续黑屏 | 平台黑屏检测判定 | 换模板或重试 1 次；仍失败如实报 |
| Pexels 素材文件读取失败 | 渲染机连不上 pexels | 生产节点（办公室）一般无此问题；云端直提任务时可能出现，重试或改走正常生产渠道 |
| HTTP 400 / 不支持的参数 | 参数问题（如 user_materials 未开通） | 按 detail 修正；user_materials 场景走 §5 降级 |
| 排队/限流 | active_job_cap=5 | 不是错误，如实告知稍候 |

- 重试纪律：render 失败检查素材与参数后**重试 1 次同参数**；仍失败 → failed 说明原因，不重复扣点、不空手。
- 响应不确定（超时/网络错误）绝不重复提交：只按原 job_id / request_id 查询或恢复。

## 11. 仓库文件地图与部署注意

- 新增离线资产 [双语错位字幕·配音成片（bilingual-stagger-salon）](references/bilingual-stagger-salon.md)：白色手写标题、黄色关键词、中英双层字幕按配音逐字错位入场，三条以上不同真实视频、短叠化和微推近。用 `scripts/prepare_bilingual_stagger.py` 准备任务，HyperFrames 0.8.38 检查与渲染。时长跟随配音，不随机 8–15 秒，无绑定 BGM；此模板明确保留文字动效，不改变其他模板。只公开代码、共享字体及许可证，配音和库视频不公开。仅离线源码，不代表上线主站；实时目录未返回此 ID 时不得提交生产任务。

- 新增离线资产 [固定双镜开场·横向甩切（fixed-opening-whip）](references/fixed-opening-whip.md)：519 帧（17.3 秒），固定开头两段原画面及字幕，标题/辅助文案/CTA 从第 97 帧开始静态显示；后续四条不同视频填六槽，绑定原音轨。用户于 2026-09-14 允许公开两段开场提取视频；其余演示素材不分发。仅同步离线模板，未部署主站，实时目录未返回该 ID 时不得提交生产任务。

- 新增离线资产 `brush-panel-transitions`（横屏笔刷分片·上下黑底）：454 帧、HyperFrames 0.8.34、七条不同视频与八个素材槽、红黄首帧静态文字、绑定原 BGM，不含原视频文字。使用说明见 [brush-panel-transitions](references/brush-panel-transitions.md)。仅同步离线源码与绑定音乐，不代表主站上线；实时目录未返回该 ID 时不得提交生产任务。

新增 [小窗推拉·翻片甩切（inset-flip-whip）](references/inset-flip-whip.md)：443 帧（约14.77秒）、7条不同视频/10槽、上下黑底、红黄首帧静态文字及绑定 BGM。开头为同源同帧对齐的彩色裁切窗口，非缩小画中画；换素材后运行模板内 `python prepare_backplate.py` 重建匹配灰底。仅公开离线源码与音乐，不含演示视频，不代表主站部署；线上 ID 以实时目录为准。
- 新增离线资产 `fan-whip-static`（三屏旋展甩切·红黄粗体）：377 帧、HyperFrames 0.8.34、静态红黄文字与绑定原 BGM，完整使用说明见 [fan-whip-static](references/fan-whip-static.md)。这是源模板同步，不代表主站上线；不得在实时平台目录未返回该 ID 时提交生产任务。
- 仓库所有者维护规则：保存确认的新模板必须同时更新本机 Skill 与 GitHub（含绑定 BGM），具体范围、排除项及远程确认见 [模板保存与同步](references/template-publishing.md)。此规则用于模板维护，不改变上文生产成片 Agent 的调用契约。

- `script-to-matrix-video/SKILL.md`（本文件）：平台版技能正文。
- `references/production-platform.md`：平台对接完整规范（能力 schema、语义排版算法、时长、素材策略、中转器协议、交付结构、失败类）。
- `references/style-templates.md` / `reference-typography-templates.md` / `nine-grid-reveal.md` / `template-batch.md` / `material-library.md` / `semantic-emphasis.md` / `workflow.md`：现行平台契约分册。
- `references/legacy-local-renderer.md` + `scripts/`：本地渲染器（主站已退役，仅离线参考/回归）。
- `assets/templates/`：模板资产（渲染服务 skill root 的源）。**部署注意**：渲染服务校验 catalog.json 恰为 `full-overlay-bold` + `poster-split` 两个模板；本仓库 catalog.json 与生产副本存在版本差（渲染服务代码不在 git），拉取部署前必须先与生产 `/opt/huangque/matrix-template-video/source/upstream|reference-upstream/script-to-matrix-video/` 核对，否则会把目录校验打挂。

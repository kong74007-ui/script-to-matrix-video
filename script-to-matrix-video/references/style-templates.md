# 模板目录（主站现行，2026-09-10）

> 本页是平台版模板目录快照。**实时目录以 `matrix-template-templates` 为准**，template_id 只从实时结果取，绝不编造。本仓库离线资产现保留 24 个模板（18 ref + 6 动效），原 8 个标准 FFmpeg 预设已删除。**2026-09-11 渲染服务侧实测 22 个模板：2 FFmpeg + 17 ref + nine-grid + triple-strip + yellow-banner**；主站对外目录因单个模板契约校验失败（ref-07）暂不可刷新、报「模板目录暂不可用」，用户可见模板数以主站页面实时为准（见 production-platform.md 的「目录刷新失败」）。两代区别见 `legacy-local-renderer.md`。

渲染服务侧现行共 **22 个模板**（2026-09-11 实测）：2 个 FFmpeg 固定版式 + 17 个 HyperFrames 参考排版（ref-01~ref-17）+ 1 个九宫格开场 + 2 个特殊动效（triple-strip-shutter / yellow-banner-zoom）。**数量以实时目录为准，不要记写死的数字。**

## FFmpeg 固定版式（字体可选）

### 仓库新增离线资产（不是线上目录项）

2026-09-11 新增 [brush-panel-transitions · 横屏笔刷分片·上下黑底](brush-panel-transitions.md)：454 帧（约 15.13 秒）、七条不同视频/八个槽、红黄首帧静态文字、绑定原 BGM，采用 HyperFrames 0.8.34；不含参考原文字。仓库当前离线资产为 **24 个（18 ref + 6 动效）**，本机另有 ref-19。仅同步源码，不代表已部署；线上调用仍以实时目录为准。

新增 [小窗推拉·翻片甩切（inset-flip-whip）](inset-flip-whip.md)：443 帧（约14.77秒）、7条不同视频/10槽、上下黑底、红黄首帧静态文字及绑定 BGM。开头为同源同帧对齐的彩色裁切窗口，非缩小画中画；换素材后运行模板内 `python prepare_backplate.py` 重建匹配灰底。仅公开离线源码与音乐，不含演示视频，不代表主站部署；线上 ID 以实时目录为准。

2026-09-11 新增 [fan-whip-static · 三屏旋展甩切·红黄粗体](fan-whip-static.md)：377 帧（约 12.57 秒）、五条不同视频、静态红黄文字、绑定原 BGM，采用 HyperFrames 0.8.34。当时仓库离线资产为 **22 个（18 ref + 4 动效）**；本机另有 ref-19，因此本机计数可不同。线上数量仍必须读实时目录。保存/上传源码不代表已部署到服务端。

模板维护者保存新模板时执行 [本机与 GitHub 同步规则](template-publishing.md)。

| id | 名称 | 时长 | 文案建议 | 特点 |
| --- | --- | --- | --- | --- |
| full-overlay-bold | 沉浸强标题 | 按文案 8~15s | 顶 ≤12 字/≤4 行，底 ≤12 字/≤3 行 | 素材全屏铺底、上下渐暗文字区、黄白强标题；私域/同城圈层/资源链接 |
| poster-split | 三段式活动海报 | 按文案 8~15s | 顶 ≤12 字/≤4 行，底 ≤13 字/≤3 行 | 上标题、中素材、下 CTA 三段式，绿橙双层描边；活动/社群招募 |

- 字体 `font_family` 可选（目录 fonts 实时为准：value="" 自动搭配 + bundled/private 字体）；默认自动搭配。
- 关键词强调由服务端按目录 emphasis_profiles 处理（黄字/描边/放大），Agent 不指定（见 `semantic-emphasis.md`）。

## HyperFrames 参考排版（17 个，字体模板锁定）

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

- 时长：随机整数 8~15 秒，任务内锁定，不可指定；字体模板锁定，不传 font_family；AI 语义断句排版；素材 3~5 段。详见 `reference-typography-templates.md`。

## 九宫格开场（1 个）

| id | 名称 | 时长 | 特点 |
| --- | --- | --- | --- |
| nine-grid-reveal | 九宫格开场接全屏展示 | 固定 12s、30fps | 标题+CTA 全程常驻；九宫格九画面 3.2s 后三格放大接全屏；绑定 BGM 可关 |

详见 `nine-grid-reveal.md`。

## 目录里的其余字段（Agent 需知道的）

- `engine`：ffmpeg / hyperframes。
- `font_mode`：selectable（可选字体）/ template_locked（模板锁定）。
- `variant`：FFmpeg=布局变体名；ref=v01~v17；九宫格=nine-grid。
- `duration_mode`：copy_length（FFmpeg）/ random_integer_7_15（ref 旧字样，实际 8~15）/ fixed_12（九宫格）。
- `required_visuals` / `required_visuals_max`：素材段数（ref=3/5，九宫格=9/9）。
- `bgm_mode` / `bgm_optional`：bound=绑定 BGM；九宫格 bound+可关。
- `semantic_layout`：模板 AI 断句层合同（v01~v17 各层字号/宽度/行数），服务端用它做断句校验——Agent 只读不传。

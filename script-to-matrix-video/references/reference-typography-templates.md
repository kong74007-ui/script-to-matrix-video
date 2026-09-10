# 参考排版模板（ref-01 ~ ref-17，主站现行）

17 套 HyperFrames 参考排版模板（variant v01~v17，引擎 hyperframes 0.8.16，1080x1920@30）。字体模板锁定（内置私有字体，含马善政/站酷快乐体/站酷小薇体等），标题与行动文案由 **AI 语义断句** 按各 variant 的真实字体层合同排版（top1 开场钩子 / top2 说明 / top3 补充（部分 variant）/ bottom2 行动文案）。id/名称对应关系见 `style-templates.md`。

## 输入输出契约

- 输入：top_text（2~60）、bottom_text（2~80）；**不传 font_family、不传 duration**。
- 时长：**随机整数 8~15 秒**（`8 + sha256(job_id:template_id)%8`），任务内锁定并写入变量；模板变量声明 duration min=8，引擎 `--strict-variables` 校验——任何 7 秒时长都会报「Variable validation failed」（2026-09-10 已修复随机段，历史失败全部来自旧算法）。
- 素材：3~5 段（required_visuals=3, max=5），策略 huangque-bookends-pexels-middle-v1（头尾黄雀库 + 中间 pexels），每段 2~3 秒切片，服务端选取。
- 排版：语义断句结果由服务端生成并真字体校验，随任务冻结；Agent 不生成不传不改。

## 语义断句层合同（semantic_layout v1）

每个 variant 的层合同（font_size_px / font_weight / max_width_px / max_lines）由渲染服务从模板 CSS 实测返回，主站 `_SEMANTIC_CONTRACTS` 有等值快照。结构：

- top1：开场钩子（多数 variant 2 行，字号 70~118px）
- top2：具体说明（无 top3 的 variant 4 行，有 top3 的 2 行，字号 50~104px）
- top3：补充说明（v01/v04/v05/v06/v07/v08/v10/v11/v12/v16/v17 有；2 行）
- bottom2：行动文案（2 行，字号 58~92px）

断点规则（服务端执行）：只在完整短语边界断；禁止拆数字组合、地名、行业词、多层名词短语、动宾短语、列举项、短 CTA；明显边界（标点/空格）自动并入；top1_end 必须取 top1 能独立排下的最早安全边界。

## 动效（服务端按任务种子生成，Agent 不指定）

- 编辑计划 v2（editing_plan）：每段一个 motion（pan_left/pull_back/tilt/slow_push/pan_right 等）、bookends（entrance/exit，如 slide_left/circle_close）、段间 transition（whip_left/cube_flip/zoom_swap 等）、禁止的 color_effects 列表（老电影/褪色类，模板走现代干净路线）。
- 片头片尾各约 0.5s 黑场由模板自身处理；文字从首帧全显，不做文字淡入。

## 与小样/示例的关系

仓库 `assets/examples/text-media-text/reference-typography-17/` 下 18 个 jpg/mp4 是本地渲染器时代的示例（含 18-beauty-private-domain，生产目录为 17 套），只作视觉参考，不作为模板目录依据；生产以 `matrix-template-templates` 实时返回为准。

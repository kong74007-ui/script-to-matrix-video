# 本地渲染器（legacy local renderer，主站已退役）

2026-09-10 老板定调：模板成片直接派平台（matrix-template-* 能力），本仓库的本地渲染管线在主站退役。以下内容仅作离线参考、模板资产回归与外部环境自渲染用途，**不再用于黄雀主站生产**。

## 退役范围

- `scripts/`：render_video.py（text-media-text FFmpeg 渲染器）、render_reference_typography.py（ref 包 HyperFrames 渲染）、prepare_nine_grid.py / prepare_triple_strip.py / prepare_yellow_banner.py（动效模板准备）、material_library.py（本地/SSH 素材库）、aliyun_tts.py（阿里云配音）、render_ci_artifacts.py（CI 示例）、template_policy.py / validate_template_batch.py / 各 test_*（校验与测试）。
- 文档：`references/project-schema.md`（项目清单）、`references/creative-system.md`（创意系统）、`references/installation.md`（装机说明）、`references/layout-templates.md`（本地布局）、`references/template-examples.md`（18 套示例索引）、`references/triple-strip-shutter.md` / `references/yellow-banner-zoom.md`（两套本地动效模板，生产未采用）。
- 模板资产差异：本地目录曾含 29 模板（8 FFmpeg + 18 ref + 3 动效）；现已删除原 8 个标准预设及其案例，保留 21 个（18 ref + 3 动效），离线默认 ref-15-tianjin-monochrome；生产现行 20 模板（2 FFmpeg：full-overlay-bold/poster-split + 17 ref + nine-grid-reveal）。渲染服务校验 catalog.json 恰为这 2 个 FFmpeg 模板，**部署本仓库资产到渲染机前必须与生产副本核对**（见 SKILL.md §11）。

## 保留原因

- 模板资产（assets/templates/）仍是渲染服务的源（skill root），生产副本在云端 `upstream/`（FFmpeg 目录）与 `reference-upstream/`（ref 包）。
- CI 工作流 `.github/workflows/template-regression.yml` 用脚本回归模板资产。
- 外部环境（客户机器、Codex 沙盒）若需本地自渲染，可继续按本目录文档操作。

## 两代关键差异速查

| 事项 | 本地渲染器（旧） | 平台（现行） |
| --- | --- | --- |
| 谁渲染 | Agent 本机 FFmpeg/HyperFrames | 渲染机集群（中转器派单） |
| 模板数 | 21（已删除原 8 个标准预设） | 20 |
| 时长 | Agent 算、可指定 | 服务端算、不可指定（ref 随机 8~15 / FFmpeg 文案长度 / 九宫格 12s） |
| 断句 | Agent 逐字关键词分析 + 断句 | 服务端 AI 语义断句 + 真字体校验 |
| 素材 | Agent 检索挑选、可生成 AI 图 | 服务端按策略选（黄雀库+pexels），Agent 不挑 |
| 报价 | 无 | 内测直出（运行时自动确认） |

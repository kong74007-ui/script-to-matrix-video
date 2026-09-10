# 关键词强调（semantic emphasis，主站现行）

> 旧版「Agent 用 AI 逐字分析关键词、把强调结果写进项目文件」的职责已随本地渲染器退役。主站现状：关键词强调是**服务端渲染器内建行为**，Agent 不做关键词分析、不传强调参数。

## 现行行为

- **只作用于 2 个 FFmpeg 模板**（full-overlay-bold / poster-split）：目录 `emphasis_profiles` 定义各模板的强调参数（scale 放大倍率、color 强调色、outline 描边、role_colors 数字/利益点/CTA 角色色），渲染器按 `auto_highlight` 自动识别数字与利益关键词并上色放大。
  - full-overlay-bold：黄 #FFD400 强调、8px 深描边、放大 1.18x。
  - poster-split：黄 #FFD400 / 白利益点、7px 描边、放大 1.16x。
- **17 个 ref 模板没有关键词强调**：固定排版 + 固定字体，文案按语义断句排版，不做大字号关键词变色。
- 九宫格：标题/CTA 常驻，无关键词强调。

## Agent 注意

- 不要向用户承诺「某个词会被放大标黄」到 ref 模板上；要强调效果建议选 FFmpeg 两模板。
- 文案里的数字（价格/日期/数量）在两个 FFmpeg 模板上天然会被服务端强调，无需在文案里加特殊符号。

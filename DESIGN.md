# 中文竖屏模板设计正本

> ⚠️ 本地渲染器文档（主站已退役，2026-09-10）：仅作离线参考，黄雀主站生产走平台矩阵模板能力，见 script-to-matrix-video/SKILL.md。

## 产品上下文

模板服务于 `text-media-text`：顶部固定文字、中间可追溯素材、底部固定 CTA，面向 1080×1920 中文信息流。模板只定义字体、字号、颜色、描边、对齐、位置和媒体窗口，不生成内容素材。

## 保留模板

仓库离线资产共保留 21 套模板：

- 3 套独立动效模板：九宫格、三横屏光栅、黄条变幅；保留各自固定时间线与绑定 BGM。
- 18 套参考排版模板：来自已通过成片确认的排版效果，保存为独立 HyperFrames 模板包，ID 从 `ref-01-...` 到 `ref-18-...`。

原 8 个标准预设已删除，`catalog.json` 为空兼容目录。离线默认是 `ref-15-tianjin-monochrome`。参考模板目录为 `script-to-matrix-video/assets/templates/reference-typography-17/manifest.json`。

## 文字层级

参考模板使用五个独立文字层：

- `top1`：城市、主题或第一钩子；
- `top2`：核心利益点或人群；
- `top3`：补充说明、方法或强结论；
- `bottom1`：地点、身份、活动频率或信任信息；
- `bottom2`：评论、私信、报名等 CTA。

每套参考模板固定这五层的字号、字体、颜色、描边、行距和位置。层可以留空，但不能复制同一句文案填满空层。

## 素材与边界

- 模板成片禁止 AI 生成图片或视频。
- 只使用客户素材或素材库中状态为“可使用”的素材。
- 18 套参考模板每条必须输入三个不同的视频素材；案例 MP4/JPG 不能反过来当成新视频素材。
- 参考模板的单条时长不由用户填写；任务准备阶段随机生成 8–15 秒整数并记录，三个素材按该时长自动均分。
- 批量开启 BGM 时必须轮换曲目，相邻成片不得使用同一首。
- 模板没有文字渐入；文字显示的第一帧即为完整不透明度。

## 字体

- `Noto Sans SC`：清晰、功能性粗体；
- `ZCOOL XiaoWei`：克制的人文标题；
- `Ma Shan Zheng`：手写与城市圈层标题；
- `ZCOOL KuaiLe`：轻松、社交型强调。

字体随 Skill 分发，不依赖另一台电脑已安装的字体。

## 渲染入口

- 通用文案/自定义布局渲染（非已存模板）：`python scripts/render_video.py project.json`
- 参考模板：`python scripts/render_reference_typography.py batch.json --quality high --workers 4`

参考模板源文件、18 条案例 MP4 和 18 张第一帧 JPG 都随 Skill 保存，便于同事先看效果再选 `template_id`。

# 平台端到端工作流（主站现行）

## 标准单条流程

1. **要什么**：用户要「模板成片」= 顶部标题 + 底部行动文案两要素；缺则一次问清（不重复确认）。
2. **查目录**：`matrix-template-templates` 拿实时模板 + 字体；`matrix-template-capability` 确认渠道可用。
3. **给用户选**：挂带封面预览的模板选择卡（小样链接页面渲染成小缩略图，点开才播）；用户挑模板（+FFmpeg 模板可选字体）。
4. **生成**：`matrix-template-generate`（top_text/bottom_text/template_id [+font_family/voiceover]）→ 第一段报价 → 运行时自动确认直出 → 拿 job_id。
5. **轮询**：task 查原 job_id 到终态。
6. **交付**：completed → 成片本体链接（相对路径、裸文本一行）+ 实测时长 + 「内测期免费、不扣点」；素材清单/来源链接绝不贴。

## 批量流程

同上，第 4 步换 `matrix-template-batch-generate` + count 2~5；第 5 步保存全部 job_ids；部分失败按 `template-batch.md` 恢复指引处理。

## 配音流程（可选）

1. `voices` 查音色，复制 ready 项的 voice_key（+voice_scope）。
2. generate 带 `voiceover{text≤120, voice, voice_scope, speed}`；配音时 bgm 默认关。
3. 成片时长跟随口播实测；完成后报实测时长。

## 用户自带素材流程（通道未开通，现状）

1. 素材先 image-upload / video-upload 拿 upload_id（confirm 直发、免费）。
2. generate 带 user_materials（1~20 条）。
3. 被 400「不支持的参数」拒 → 降级 ChatCut 剪辑出同款（照片全屏铺底 + 标题/底字按模板样式 9:16、时长对齐）并如实说明一句。
4. 绝不谎称走了模板通道。

## 失败与恢复

- 渲染失败（黑屏/变量校验/素材失败）：检查后重试 1 次同参数；仍失败如实报原因。
- 响应不确定：只按原 job_id/batch 查询或恢复，绝不新建。
- 排队（active_job_cap=5）：如实告知「正在排队」，不是错误。

## 交付检查清单（发回复前逐项过）

- [ ] 链接是成片本体（result.video_url / `/api/v4/render/...`），不是素材来源/pexels
- [ ] 相对路径、无域名无前缀
- [ ] 时长照实测报
- [ ] 标了「内测期免费、不扣点」
- [ ] 转义符已还原（\n、\*、\"、\\）
- [ ] 拿到 job_id 才说「已提交」

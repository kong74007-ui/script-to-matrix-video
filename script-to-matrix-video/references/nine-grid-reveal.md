# 九宫格开场接全屏展示（nine-grid-reveal，主站现行）

独立模板 ID：`nine-grid-reveal`（variant=nine-grid，引擎 hyperframes 0.8.33）。不是 ref-* 的别名，也不改它们的随机时长规则。

## 平台契约

- 输入：与普通模板相同——top_text（标题）+ bottom_text（行动文案/副题），2~60 / 2~80 字符；**Agent 不传九宫格画面**（旧本地渲染器的 title/tagline/9 grid/3 main 输入已被平台化吸收）。
- 时长：**固定 12 秒、30fps**（duration_mode=fixed_12；传任何其它时长都会被服务端纠正为 12.0）。
- 画面：9 个宫格画面 + 3 个全屏画面，**服务端素材池选取**（策略 huangque-bookends-pexels-middle-v1；每个画面取 3.0s 切片——/v1/select 的 clip_duration_seconds 只收 2~3，不能传 3.2）；全屏位在宫格 0/4/8。
- 文字：标题与行动文案从第 0 帧到结尾全程常驻；AI 语义断句排版（层合同 top1/top2/bottom2，最大宽 930px）。
- BGM：绑定 BGM（bgm_mode=bound）但 bgm_optional=true——**可关**，与自动音乐选取和批量轮换无关。

## Agent 注意事项

- 用户要「九宫格开场」→ 选该 template_id + 两段文案即可，不要向用户索要 12 个画面。
- 固定 12 秒是模板特性，如实告知用户，不承诺可调时长。
- 目录字段：required_visuals=9 / required_visuals_max=9 / duration_mode=fixed_12 / bgm_mode=bound / bgm_optional=true；与目录不一致 = 渲染服务模板包异常，报障。

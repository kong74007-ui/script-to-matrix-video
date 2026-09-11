# 双语错位字幕·配音成片

ID：`bilingual-stagger-salon`。保留用户确认的 AI 圈子成片及此前沙龙成片的文字规则，非固定文案。源码在 `assets/templates/bilingual-stagger-salon/`，准备脚本为 `scripts/prepare_bilingual_stagger.py`。HyperFrames 0.8.38，仅离线模板，不代表部署主站。

## 保留规则

- 1080×1920，默认30 fps；原片为60fps时可用 `fps:60` 保留流畅度。全屏真实素材，不加黑边、圆角或额外装饰。
- 主标题 Ma Shan Zheng 128px，白字手写风，y=140；副标题 Noto Serif SC 800/80px，黄字，y=278。字幕 Noto Serif SC 700/82px，英文 400/38px。白色 #ffffff、黄字 #fff36a、暗描边/投影 #17130f。字体为已确认的便携近似匹配，不宣称与原剪辑字体完全一致。
- 中文字幕短句逐字错位入场：下移48/58/68px，-5/+6度，0.20秒归位；关键词直接黄色。英文逐词上升，0.18秒、间隔0.035秒。中英成对，可用 y=1260/1450 两层叠行；同层短句切换，不能整篇常驻。
- 标题按语义阶段短距离侧入，0.30秒入场、0.18秒退出；片尾文案保留到最后一帧。这是本模板明确允许的文字入场效果例外，不修改其他模板的“首帧静态文字”规则。
- 至少三段不同实拍视频，保持比例，约0.18秒短叠化和2.5–3%微推近。禁止 AI 生成素材及图片兜底。仅用用户素材或状态“可使用”的库记录。
- 使用用户配音；默认不加 BGM，无绑定曲目，不保留参考原声。长度跟随实测音频，向上对齐所选fps并留约0.6秒尾帧，不随机8–15秒，不拉伸或截短配音。

## 换配音、文案、素材

1. 首次使用先按 Skill 规则连接自己的素材库。此模板需完整音频和实测字幕时间；缺音频时索取音频或另行按用户授权合成，不硬套旧时间轴。
2. 使用支持中文的本机 ASR 生成词级时间，逐条核对转写。多字词可在自身测量时间范围内细分；零时长、错字、漏词需复核。不要按整段总字数均摊。每条英文是对应短句翻译，不添加收益承诺。
3. 将字幕整理为下方输入：每个 Unicode 字符（含引号和 AI 两个字母）有一个 `times` 时间；`yellow` 为零基字符索引；`row` 是0/1。最后一字需至少0.20秒完成入场；过密时合并短句或调整短句切换，不能截断文字。相邻同层仅允许最多0.055秒交接。
4. 默认 `render_profile:"gpu-hdr"`：准备至少三条不同真实视频，直接使用原始10-bit BT.2020 HLG/PQ素材，不先转SDR；支持旋转元数据，显示尺寸至少1080×1920，允许正确标记的Rec.709辅镜头，但必须有真实HDR源。按 [GPU HDR渲染](gpu-hdr-rendering.md) 配置并验证NVENC。用户明确要SDR兼容版时才设 `render_profile:"sdr-compat"`，此时使用真实Rec.709素材。每条须覆盖 `end-start+offset`，长配音加素材，不循环单素材填满。
5. 创建私有 `task.json`。路径相对该文件，或本机绝对路径；不上传此文件及配音、库视频、成片。

```json
{
  "render_profile":"gpu-hdr",
  "fps":30,
  "voice":"voice.mp3",
  "media":[
    {"path":"01.mp4","source_type":"client"},
    {"path":"02.mp4","source_type":"library","status":"可使用","record_id":"your-approved-record"},
    {"path":"03.mp4","source_type":"client"}
  ],
  "titles":[
    {"text":"深圳AI圈子","start":0.06,"end":3.8,"entrance_x":42},
    {"text":"专注落地实践","style":"subtitle","start":0.48,"end":3.8}
  ],
  "cues":[
    {"text":"我在深圳","en":"Here in Shenzhen","times":[0,0.14,0.28,0.60],"end":1.4,"row":0,"yellow":[2,3]}
  ]
}
```

以上仅展示字段，`cues` 必须替换成整段音频的真实完整时间轴。结尾 `end:"end"` 表示保持到片尾。可指定整体 `duration`（所选fps的帧边界，且不短于音频）；否则按配音自动计算。`media` 默认均分视频长度并重叠0.18秒；为贴合语义可为每项指定 `start/end/offset`，必须首尾连续且每次重叠0.18秒。标题 `style` 只有 `main/subtitle`，不能同位置持续重叠。超长标题/字幕先按语义缩短、拆句，不缩放压扁字体。

```bash
python scripts/prepare_bilingual_stagger.py --task task.json --output new-job --validate-only
python scripts/prepare_bilingual_stagger.py --task task.json --output new-job
cd new-job
npm run check -- --snapshots
npm run preview
# 确认后
npm run render -- --workers 2 --output renders/final-hdr.mp4
```

准备脚本只复制明确选择的原始文件，不负责联网转写、生成素材或公开上传。母版共享字体、OFL许可证、GPU包装器和定点兼容模块会被复制进新项目；不要只单独下载模板子目录。用户提供配音完整保留，库素材原声静音。Windows 子进程保持隐藏。HDR流程需配置本机CLI路径；无有效NVENC或原始HDR时明确报错，不偷偷退回CPU/SDR。

检查首句、最长句、双行叠字、切镜和末尾：文字不溢出、无残留引号、人物不拉伸、颜色不发白、配音不断。逐字入场途中24ms左右的文字边界交叠可能被审计报为 warning；需看实际帧，不可全局忽略布局检查。返回实际MP4链接。

## 保存与公开

按 [模板发布规则](template-publishing.md) 同步本机与GitHub。公开包只含可复用代码、GSAP及已有共享字体许可证，不含参考完整视频、两条演示成片、用户配音、库素材和个人路径。本模板无绑定BGM，因此无音频随模板发布。普通默认模板和平台调用规则不变。

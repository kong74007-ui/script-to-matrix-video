# 本机 GPU / 10-bit HEVC HDR

适用：用户明确要求 NVIDIA GPU 编码并保留原素材 HDR 的离线任务。当前入口为 `scripts/render_gpu_hdr.py`，已接入 `bilingual-stagger-salon` 准备脚本；不代表其他旧模板或主站渲染服务已升级。其他模板迁移必须单独检查原始素材、动效、HDR 合成兼容性后实测。

## 画质与范围

- 从原始 10-bit BT.2020 HLG/PQ 视频开始，保留方向、源帧率、源片段和比例。不能用先前已转 SDR、720p 或 H.264 代理的文件再贴 HDR 标签。没有 HDR 原片时说明限制，不声称能恢复原有高光。
- 当前成片 1080×1920，30/60fps 可选，60fps 仅用于有相应源帧率的素材；不要用插帧宣称原生画质。文字字号、配音时间轴和动效保持模板约定。
- HyperFrames 原生 HDR 分层合成保留高位深画面；DOM 文字层转换到目标色彩空间。输出 NVENC HEVC Main10、yuv420p10le、BT.2020、原片 HLG/PQ 类型、CQ16、VBR，无固定低码率上限；音频 AAC。
- GPU 用于最终 NVENC 编码；浏览器文字层默认软件截图，避免本机曾出现的 GPU 捕获片尾无响应。HDR 解码、合成、磁盘读写仍依赖 CPU。不是全 GPU 流水线，也不是无损输出。`--browser-gpu` 仅供另行测试，不等于已验证的生产配置。HDR 高位深缓存较大，先确认临时磁盘有足够空间。
- HLG HDR 不等于严格 HDR10 母版，更不等于保留 Dolby Vision 动态元数据；若用户明确要求 HDR10 mastering metadata 或 Dolby Vision，另行处理。普通 SDR 播放器显示效果不能用来判断 HDR 高光；需要支持 HDR 的显示链。

## 本机依赖（不公开个人配置）

安装并定位 HyperFrames 0.8.38 的 `dist/cli.js`，需要 Node.js、Python、FFmpeg/ffprobe，以及实际支持 HEVC Main10 NVENC 的 NVIDIA 驱动。编译列表中出现 `hevc_nvenc` 不代表硬件调用成功，包装器会先进行真实编码测试。

FFmpeg 9.0 本机实测需要 NVENC API 13.1、NVIDIA 驱动至少 610；RTX 3060 更新至 616.92 后测试通过。其他 FFmpeg 构建按实际测试判断，不硬编码全部机器的驱动版本。

可使用参数 `--cli /path/to/hyperframes/dist/cli.js --ffmpeg-bin /path/to/ffmpeg/bin`，或在用户私有的 `$CODEX_HOME/script-to-matrix-video/render-runtime.json`（未设置时 `~/.codex/...`）保存 `hyperframes_cli`、`ffmpeg_bin`。只保存路径，不保存凭据，不复制到 GitHub。

```bash
python scripts/render_gpu_hdr.py new-job --preflight-only --cli /path/to/hyperframes/dist/cli.js
# 先完成 HyperFrames check，保持用户已确认的版式
python scripts/render_gpu_hdr.py new-job --output renders/final-hdr.mp4 --cli /path/to/hyperframes/dist/cli.js
```

## 0.8.38 的定点兼容处理

实测上游 HDR `runCaptureHdrStage` 没有把 `useGpu` 传给流式编码器，因此普通 `--gpu --hdr` 仍可能运行 libx265。`hyperframes_hdr_patch.py` 只在每次运行中生成同包目录下的唯一临时 CLI：补传此字段、为 HDR NVENC 设置 Main10/VBR/hvc1，拒绝 CPU 回退，结束后移除临时 CLI。原始安装文件与其他窗口不变。包目录必须可写。

仅支持已审计的 0.8.38，版本或补丁锚点变化时失败并重新审计，不能盲目修改新版本；不声称上游已合并修复。生成项目必须同时保留 `render_gpu_hdr.py` 和 `hyperframes_hdr_patch.py`。

## 验收

HDR 合成按带 `data-start` 的元素收集图层。双语字幕容器必须保留完整画布尺寸、`class="clip"`、`data-start="0"`、全片 `data-duration` 和独立层级；内部字词仍按原 GSAP 时间轴出现。仅浏览器预览正常不代表 HDR 成片包含字幕，必须抽查实际编码文件中的中英文字幕。

检查真实输出的 HEVC Main10、10-bit 像素格式、BT.2020 + HLG/PQ、`hevc_nvenc` 编码器标记、1080×1920、实际 fps/时长及 AAC。包装器拒绝不符输出，并保存私有 `.verified.json` 和日志。再看开头、中间、切镜和结尾，确认人物比例、字幕和色彩；若制作 SDR 检查图，应真正 tone-map，只作为检查，不替换 HDR 成片。

官方机制与限制：[HyperFrames HDR 文档](https://github.com/heygen-com/hyperframes/blob/main/docs/guides/hdr.mdx)。

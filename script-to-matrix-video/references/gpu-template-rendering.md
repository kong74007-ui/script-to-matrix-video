# 全部离线模板的 GPU 默认执行规则

所有已保存模板通过九个模板族入口统一执行 GPU 优先策略，包括整套参考字体模板和八种动效模板。此修改适用于本机 Skill、仓库源码和之后新建的任务，不代表远程生产服务已经部署，也不会自动修改已经打开的旧项目。

## 各阶段

- 编码：强制 NVIDIA NVENC。普通模板仍使用 H.264/AAC SDR 兼容格式；双语配音模板的 `gpu-hdr` 使用 HEVC Main10、10-bit、BT.2020 HLG/PQ。编码前真实测试硬件，编码后检查文件中的 NVENC 标记；失败报错，不悄悄换 CPU 编码。
- 解码：FFmpeg 预处理及 HyperFrames 视频抽帧优先 NVDEC。审计过的 H.264 4:2:0 8-bit、HEVC 4:2:0 8/10-bit 路径使用 CUDA；H.264 High10、4:2:2 等其他编码/像素格式可使用 CPU 解码，最终编码仍为 GPU。
- 缩放：现有预处理中的固定尺寸等比 SDR 缩放使用 `scale_cuda`；保留原裁剪位置和色彩转换顺序。已存在的 libplacebo GPU 色彩处理保持不变。不把尚未验证的 CPU 滤镜强行替换为不同视觉效果。
- 浏览器画面：默认 `--browser-gpu`，使用 Chromium GPU 合成支持的步骤。截图读回、某些滤镜、原生 HDR 高位深图层合成、音频及磁盘操作仍需要 CPU。GPU 优先不意味着所有步骤都在 GPU，也不承诺每种短片都更快。

不改变文字、字体、绑定 BGM、固定开场、素材比例、转场时序或随机 8–15 秒规则。不得给 SDR 文件直接贴 HDR 标签来假装恢复画质。H.264 SDR 与 HEVC HDR 是色彩/兼容模式，不是 GPU 与 CPU 的区别。

## 使用

新任务按各模板准备流程创建，使用生成项目的 `npm run render -- --output renders/new-name.mp4`。参考字体批量继续使用 `scripts/render_reference_typography.py`，其素材预处理、批量渲染和最终时长裁切均已接入 NVENC。

需要 Node/npm、Python、支持 NVENC/CUDA 的 FFmpeg/ffprobe 和可用 NVIDIA 驱动。首次先运行模板保留的 `npm run check`，该命令同时缓存对应版本的 HyperFrames。若缺运行时，按报错运行 `npx --yes hyperframes@指定版本 --version`。本次保留已经审计的 0.8.29/0.8.33/0.8.34/0.8.38 各模板版本，不盲目升级。

`scripts/gpu_runtime.py` 是统一源码，`scripts/sync_gpu_runtime.py` 将便携副本和 npm 入口同步到各模板目录。不要只复制 HTML 而遗漏 Python 文件。HDR 项目还必须保留 `render_gpu_hdr.py` 和 `hyperframes_hdr_patch.py`，见 [HDR 规则](gpu-hdr-rendering.md)。

已创建的旧项目需重新按更新模板准备，或仅更新相同模板的 package.json 及 GPU 辅助脚本；保留旧项目的文案、HTML、媒体及时间轴，不用母版占位文件覆盖。旧项目仍运行旧的裸 `npx … render` 命令时不会自动获得统一策略。

## 兼容、安全与验收

临时桥接已审计 CLI 的编码/抽帧函数，支持检测像素格式、禁止 CPU 编码回退；原安装文件不变，其他窗口不被修改。版本或锚点变化则拒绝运行。辅助进程在 Windows 隐藏，不打开控制台窗口。使用全新的输出名，防止旧文件被当作本次成功结果。

遇到浏览器 GPU 驱动/捕获兼容问题，先保存错误，才可显式用 `--no-browser-gpu` 诊断；此时 NVENC 仍必须启用，交付时说明浏览器阶段的例外。不要在失败时静默改成 CPU。

验收包含实际 NVENC 标记、音频、尺寸、帧数/时长、色彩信号及真实编码帧中的字体/字幕/素材比例。维护测试覆盖统一入口、便携文件一致性、临时 CLI 清理、CPU 回退拒绝和预处理过滤顺序；不能用参数中出现 `--gpu` 代替实际验证。

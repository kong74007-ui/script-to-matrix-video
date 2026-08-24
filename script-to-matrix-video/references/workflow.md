# Complete production workflow

Use this reference when planning or running a full video job.

```mermaid
mindmap
  root((客户文案一键成片))
    输入与理解
      保留原始文案
      识别客户与受众
      提炼痛点与承诺
      判断语气与内容类型
      提取强制信息与禁用表达
    全片策略
      原生信息流风格
      9比16通用母版
      视觉圣经
        色彩
        人物与场景
        镜头语言
        字幕版式
        动效强度
      CTA
        文案自带优先
        约束池随机
    语义分镜
      开头钩子
      痛点展开
      原因或证据
      解决方案
      行动指令
      每镜头一至三个素材
    素材检索与生成
      客户素材优先
      可使用素材库
        图片
        视频
        BGM
        元数据语义检索
        候选画面复核
        复制到项目目录
      AI图片补缺
        素材提示词
          全文上下文
          当前分镜任务
          统一画面风格
          竖屏构图与字幕留白
          负面约束
        封面图
        分镜主图
        细节或对比图
        失败最多重试两次
        文字卡兜底
    阿里语音
      CosyVoice合成
      分镜独立缓存
      48k单声道WAV
      读取真实音频时长
      失败最多重试两次
    时间轴锁定
      音频时长加尾部缓冲
      字幕按语义切块
      素材时长分配
      动效节奏
      转场窗口
    剪辑与包装
      图片运镜
        轻推近
        轻拉远
        横向平移
        局部揭示
      字幕烧录
      语义音效
      BGM
        按整体内容选曲
        交叉循环
        淡入淡出
        人声避让
      风格化转场
      分镜拼接
    封面与首帧
      独立封面文案
      第一帧展示
      不把文字交给生图模型
    渲染与质检
      H264加AAC
      1080乘1920
      30帧
      检查首帧中段CTA
      检查字幕安全区
      检查音视频时长
      输出MP4
    可恢复与复用
      项目清单
      哈希缓存
      单镜头重跑
      素材库检索与来源记录
      多客户矩阵生产
```

## Stage gates

| Gate | Must be true before continuing |
|---|---|
| Copy analysis | Audience, pain point, promised value, tone, and CTA policy are explicit |
| Storyboard | Every source-copy idea is represented and each scene has one narrative function |
| Material resolution | Every selected library record is `可使用`, has been visually checked, and is copied into the project; missing scenes have an AI-generation plan |
| Visual generation | A global visual bible exists and each generated scene prompt inherits it |
| Timing lock | With narration, every scene has a successfully probed audio duration; without narration, every scene has a positive explicit duration |
| Render | Images/videos, audio, optional BGM, caption chunks, motion, and transition values resolve to local files or allowed defaults |
| Delivery | Final MP4 probes successfully; opening, middle, CTA, contextual relevance, and audio balance spot checks pass |

## Resume logic

Resume from the first failed or stale artifact. An artifact is stale when its input hash no longer matches the copy, prompt, voice settings, or render settings recorded in the manifest. Do not discard unaffected scenes.

# 主站模板成片 CLI 合同

仅在使用黄雀主站当前模板成片服务时读取本文件。本地内置 FFmpeg/HyperFrames 渲染继续使用 `layout-templates.md`、`reference-typography-templates.md` 和 `template-batch.md`。

## 适用范围

满足任一条件时优先使用本路径：

- 用户要求使用网站当前模板、平台素材库或账号任务记录；
- 用户要选择公共音色或本人已复刻的个人音色；
- 用户需要模板成片配音、语速调节或主站批量生成；
- 本机已有已登录的 HQ CLI 0.15.4 或更高版本，且用户没有指定离线渲染。

本路径不上传本地素材，不调用 AI 图片或视频生成。素材由主站从平台已审核素材库选择，按精准匹配、宽松匹配、随机可用的顺序补足；同一成片不重复素材，批量输出使用不同素材组合。不要把内置案例视频当作新任务素材。无配音时 BGM 与成片时长由服务端处理，BGM 应覆盖完整视频；开启配音后不使用 BGM。

## 免费准备检查

先执行以下只读命令；它们不会创建视频或扣点：

```sh
hq version --json
hq status --json
hq run matrix-template-capability --json
hq run matrix-template-templates --json
```

要求：

- `cli_version` 不低于 `0.15.4`；
- 账号处于已登录可用状态；
- 模板成片 capability 可用；
- `template_id` 必须从本次 `matrix-template-templates` 结果选择，不按旧文档猜测 ID；
- 固定字体或 HyperFrames 模板不传 `font_family`。

需要配音时再读取音色：

```sh
hq run voices --json
```

只使用 `ready=true` 的项目，复制其 `voice_key`；同时复制 `scope` 到 `voice_scope` 可防止音色归属变化。不得记录供应商内部音色 ID。

## 输入合同

单条和批量共用以下字段：

| 字段 | 规则 |
| --- | --- |
| `top_text` | 必填，2–60 字符 |
| `bottom_text` | 必填，2–80 字符 |
| `template_id` | 必填，来自实时模板目录 |
| `font_family` | 可选，仅用于目录中允许选择字体的模板 |
| `voiceover` | 可选；存在即开启配音，不存在即保持无配音模式 |

`voiceover`：

| 字段 | 规则 |
| --- | --- |
| `text` | 必填，1–120 字符 |
| `voice` | 必填，来自 `voices` 的 `ready=true` 项 |
| `voice_scope` | 可选，`public` 或 `personal`，应与音色目录一致 |
| `speed` | 可选，0.5–2.0，默认 1.0，服务端按 0.1 归一化 |

不要传 `pitch`、`volume`、`delivery`、`bgm`、`duration`、`batch_id`、`batch_index` 或 `batch_size`。服务端会补齐固定配音参数；开启配音时强制关闭 BGM，最终时长跟随实际音频。无配音时使用服务端正常 BGM 与自动时长。

对于当前 HyperFrames 模板，传完整 `top_text` 和 `bottom_text`。服务端在扣点前完成 AI 语义分块和真实字体宽度校验；不要自行填写 `top1`、`top2`、`top3`、`bottom1` 或 `bottom2`，不要在校验失败后缩小模板固定字号。

## 单条报价与生成

准备一个 UTF-8 JSON 文件：

```json
{
  "top_text": "真正拉开差距的，不是工具",
  "bottom_text": "评论区留下关键词，领取完整方案",
  "template_id": "ref-04-foshan-yellow-strip",
  "voiceover": {
    "text": "真正拉开差距的，不是你用了多少工具，而是能不能把工具变成稳定产出的流程。",
    "voice": "vip_slot_12345678",
    "voice_scope": "personal",
    "speed": 1.2
  }
}
```

先报价：

```sh
hq run matrix-template-generate --input @matrix-template.json --json
```

向用户展示返回的点数、输入摘要和关键设置。只有用户明确确认本次付费生成后，才能用完全相同的输入和原 `quote_token` 提交：

```sh
hq run matrix-template-generate --input @matrix-template.json --confirm --quote-token '<quote_token>' --json
```

取得 `job_id` 后只查询原任务：

```sh
hq run task --input @- --json <<'JSON'
{"job_id": 123}
JSON
```

不得因为轮询慢、网络断开或页面未刷新而重新生成。

## 批量生成

仅当实时模板目录和 CLI 允许该模板批量生成时，使用 `matrix-template-batch-generate`。当前 HyperFrames/固定字体模板只支持单条；不要绕过限制并行创建替代批次。

批量请求在单条输入上增加 `count`，范围 2–5：

```json
{
  "top_text": "真正拉开差距的，不是工具",
  "bottom_text": "评论区留下关键词，领取完整方案",
  "template_id": "native-bold",
  "count": 3,
  "voiceover": {
    "text": "把工具变成稳定产出的流程，才能持续提高内容产能。",
    "voice": "S_d21F8OR62",
    "voice_scope": "public",
    "speed": 1.0
  }
}
```

```sh
hq run matrix-template-batch-generate --input @matrix-template-batch.json --json
hq run matrix-template-batch-generate --input @matrix-template-batch.json --confirm --quote-token '<quote_token>' --json
```

服务端从签名报价派生共享批次 ID，2–5 个子任务复用同一段配音缓存，并为每条选择不同素材。客户端不得提供或修改批次身份字段。

保存返回的全部 `job_ids` 并逐条查询。某一条失败不代表其他任务失败。

## 恢复规则

- 报价过期或输入有任何变化：重新报价，不复用旧 token。
- 已返回 `job_id`/`job_ids`：只轮询原任务，不再次提交。
- 返回 `batch_result_pending`：保留响应中的 `jobs`、`job_ids` 和 `next_index`；仅按错误提示用完全相同输入、原 token 和 `--confirm` 重放一次，服务端会复用原批次与子任务幂等键。
- 返回部分成功：继续查询已受理任务，不为失败项自动创建替代任务。
- 返回 AI 断句、字体宽度、素材或音色校验错误：报告原错误；不要降级到本地模板、其他音色或 AI 素材。
- 任何 dry run、目录读取、方案说明都不能执行带 `--confirm` 的命令。

不要在日志、Skill、项目文件或回复中保存账号 token、供应商凭证、内部音色 ID 或签名下载地址。

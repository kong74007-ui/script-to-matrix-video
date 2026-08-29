# 18 套参考排版模板

这组模板保留了用户确认过的 18 套文字排版、字号、字体、颜色、描边、文字层级和中间素材结构。它们使用 HyperFrames 渲染，与 `assets/templates/catalog.json` 中的 8 套标准 FFmpeg 模板相互独立。

## 选择表

| template_id | 名称 | 适合内容 |
|---|---|---|
| `ref-01-chengdu-green-brush` | 成都绿描边手写 | 女性圈层、社群、成长 |
| `ref-02-shenzhen-ai-orange` | 深圳 AI 橙色主标题 | AI 沙龙、获客、科技创业 |
| `ref-03-zhengzhou-blue-banner` | 郑州蓝色标题红横条 | 城市活动、沙龙报名 |
| `ref-04-foshan-yellow-strip` | 佛山黄色信息条 | 老板茶话会、同城活动 |
| `ref-05-changsha-white-red` | 长沙白字红强调 | 聚会、破圈、邀约 |
| `ref-06-guangzhou-yellow-button` | 广州黄色按钮 CTA | 读书会、女性组织、强转化 |
| `ref-07-shenzhen-red-growth` | 深圳红色成长强调 | 高净值圈层、成长话题 |
| `ref-08-puyang-yellow-white` | 濮阳黄白层级 | 中年女性圈层、聚会报名 |
| `ref-09-urumqi-soft-brush` | 乌鲁木齐柔和手写 | 温暖女性社群、长期成长 |
| `ref-10-shenzhen-sisters` | 深圳姐妹自我提升 | 姐妹圈、自我提升 |
| `ref-11-nansha-clean` | 南沙清爽三层标题 | 创业沙龙、资源互换 |
| `ref-12-guangzhou-brush` | 广州手写聚会 | 中年女性、资源链接 |
| `ref-13-shenzhen-green-location` | 深圳绿色坐标 CTA | 本地活动、饭局、线下邀约 |
| `ref-14-karamay-green` | 克拉玛依绿系手写 | 异地女性圈、资源共享 |
| `ref-15-tianjin-monochrome` | 天津黑白极简 | 稳重圈层、退休生活、知识活动 |
| `ref-16-shenzhen-opc` | 深圳 OPC 多层信息 | OPC、共享创业、项目招募 |
| `ref-17-shenzhen-yellow-red` | 深圳黄红爆款层级 | 强钩子、强报名、矩阵引流 |
| `ref-18-beauty-private-domain` | 美业粉白私域运营 | 美业、私域运营、朋友圈、女性创业 |

## 输入字段

每条任务使用以下字段：

- `name`：输出文件名，只使用英文、数字、连字符或下划线。
- `template_id`：上表中的一个稳定 ID。
- `top1`、`top2`、`top3`：顶部三层文字；至少填写一层。
- `bottom1`、`bottom2`：底部两层文字；至少填写一层。
- `videoA`、`videoB`、`videoC`：三个不同的、已批准的本地视频素材。禁止 AI 生成素材、禁止图片替代，也禁止用同一个素材重复填充。
- `bgm`：可选的已批准本地 BGM；省略时保留兼容音轨但静音。

不要输入 `duration`。每条任务在准备阶段自动随机生成一个 8–15 秒的整数时长，并写入工作目录中的 `batch/prepared-rows.json`。同一工作目录的 dry-run 与正式渲染复用该次随机结果；新任务使用新的随机结果。

示例：

```json
{
  "rows": [
    {
      "name": "opc-shenzhen-a",
      "template_id": "ref-16-shenzhen-opc",
      "top1": "我在深圳发起了\n共享创业 OPC 门店",
      "top2": "1个人＋AI员工",
      "top3": "接待｜导购｜成交｜复盘",
      "bottom1": "坐标：深圳-南山",
      "bottom2": "想了解私信 OPC",
      "videoA": "D:/approved-media/store-01.mp4",
      "videoB": "D:/approved-media/ai-store-02.mp4",
      "videoC": "D:/approved-media/customer-service-03.mp4",
      "bgm": "D:/approved-media/bgm/track-01.mp3"
    }
  ]
}
```

## 渲染

先完成素材库连接、素材检索和来源记录，再运行：

```bash
python scripts/render_reference_typography.py batch.json --quality high --workers 4
```

批量任务默认串行启动每个成片、单条内部使用 4 个 worker，避免本机内存峰值。脚本会把模板复制到任务自己的工作目录，不会修改 Skill 内的模板源文件。三个输入视频会在任务目录中循环补足到 15 秒，HyperFrames 完整渲染后再按该条记录的随机时长精确裁切，避免短素材或最后一段提前结束造成黑屏。

这组版式固定为 1080×1920、30fps，单条时长由脚本随机设为 8–15 秒整数。三个素材按实际总时长自动均分，文字从第一帧完整显示且不做渐入。它适合短钩子和活动邀约；超过可读容量的文案必须先压缩或拆成多条，不要缩成难以阅读的小字。

## 文件位置

- 模板源文件：`assets/templates/reference-typography-17/`
- 机器可读清单：`assets/templates/reference-typography-17/manifest.json`
- 案例视频和封面：`assets/examples/text-media-text/reference-typography-17/`
- 批量渲染脚本：`scripts/render_reference_typography.py`

案例 MP4/JPG 只用于选款和视觉核对，禁止把案例视频重新当作内容素材投入新成片。

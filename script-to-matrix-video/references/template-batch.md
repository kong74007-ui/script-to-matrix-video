# 批量模板成片（matrix-template-batch-generate，主站现行）

## 契约

- 一条调用 `count` 2~5 条：`top_text + bottom_text + template_id + count`（+可选 font_family / voiceover）。
- 一次调用生成整批，**绝不逐条单独 generate**；同一批共享一次报价与一次确认（内测期运行时自动确认直出）。
- 批量任务由渲染服务按 batch_id（32hex）+ batch_index/batch_size（1~5）标记，整批独立成片；素材/切点/强调在批内做差异轮换（服务端按种子决定），文案本身不改。
- **字体锁定的模板（ref-* / nine-grid-reveal）批量可用**；只有「字体参数」这类必须单条的能力才降级单条并说明（当前目录下没有这种模板）。

## 提交后

- 保存返回的**全部 job_ids**，只轮询 task 查这些原任务直到终态。
- 部分成功/部分失败：保留已接受任务与已出成片，按返回错误里的 jobs/job_ids 处理，**绝不新建整批**；仅当返回 batch_result_pending 并明确要求恢复时，才用完全相同输入、原 quote_token 重放一次。
- 结果不确定（超时/网络错误）：先按原 batch_id / job_ids 查询，绝不盲目重发。

## 与单条的区别

- 单条：matrix-template-generate，一次一条。
- 批量：count 2~5。用户要「同一文案多条」或「一套文案多条」时优先批量。
- 内测期两条路都直出无报价卡、免费不扣点。

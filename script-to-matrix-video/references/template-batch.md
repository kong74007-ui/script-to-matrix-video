# 批量模板成片（matrix-template-batch-generate，主站现行）

## 契约

- 一条调用 `count` 2~5 条：`top_text + bottom_text + template_id + count`（+可选 font_family / voiceover）。
- 一次调用生成整批，**绝不逐条单独 generate**；同一批共享一次报价与一次确认（内测期运行时自动确认直出）。
- 批量任务由渲染服务按 batch_id（32hex）+ batch_index/batch_size（1~5）标记，整批独立成片；素材/切点/强调在批内做差异轮换（服务端按种子决定），文案本身不改。

## 模板限制（2026-09-10 客户实录修正）

- **batch 只对非字体锁定模板开放**：当前是 full-overlay-bold（沉浸强标题）、poster-split（三段式活动海报）。
- **ref-01~ref-17 与 nine-grid-reveal（HyperFrames + 字体锁定）平台直接拒绝批量**，报「HyperFrames 模板暂仅支持单条生成」。
- 这类模板用户要 N 条时只有两条路：
  1. **逐条 generate 调 N 次，且每条参数（文案）必须不一样**——平台按「能力+参数」5 分钟去重，参数一字不差的第二次不会产生新任务，只会返回同一个 job_id（`ok=false`、error 写明「本次没有创建新任务」——这是正常提示，不是失败）；
  2. 如实告诉用户「这个模板一次只能出一条」，问清是改文案再出一条、还是换支持批量的模板。
- **被拒后只发了一条却对用户说「两条已经提交上了」= 谎报，绝对禁止**；被拒后也不要反复重试完全相同的参数。

## 提交后

- 保存返回的**全部 job_ids**，只轮询 task 查这些原任务直到终态。
- 部分成功/部分失败：保留已接受任务与已出成片，按返回错误里的 jobs/job_ids 处理，**绝不新建整批**；仅当返回 batch_result_pending 并明确要求恢复时，才用完全相同输入、原 quote_token 重放一次。
- 结果不确定（超时/网络错误）：先按原 batch_id / job_ids 查询，绝不盲目重发。

## 与单条的区别

- 单条：matrix-template-generate，一次一条。
- 批量：count 2~5，只对 2 个非字体锁定模板开放。
- 内测期两条路都直出无报价卡、免费不扣点。

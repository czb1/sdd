# 执行阶段任务 Skill 消费 [可配置: skill_consumption]（默认关闭）

## 启用门控

仅消费根项目 `docs/.flow_context/execution-plan-core-apply.json` 的 `orchestration_points.pre-codegen` 中 `key=skill_consumption`、`type=reference`、`file=references/skill-consumption.md` 的有效条目；多仓子代理使用主会话下发的执行计划片段中的同一条目。未配置、已注释、条目不存在或显式 `enabled=false` 时立即返回，不读取关联的 Skill / 经验内容，不检索、确认、下载或回写字段。

这是现有 `pre-codegen` 的自定义 reference 子步骤，不新增固定 Step 或内置布尔键。不要用 core-design 的计划、已有 Skill 字段、本地文件或其他 pre-codegen 条目推断启用。计划 / 片段不可读取或无效时停止并报告计划错误，不自行视为启用或从配置源重建。

<!-- GATE:REF ../core-shared/references/skill-consumption.md -->
**MANDATORY GATE（仅启用时）**：Read `config_dir / 'skills/core-shared/references/skill-consumption.md'`，按共享规则处理候选、确认、安装、失败及任务回写。路径相对本 SKILL 安装目录为 `../core-shared/references/skill-consumption.md`；不存在时 MUST STOP，不复制规则回 SKILL.md。
读取后输出: "GATE PASSED: core-shared/references/skill-consumption.md loaded"。
<!-- /GATE:REF -->

## 循环前准备（主会话，每轮一次）

1. 只处理 tasks.md `## 代码生成任务` 的待办 1.x 任务；无待办直接返回。多仓在启动 M-2 代码生成代理前汇总各仓待办，以“仓名 + 任务编号”区分。
2. 读取 Skill 字段和已关联的本地内容；尊重「不使用（用户选择）」，不将其当成缺失关联。已有有效关联直接复用，不重复选型或确认。
3. 已锁定的同名内容丢失时按原决定补下，无须重新选型；需要新增 / 改选时才按共享规则的「CLI 命令与字段传递」准备候选：业务能力走 `offering` → `product-scenes` → `scene-skills`（`scenes --repo` 已返回产品及场景时复用），通用能力走 `skill search`，业务未命中再加 `experience search`。由主会话按任务组一次批量确认，然后按名称去重，用真实 Skill ID 调用 `skill download`，安装并回写。下载失败保留旧内容，仅验证旧内容仍适用时才复用。
4. 只在会话内保留本轮准备结果及未选用 / 失败状态，避免每任务重复检索、确认或重试；tasks.md 仍是持久关联唯一来源，不另建能力索引。

## 每任务消费（pre-codegen，task 级）

1. 在单仓 9.3.5 / 多仓模板步骤 c 的 pre-codegen 位置，复核本步骤条目仍有效，再读取当前任务锁定的 Skill / 经验内容，作为代码生成上下文；不得改写项目原则或跳过原验证步骤。
2. 复用循环前的批量准备结果，不再执行全量候选准备。明确不使用、无合适候选或本轮获取失败时继续原任务，不在每个任务弹窗或重新下载。
3. 循环中发现新的新增 / 改选需求时，汇总并预检其余待办任务，回到主会话的批量准备阶段统一处理；已有可用关联的任务可以继续，不逐任务临时弹窗。
4. 继续执行 pre-codegen 中其他已配置条目，然后进入原则自检与代码生成。

## 多仓执行

- 主会话从根执行计划判断启用并完成循环前准备，将计划片段及锁定结果交给各仓代理；片段缺少本条目时该仓不执行消费，其他编排条目照常执行。
- 子代理在每任务的 pre-codegen 条目中读取本文件及共享规则，按本仓 tasks.md 读取已锁定内容；单纯补下同名内容可按原决定在本仓落地，不下载替代 Skill，不修改其他仓。
- 新增 / 改选需求只返回主会话汇总处理，禁止子代理各自提问。委托时传入本文件、共享规则、根执行计划与本仓片段的绝对路径；不假设主会话加载的文件自动进入子代理上下文。
- 关闭时仅跳过新增消费行为；普通任务读取、checkbox 更新、M-2 代码生成以及其他已配置步骤照常执行。保留已有 Skill / 经验字段和本地文件，方便以后重新启用。

## 输出

汇报实际使用的关联、用户指定 / Agent 自选 / 不使用及获取失败任务；失败说明后继续原任务，字段回写失败不得宣称成功。关闭时只报告“skill_consumption 已关闭”，不把关闭伪装成无候选或获取失败。

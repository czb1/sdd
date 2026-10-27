# Phase 10: design-doc-reviewer 审查（单仓模式指令文件）

> 本文件为可配置步骤 `design_review` 的指令文件（单仓版）。仅在执行计划含 `key=design_review` 条目时被 Read。

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，禁止主会话直接执行
**【禁止】主会话直接调用 design-doc-reviewer Skill tool** — 主会话必须通过 Agent tool 启动子代理，由子代理调用 Skill tool
**加载技能**: ["design-doc-reviewer"]
**同步/异步**: sync

**【强制执行证据】**：
- **必须**使用 Agent tool（subagent_type="general"）启动子代理执行审查 — 禁止直接调用 Skill tool: design-doc-reviewer
- **必须**显式声明"已通过 Agent tool 启动子代理执行 Phase 10 design-doc-reviewer 审查"
- **必须**展示子代理的返回结果（PASS/FAIL 及 findings 数量）

**子代理启动方式**：
```
Agent tool: subagent_type="general", prompt="执行 core-design Phase 10 design-doc-reviewer 审查。调用 Skill tool: design-doc-reviewer <change-name>。按 design-doc-reviewer 的 CHECK-ID 集合执行审查，如有 ERROR 执行 3 轮自动修复循环。审查完成后报告结果。"
```

## 审查维度

| 维度 | 检测内容 | 严重级别 |
|------|----------|----------|
| 六维检测 | 可测试性/可维护性/可扩展性/安全性/可监控性/容错性 | ERROR |
| 九条宪法 | 简洁性/抽象性/单一职责/清晰结构/一致性/可读性/可验证性/最小依赖/增量更新 | WARNING |
| NEEDS CLARIFICATION 限流 | 单文档标记不超过 3 个 | ERROR |

## 自动修复循环（最多 3 轮）

1. 读取 design-doc-reviewer 输出的 findings 列表
2. 按 finding 类型执行修复：
   - 【文档保真类】必需章节缺失 → 补充缺失章节
   - 【文档保真类】截断/占位符 → 替换为具体内容
   - 【文档保真类】验收条件缺失 → 补充可判定的验收条件
   - 【文档保真类】越权决策/隐式越权 → 删除越权内容，返回主会话由主会话与用户确认
   - 【文档保真类】Q&A 捏造 → 删除无交互记录对应的 Q&A
   - 【实现一致性类】设计引用 spec 外模块 → 删除多余模块或在 spec 中补充需求
   - 【实现一致性类】设计模块无对应任务 → 在 tasks.md 中补充遗漏任务
   - 【实现一致性类】任务缺少必需字段 → 补充编程语言/关联需求/验收标准
   - 【用户意图类】NEEDS CLARIFICATION 超标 → 返回主会话，由主会话与用户澄清
   - 【用户意图类】→ **禁止**自行修改文档掩盖问题，必须返回主会话由主会话与用户更新决策记录
3. 修复完成后，**必须重新调用** Skill tool: design-doc-reviewer <change-name>
4. 3 轮后仍有 FAIL → 暂停流程，返回主会话由主会话上报用户处理
5. **禁止**：发现 FAIL 后仅报告问题不修复

## 判断

- 审查通过 → 进入 Phase 11（如 `cleanup` 开启）或流程完毕
- 审查失败 → 修复文档问题后重新审查（循环最多 3 次）

**主会话后处理**（子代理返回后执行）：
- 子代理返回审查通过 → 进入 Phase 11（如 `cleanup` 开启）
- 子代理返回【用户意图类】finding → 主会话与用户交互澄清，完成后再次派发子代理执行审查
- 子代理返回 3 轮 FAIL → 主会话上报用户处理
- 子代理执行失败或无法调起 → **【强制】先向用户明确告知**："子代理审查执行失败（原因：{具体错误}），将降级为主会话直接执行 design-doc-reviewer"，**然后**主会话降级直接调用 design-doc-reviewer Skill 执行

## 衔接豁免

- **`design_review` 关闭时**：跳过 Phase 10，Phase 9 通过后（如 `design_traceability` 开启）或 Phase 8 完成后（如 `design_traceability` 也关闭）直接进入 Phase 11。"禁止主会话直接执行"强制位随关闭豁免。
- **`design_traceability` 关闭但 `design_review` 开启时**：Phase 8 完成后直接进入 Phase 10，不经 Phase 9。

## 关闭语义

**执行计划不含 `design_review` 条目时**：跳过 design-doc-reviewer 审查，六维检测/九条宪法无人把关。关闭语义 = "已有外部审查或用户明确放弃文档审查"。

# TEMPLATE_JSONC replacement only; also apply the built-in registry and fixed-step changes.
# Do not replace the complete flow_config.py module with this file.

TEMPLATE_JSONC = """// ============================================================
// CoreSpec 通用流程编排框架 - 全局配置（JSONC：支持 // 行注释）
// 位置：~/.corespec/flow-config.json
// 说明：顶层按 skill 名分组。每个 core-* skill 只解析自己的命名空间。
//       某 skill 对象不存在 = 该 skill 全默认（内置步骤按各自默认值启停，无自定义步骤）。
//       修改后调用 main.py flow-config --json --skill <name> 重建执行计划。
// 完整指南：~/.corespec/flow-config-guide.md（或 main.py flow-config --guide）
// ============================================================

{
  "core-apply": {
    // ---- 内置步骤开关（true/false）----
    "version_check": true,  // Step 1 版本检查
    "show_progress": false,  // Step 8 展示当前进度（默认关闭）
    "skill_consumption": false, // Step 9 任务 Skill 准备与消费（默认关闭）
    "l4_review": true,      // Step 11 L4 实现追溯验证
    "code_review": true,    // Step 12 Code Review
    "unit_test": true,      // Step 13 单元测试（l5_coverage 依赖它，关闭则 L5 自动降级）
    "l5_coverage": true,     // Step 14 L5 UT 覆盖度验证
    "completion_report": true, // Step 15 完成或暂停时展示状态
    // ---- 自定义步骤示例（取消注释即启用；注意：最后一个有效键不可带尾逗号）----
    "judgment_ladder": {
      "type": "reference",
      "file": "references/judgment-ladder.md",
      "at": "pre-codegen"        // 编排点：pre-codegen / post-codegen / post-l4 / post-review / post-ut
    }
    // "compile": {
    //   "type": "skill",
    //   "skill": "my-compile-skill",
    //   "at": "post-codegen",
    //   "order": 1,
    //   "description": "编译项目代码"
    // },
    // "codebase_scan": {
    //   "type": "skill",
    //   "skill": "my-scan-skill",
    //   "at": "post-review",
    //   "run_mode": "subagent"     // direct（默认，当前会话）/ subagent（独立子代理）
    // }
  },
  // ---- 其他 core-* skill 的配置各自独立分组（未配置 = 全默认，互不影响）----
  // 启用命名空间时只去掉一层注释，并在其闭合 } 后加逗号以连接后续顶层键。
  // 保留内部自定义声明的注释；需要启用某声明时再取消其整块注释。
  // "core-design": {
  //   // ---- 内置步骤开关（true/false）----
  //   "version_check": true,       // Phase 1 版本检查
  //   "fetch_rules": true,         // Phase 2 多语言规范获取（B 档：只控 code-rule 拉取，不控 design-principles/design-views GATE）
  //   "read_similar": true,        // Phase 5 读取相似需求参考归档
  //   "expert_experience": true,   // Phase 7 准备已有项目经验及任务能力查找上下文（不独立拉取经验，纯增益）
  //   "skill_consumption": false, // Phase 9 任务 Skill 查找、确认、安装与关联（默认关闭）
  //   "design_traceability": true, // Phase 10 设计追溯验证（cross-doc-checker L2/L3，subagent 强制）
  //   "design_review": true,       // Phase 11 design-doc-reviewer 审查（subagent 强制）
  //   "cleanup": true              // Phase 12 清理临时文件
  //   // ---- 自定义步骤示例（取消注释即启用；at 取 core-design 编排点）----
  //   // "team_design_rules": {
  //   //   "type": "reference",
  //   //   "file": "references/team-design-rules.md",
  //   //   "at": "pre-generate"    // 编排点：post-rule-fetch / post-gather-context / post-code-understanding / pre-generate / post-generate / post-traceability / post-design-review / post-cleanup
  //   // }
  // }
  // "core-init": {
  //   // ---- 内置步骤开关（true/false）----
  //   "version_check": true,        // Step 0 版本检查
  //   "okf_knowledge_fetch": false,  // Step 4 拉取产品知识中心代码仓（asset/ 扁平到 docs/knowledge/产品名/）
  //   "multi_analysis": true,       // Step 5 多仓依赖分析（subagent）
  //   "check_sync": true,           // Step 6a 同步必要性检查
  //   "execute_sync": true          // Step 6b 代码仓逆向文档获取（依赖 check_sync，关闭 check_sync 时同步跳过）
  //   // ---- 自定义步骤示例（取消注释即启用；at 取 core-init 编排点）----
  //   // "spec_source": {
  //   //   "type": "reference",
  //   //   "file": "references/spec-source.md",
  //   //   "at": "pre-execute-sync"   // 编排点：post-init-structure / post-scan-language / post-multi-analysis / pre-execute-sync / post-execute-sync
  //   // }
  // }
  // "core-explore": {
  //   // ---- 内置步骤开关（true/false）----
  //   "version_check": true,      // Step 0 版本检查
  //   "req_refine": false,        // 阶段5.1.5 需求文档细化补全（默认关闭；启用后 step-4 解析设计文档自动降级、step-7 上下文补全读取源切到 refined 文档；产出 requirement.md + story.md 到 docs/.explore_context/req-refine/{需求ID}/；产出后下游 knowledge_precheck/brainstorming 自动豁免）
  //   "knowledge_precheck": true, // 阶段5.3 领域知识预澄清（双层语义：指令文件挂 ref_file 条件加载（references/knowledge-precheck.md），关闭时文件不加载、三条件检查点豁免；req_refine 产出时追加第四条件豁免）
  //   "brainstorming": true,      // 阶段5.4 需求澄清（双层语义：指令文件挂 ref_file 条件加载（references/requirement-clarification.md），关闭时文件不加载、七条件豁免、后处理降级；req_refine 产出时追加第八条件豁免）
  //   "find_similar": true,       // 阶段7 查找相似需求
  //   "l1_review": true,          // 阶段9 L1 需求完整性验证
  //   "explore_review": true,     // 阶段10 explore-doc-reviewer 审查
  //   "cleanup_temp": true        // 阶段11 清理临时文件
  //   // ---- 自定义步骤示例（取消注释即启用；at 取 core-explore 编排点）----
  //   // "team_rules": {
  //   //   "type": "reference",
  //   //   "file": "references/team-rules.md",
  //   //   "at": "pre-proposal"    // 编排点：pre-clarification / post-clarification / pre-proposal / post-proposal / pre-delta-spec / post-delta-spec / post-l1 / post-review / post-cleanup
  //   // }
  // }
  // "core-archive": {
  //   // ---- 内置步骤开关（true/false）----
  //   "version_check": true,    // Step 1 版本检查
  //   "core_verify": true,      // Step 4 core-verify 归档前验证（subagent 强制，UNDER_IMPL 阻塞 / DOC_STALE 交反刷）；多仓 M-0 替代
  //   "check_artifacts": true,  // Step 5 检查 artifact 完成状态
  //   "check_tasks": true,      // Step 6 检查 task 完成状态 + 消费 skipped-core-apply.json
  //   "backfill": true,         // Step 9 代码反刷（backfill-from-code）；多仓 M-1 子代理并行替代
  //   "spec_sync": true,        // Step 10 delta 合并到全量文档；多仓 M-2 子代理并行替代
  //   "show_summary": true,     // Step 12 展示归档摘要
  //   "push_mr": true           // Step 13 core-auto-git 推送 + 建 MR；多仓 M-4 逐仓替代
  //   // ---- 自定义步骤示例（取消注释即启用；at 取 core-archive 编排点）----
  //   // "archive_hook": {
  //   //   "type": "reference",
  //   //   "file": "references/archive-hook.md",
  //   //   "at": "pre-archive"    // 编排点：pre-verify / post-verify / pre-backfill / post-backfill / pre-spec-sync / post-spec-sync / pre-archive / post-archive / pre-push / post-push
  //   // }
  // }

  // ---- 全局默认测试策略（顶层键，不属任何 skill 命名空间）----
  // core-init 生成项目 docs/config.yaml 时参考此值；用户后续改项目级
  // config.yaml 则以项目级为准（core-design 生成 tasks.md 时项目级优先）。
  "test_strategy": "test-after"   // tdd / test-after，缺省 test-after
}
"""

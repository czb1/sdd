# Step 12: 单元测试环节（多仓模式指令）

> 本文件为可配置步骤 `unit_test` 的指令文件（多仓版）。仅在执行计划含 `key=unit_test` 条目时被 Read。
> 指令来源：`references/multi-repo.md` 的 **M-5**（多仓下单元测试的唯一执行权威，与 multi-repo.md 内容一致）。

## 多仓下的执行位置

多仓模式下，单元测试由 **M-5** 承担（替代单仓 Step 12 unit-test）。M-4（各仓 Code Review）完成后，主会话分派 M-5 子代理并行执行各仓单元测试：

- M-5: 各仓单元测试（subagent并行，替代UT环节）

## M-5 执行指令

**Replaces**: steps.md Step 10 unit-test（单仓步骤）
**Input**: 各仓代码文件、delta_test_design.md、tasks.md

**先读取 tasks.md 头部 `测试策略` 字段**判断执行序列（与单仓 Step 12 一致；差异仅在环节1 UT生成是否执行；环节2~5 两模式相同）：
- `test-after` / 无字段：环节1 UT生成 → 环节2 UT修复 → 环节3 覆盖率 → 环节4 断言 → 环节5 报告
- `tdd`：**跳过环节1（UT生成）**——每个任务的"编写失败的测试"已生成对应 TC 的测试，任务拆分保证全部 TC 已覆盖；执行 环节2 UT修复 → 环节3 覆盖率 → 环节4 断言 → 环节5 报告
  - 环节2 UT修复：处理编译/运行问题（测试已在任务内通过验证，此处为跨任务集成时的残余问题）——复用现有修复技能，断言失败时先裁决（实现错→回改实现；测试断言错→修测试；禁止篡改测试意图适配实现）
  - 环节3~5（覆盖率提升、断言审查、测试报告，Java 链路）与 test-after 相同

### 1. 对每个涉及仓启动子代理执行UT生成/修复

子代理任务描述模板：

```
你是仓 {repo} 的专属UT代理。请对 {repo} 仓执行单元测试生成和修复：

输入文件（必须全部读取）：

| # | 文件 | 路径 | 消费用途 |
|---|------|------|----------|
| 1 | delta_test_design.md | {repo}/docs/changes/<change>/delta_test_design.md | **核心输入**：UT代码必须覆盖其中定义的所有测试用例（TCxxx），验收标准为"生成的UT覆盖delta_test_design.md中所有测试用例" |
| 2 | tasks.md | {repo}/docs/changes/<change>/tasks.md | **头部测试策略字段**：判断 tdd / test-after 执行序列；**仅 test-after 时**读取代码生成任务的"编程语言"字段确定调用哪个UT生成技能（tdd 跳过UT生成，不读UT生成技能字段）；检查依赖任务是否已完成 |
| 3 | 执行计划片段 | {project_root}/docs/.flow_context/execution-plan-fragment-core-apply-{repo}.json | **编排输入**：本仓执行计划片段。post-ut 插槽条目在 UT 环节完成后执行；不在插槽中的编排点不执行 |

执行步骤：
1. 读取 delta_test_design.md 和 tasks.md（含头部测试策略字段）
2. 按测试策略判断执行序列：
   - `test-after` / 无字段：**环节1 UT生成执行**——根据代码生成任务的"编程语言"字段选择对应的UT技能链（按代码生成任务语言生成UT）：
   - `tdd`：**跳过环节1 UT生成**（每个任务的测试已在 Step 9/M-2 红-绿循环中手写并验证通过），直接进入环节2

   **UT生成技能映射**（5环节，对齐单仓模式；tdd 仅环节2~5 使用）：

   | 编程语言 | 环节1-UT生成 | 环节2-UT修复 | 环节3-覆盖率提升 | 环节4-断言审查 | 环节5-测试报告 |
   |----------|-------------|-------------|-----------------|---------------|---------------|
   | java | generate-java-ut | fix-java-ut | improve-java-ut-coverage | java-assertion-validity-review | java-test-report |
   | cpp/c/c++ | c-cpp-dt | c-cpp-dt-autofix | - | - | - |
   | go | go-ut | go-ut-compilation-execution-fixing | - | - | - |
   | python | python-ut | - | - | - | - |
   | js/ts/other | test-driven-development | - | - | - | - |

3. 按环节顺序执行（环节间串行，同环节内不同任务可并行）：
   - **环节1**: UT生成（仅 test-after）— 按代码生成任务的"编程语言"字段调用对应的UT生成技能，生成的UT必须覆盖delta_test_design.md中定义的TCxxx测试用例。tdd 模式跳过此环节
   - **环节2**: UT修复（仅Java/C/C++/Go）— 调用对应的UT修复技能，修复编译和运行错误（最多3轮）
   - **环节3**: 覆盖率提升（仅Java）— 调用improve-java-ut-coverage
   - **环节4**: 断言审查（仅Java）— 调用java-assertion-validity-review
   - **环节5**: 测试报告（仅Java）— 调用java-test-report
4. 3轮UT修复后仍有ERROR级问题 → 返回ESCALATE状态 + blocking_issues列表
5. **【强制】子代理必须在内部完成3轮UT修复循环后才返回结果** — 禁止返回fix_rounds<3的ESCALATE，主会话不会重新启动子代理执行修复
6. **【强制】修复轮次必须包含实际代码变更** — 如果某轮修复没有任何Edit/Write操作，该轮不计入fix_rounds，必须重新执行该轮
7. UT 环节完成后，执行执行计划片段（输入 #3）中 `orchestration_points.post-ut` 插槽条目：
   - `type=reference` → Read 条目 `file` 字段指令文件并执行
   - `type=skill` → 调用条目 `skill` 字段指定 skill（`run_mode=subagent` 时 spawn 独立子代理）
   - 插槽为空 → 跳过，不加载任何指令文件

当前变更：{change_name}
项目根目录：{project_root}
仓目录：{repo_path}

返回格式（必须包含修复过程记录）：
- 全部通过：status=PASSED, test_results=[...]
- 自动修复成功：status=FIXED, fixes_summary=[{round, errors_found, errors_fixed, code_changes_made}]
- 需要用户决策：status=ESCALATE, blocking_issues=[{id, description, severity, attempted_fixes}], fix_rounds=3
```

### 2. 汇总所有子代理结果，处理ESCALATE升级

- 子代理返回ESCALATE → 升级到用户决策（对齐通用规则"用户决策升级机制"：fix_rounds = 3 → 已尽力修复仍无法解决，升级；fix_rounds < 3 → 子代理逻辑异常，记录WARNING但仍升级，**禁止主会话重新启动子代理执行修复**）
- **【强制】禁止主会话将子代理返回的问题"记录后继续"**

**Output**: 各仓UT报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的UT已完成

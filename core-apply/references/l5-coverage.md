# Step 13: Gate-2 L5 UT覆盖度验证（单仓模式指令）

> 本文件为可配置步骤 `l5_coverage` 的指令文件（单仓版）。仅在执行计划含 `key=l5_coverage` 条目时被 Read。
> **依赖规则**：`l5_coverage` 依赖 `unit_test`。若 `unit_test` 关闭，本步骤自动降级，本文件不被 Read。

**先读取 tasks.md 头部 `测试策略` 字段**判断验证预期（主流程相同：调用 cross-doc-checker --layer L5 → 检查 CHECK-ID → 失败自动修复循环 → 通过后流程完成；差异仅在 TC-SEMANTIC-COVERAGE 的命中方式与修复动作）：
- `test-after` / 无字段：TC-SEMANTIC-COVERAGE 采用语义匹配——功能覆盖通过但缺 TC 编号注释降级 WARNING 不阻塞；修复时 TC 场景未被覆盖直接补充 UT 代码
- `tdd`：TC-SEMANTIC-COVERAGE 命中 ID-TRACEABLE 优先级1——任务内测试按 delta_test_design.md 的 TC 编号直接引用，不依赖语义匹配；修复时 TC 场景未被覆盖先回查对应任务红-绿实现

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，禁止主会话直接执行
**加载技能**: ["cross-doc-checker"]
**同步/异步**: sync

**【强制】进入此门控检查时，必须向用户输出：**
"## Step 13: L5 UT覆盖度验证 — UT代码已生成，正在验证UT与delta_test_design.md的覆盖度..."

**【强制】此门控检查是 Step 12（单元测试）完成后的必经验证。禁止跳过此步骤直接结束流程。**

**前置条件**：如果 `delta_test_design.md` 不存在，则跳过此门控检查，直接结束流程。

**【强制】禁止以环境限制为由跳过L5验证** — L5验证是**代码审查**（通过Grep/Read验证UT代码是否覆盖TC场景、断言是否一致、是否调用业务代码），不是编译运行UT获取覆盖率。Windows/Linux环境差异、无法编译UT、无法运行UT获取覆盖率数据等均不构成跳过L5验证的理由。cross-doc-checker的L5 CHECK-ID仅依赖Grep/Read/Glob工具，这些工具在任何环境下都可用。禁止以"Windows环境无法编译"、"需要Linux环境运行UT"等理由跳过或推迟L5验证。

子代理使用 Skill tool 调用 `cross-doc-checker`，传入 layer=L5：
```
Skill tool: cross-doc-checker <change-name> --layer L5
```

**【强制】必须使用Skill tool调用cross-doc-checker** — 禁止Agent自行用Grep/Read替代skill调用。Agent自行Grep比对无法覆盖cross-doc-checker的完整CHECK-ID集合和语义判断逻辑。
- **验证重点**：UT是否存在空壳/恒真断言（CHECK-R5-TESTSHELL）、delta_test_design.md场景是否被UT功能覆盖（CHECK-R13-TC-SEMANTIC-COVERAGE正向+反向）、UT断言是否与预期结果一致（CHECK-R13-TC-ASSERTION）、UT是否实际调用被测业务代码（CHECK-R13-TC-CALLTARGET）、业务代码公共接口是否有测试覆盖（CHECK-R13-PUBLIC-TESTED）
- **说明**：L5执行5项UT覆盖度与代码关联性相关CHECK-ID（含TESTSHELL测试空壳检测），TC-SEMANTIC-COVERAGE 的命中方式（语义匹配 / ID-TRACEABLE）按顶部测试策略分支执行
- **强制要求**：**不得自行执行Grep/Read绕过Skill tool做L5验证** — 必须且只能通过 Skill tool 调用 cross-doc-checker。自行执行的L5验证结果无效
- **结果校验**：Skill tool 执行完成后，必须检查输出中是否包含所有L5 CHECK-ID（CHECK-R5-TESTSHELL, CHECK-R13-TC-SEMANTIC-COVERAGE, CHECK-R13-TC-ASSERTION, CHECK-R13-TC-CALLTARGET, CHECK-R13-PUBLIC-TESTED）。缺少任何CHECK-ID的输出表示 cross-doc-checker 未完整执行，必须重新调用
- **失败处理**：UT覆盖度验证失败 → **必须自动修复**后重新执行L5验证
  - **自动修复循环（最多3轮）**：
    1. 读取cross-doc-checker输出的findings列表
    2. 按finding类型执行修复：
       - 【实现一致性类】TC场景未被UT覆盖（CHECK-R13-TC-SEMANTIC-COVERAGE FAIL）→ 补充UT代码覆盖缺失场景；**tdd 模式下**按顶部测试策略分支先回查对应任务的红-绿实现（如 TC 编号引用缺失则补 TC 编号注释，如测试确实缺失则回该任务补写）
       - 【代码质量类】UT空壳或恒真断言（CHECK-R5-TESTSHELL WARNING）→ 补充实际测试逻辑或有效断言
       - 【代码质量类】UT仅操作mock未调用业务代码（CHECK-R13-TC-CALLTARGET FAIL）→ 修改UT使其实际调用业务代码
       - 【实现一致性类】UT断言与预期结果不一致（CHECK-R13-TC-ASSERTION FAIL）→ 修正UT断言使其与delta_test_design.md一致
       - 【实现一致性类】业务代码public函数无测试覆盖（CHECK-R13-PUBLIC-TESTED FAIL）→ 为该函数生成UT
       - 【文档保真类】设计文档中引用的函数名与实际代码不一致（如设计写validateScaleRequest但实际是doCustomSelectorScale）→ **以实际代码为准更新设计文档**
    3. 修复完成后，**必须重新调用** Skill tool: cross-doc-checker <change-name> --layer L5
    4. 如果3轮后仍有FAIL → 暂停流程，返回主会话由主会话上报用户处理
  - **WARNING级finding处理**：WARNING不阻塞流程，但**应当修复**。修复后无需重新执行L5验证
  - **禁止**：发现FAIL后仅报告问题不修复，或跳过修复直接标记完成
- **通过后**：所有L5 CHECK-ID通过 → core-apply流程完成

**主会话后处理**（子代理返回后执行）：
- 子代理返回L5验证通过 → core-apply流程完成
- 子代理返回3轮FAIL → 主会话上报用户处理
- 子代理执行失败 → 主会话直接调用 cross-doc-checker Skill 执行（降级策略）

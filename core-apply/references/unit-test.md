# Step 12: 单元测试环节（单仓模式指令）

> 本文件为可配置步骤 `unit_test` 的指令文件（单仓版）。仅在执行计划含 `key=unit_test` 条目时被 Read。

**UT 范围**：代码生成任务（Step 9）产出的代码文件，按 delta_test_design.md 定义覆盖。

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，禁止主会话直接执行
**加载技能**: ["generate-java-ut", "fix-java-ut", "improve-java-ut-coverage", "java-assertion-validity-review", "java-test-report", "c-cpp-dt", "c-cpp-dt-autofix", "go-ut", "go-ut-compilation-execution-fixing", "test-driven-development"]
**同步/异步**: sync

**重要约束**：所有 UT 生成任务**必须**先读取 `delta_test_design.md`，根据其中定义的测试用例（TCxxx）生成对应的 UT 代码。验收标准为"生成的UT必须覆盖delta_test_design.md中定义的所有测试用例"。

**先读取 tasks.md 头部 `测试策略` 字段**判断执行序列（差异仅在环节1 UT生成是否执行；环节2~5 两模式相同）：
- `test-after` / 无字段：环节1 UT生成 → 环节2 UT修复 → 环节3 覆盖率 → 环节4 断言 → 环节5 报告（按下方 执行顺序 全流程执行）
- `tdd`：**跳过环节1（UT生成）**——每个任务的"编写失败的测试"已生成对应 TC 的测试，任务拆分保证全部 TC 已覆盖；执行 环节2 UT修复 → 环节3 覆盖率 → 环节4 断言 → 环节5 报告
  - 环节2 UT修复：处理编译/运行问题（测试已在任务内通过验证，此处为跨任务集成时的残余问题）——复用现有修复技能（fix-java-ut / c-cpp-dt-autofix / go-ut-compilation-execution-fixing），本体不改；断言失败时先裁决：实现错→回改实现；测试断言错→修测试；禁止篡改测试意图适配实现
  - 环节3~5（覆盖率提升、断言审查、测试报告，Java 链路）与 test-after 相同

**执行顺序**：

1. **环节1: UT生成** (`### 4.1 UT生成`)
   - 并行执行所有 generate-java-ut / c-cpp-dt / go-ut / test-driven-development 任务

2. **环节2: UT修复** (`### 4.2 UT修复`)
   - 仅 Java/C/C++/Go 有此环节
   - 并行执行所有 fix-java-ut / c-cpp-dt-autofix / go-ut-compilation-execution-fixing 任务

3. **环节3: 覆盖率提升** (`### 4.3 覆盖率提升`)
   - 仅 Java 有此环节
   - 执行 improve-java-ut-coverage 任务

4. **环节4: 断言审查** (`### 4.4 断言审查`)
   - 仅 Java 有此环节
   - 执行 java-assertion-validity-review 任务

5. **环节5: 测试报告** (`### 4.5 测试报告`)
   - 仅 Java 有此环节
   - 执行 java-test-report 任务

**UT生成技能映射**：

| 编程语言 | 环节1-UT生成 | 环节2-UT修复 | 环节3-覆盖率提升 | 环节4-断言审查 | 环节5-测试报告 |
|----------|-------------|-------------|-----------------|---------------|---------------|
| java | generate-java-ut | fix-java-ut | improve-java-ut-coverage | java-assertion-validity-review | java-test-report |
| cpp/c/c++ | c-cpp-dt | c-cpp-dt-autofix | - | - | - |
| go | go-ut | go-ut-compilation-execution-fixing | - | - | - |
| python/js/ts/other | test-driven-development | - | - | - | - |

**主会话后处理**（子代理返回后执行）：
- 子代理返回 UT 全部完成 → 进入 Step 13（L5门控）
- 子代理执行失败 → 主会话直接执行单元测试环节（降级策略）

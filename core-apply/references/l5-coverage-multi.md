# Step 14: Gate-2 L5 UT覆盖度验证（多仓模式指令）

> 本文件为可配置步骤 `l5_coverage` 的指令文件（多仓版）。仅在执行计划含 `key=l5_coverage` 条目时被 Read。
> **依赖规则**：`l5_coverage` 依赖 `unit_test`。若 `unit_test` 关闭，本步骤自动降级，本文件不被 Read。
> 指令来源：`references/multi-repo.md` 的 **M-6**（多仓下 L5 验证的唯一执行权威，与 multi-repo.md 内容一致）。

**先读取 tasks.md 头部 `测试策略` 字段**判断验证预期（与单仓 l5-coverage.md 一致；主流程相同：调用 cross-doc-checker --layer L5 → 检查 CHECK-ID → 失败自动修复循环 → 通过后进入 M-7；差异仅在 TC-SEMANTIC-COVERAGE 的命中方式与修复动作）：
- `test-after` / 无字段：TC-SEMANTIC-COVERAGE 采用语义匹配——功能覆盖通过但缺 TC 编号注释降级 WARNING 不阻塞；修复时 TC 场景未被覆盖直接补充 UT 代码
- `tdd`：TC-SEMANTIC-COVERAGE 命中 ID-TRACEABLE 优先级1——任务内测试按 delta_test_design.md 的 TC 编号直接引用，不依赖语义匹配；修复时 TC 场景未被覆盖先回查对应任务红-绿实现

## 多仓下的执行位置

多仓模式下，L5 验证由 **M-6** 承担（替代单仓 Step 14 gate-2-coverage）。M-5（各仓单元测试）完成后，主会话分派 M-6 子代理并行执行各仓 L5 验证：

- M-6: 各仓L5 UT覆盖度验证（subagent并行，替代门控2 L5）

## M-6 执行指令

**Replaces**: SKILL.md Step 14 gate-2-coverage（单仓步骤）
**Input**: 各仓UT代码、delta_test_design.md、业务代码头文件、tasks.md

### 1. 对每个涉及仓启动子代理执行L5验证

子代理任务描述模板：

```
你是仓 {repo} 的专属L5验证代理。请对 {repo} 仓执行 L5 UT覆盖度验证：

输入文件（必须全部读取后再开始执行步骤）：

| # | 文件 | 路径 | 消费用途 |
|---|------|------|----------|
| 1 | delta_test_design.md | {repo_path}/docs/changes/{change_name}/delta_test_design.md | **核心输入**：L5验证的基准文档，cross-doc-checker将检查UT覆盖度是否满足其中定义的测试用例要求 |
| 2 | UT代码文件 | {repo_path}/test/ 等测试目录 | **核心输入**：L5验证的目标，检查UT代码是否覆盖了delta_test_design中的所有测试用例 |
| 3 | tasks.md | {repo_path}/docs/changes/{change_name}/tasks.md | **核心输入**：读取已完成（`- [x]`）的代码生成任务，提取"编程语言"字段用于选择UT生成技能；提取"生成文件"字段定位增量代码 |
| 4 | 业务代码头文件 | tasks.md中代码生成任务的生成文件 | **修复必需输入**：修复L5 findings需要理解业务代码接口定义，用于编写正确的UT代码 |

执行步骤：
1. 使用 Skill tool 调用 cross-doc-checker <change-name> --layer L5（禁止自行用Grep/Read替代skill调用）
2. 读取审查输出的findings列表
3. 如果存在ERROR级finding，**【强制】执行3轮自动修复循环**（禁止跳过，禁止直接报告问题而不修复）：

   **修复 = 编写/修改UT代码**，不是"验证发现"或"确认问题"。每一轮修复必须产生实际的代码变更（Edit/Write操作），不允许仅读取文件确认问题后进入下一轮。

   修复轮次 = 0
   while 存在ERROR级finding AND 修复轮次 < 3:
       修复轮次 += 1
       输出 "修复轮次 {修复轮次}/3：发现 {ERROR数量} 个ERROR"
       **按finding类型执行修复**（对齐单仓SKILL.md门控2修复逻辑；**tdd 模式下**按顶部测试策略分支，"TC场景未被UT覆盖"先回查对应任务的红-绿实现——如 TC 编号引用缺失则补 TC 编号注释，如测试确实缺失则回该任务补写）：

       | finding类型 | 对应CHECK-ID | 修复方式 |
       |------------|-------------|----------|
       | TC场景未被UT覆盖 | CHECK-R13-TC-SEMANTIC-COVERAGE | **补充UT代码**覆盖缺失场景：读取delta_test_design.md中缺失TC的场景描述和预期结果，使用对应编程语言的UT生成技能（见下方映射表）生成UT函数 |
       | UT空壳或恒真断言 | CHECK-R5-TESTSHELL | **补充实际测试逻辑**：在空壳UT函数中添加有效断言和测试逻辑（参考delta_test_design.md预期结果） |
       | UT仅操作mock未调用业务代码 | CHECK-R13-TC-CALLTARGET | **修改UT调用业务代码**：将UT函数中仅操作mock变量的逻辑改为调用实际业务函数/宏（通过#include业务头文件 + 直接调用业务函数） |
       | UT断言与预期结果不一致 | CHECK-R13-TC-ASSERTION | **修正UT断言**：将UT断言修改为与delta_test_design.md预期结果一致 |
       | 业务代码public函数无测试覆盖 | CHECK-R13-PUBLIC-TESTED | **为该函数生成UT**：使用对应编程语言的UT生成技能为未覆盖的public函数编写UT |
       | 设计文档引用的函数名与实际代码不一致 | 各CHECK-ID | **以实际代码为准**，更新delta_test_design.md中的函数名引用 |

       **UT生成技能映射**（用于补充/生成UT代码时选择技能）：

       | 编程语言 | UT生成技能 |
       |----------|-----------|
       | java | generate-java-ut |
       | cpp/c/c++ | c-cpp-dt |
       | go | go-ut |
       | python | python-ut |
       | js/ts/other | test-driven-development |

       修复完成后重新调用 Skill tool: cross-doc-checker <change-name> --layer L5
       读取新的findings列表
4. 3轮后仍有ERROR级finding → 返回ESCALATE状态 + blocking_issues列表
5. **【强制】禁止发现ERROR后直接返回ESCALATE而不执行修复循环**
6. **【强制】子代理必须在内部完成3轮修复循环后才返回结果** — 禁止返回fix_rounds<3的ESCALATE，主会话不会重新启动子代理执行修复
7. **【强制】修复轮次必须包含实际代码变更** — 如果某轮修复没有任何Edit/Write操作，该轮不计入fix_rounds，必须重新执行该轮

当前变更：{change_name}
项目根目录：{project_root}
仓目录：{repo_path}

返回格式（必须包含修复过程记录）：
- 全部通过：status=PASSED, findings=[...], fix_rounds=0
- 自动修复成功：status=FIXED, fixes_summary=[{round, errors_found, errors_fixed, code_changes_made}], fix_rounds=N
- 需要用户决策：status=ESCALATE, blocking_issues=[{id, description, severity, attempted_fixes}], fix_rounds=3
```

### 2. 汇总所有子代理结果，处理ESCALATE升级

- 子代理返回ESCALATE → 升级到用户决策（对齐通用规则"用户决策升级机制"：fix_rounds = 3 → 已尽力修复仍无法解决，升级；fix_rounds < 3 → 子代理逻辑异常，记录WARNING但仍升级，**禁止主会话重新启动子代理执行修复**）
- **【强制】禁止主会话将子代理返回的问题"记录后继续"**

### 3. 阶段间同步

- **所有仓L5通过后进入on-completion**

**Output**: 各仓L5验证报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的L5验证已完成

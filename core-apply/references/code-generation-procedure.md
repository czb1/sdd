# Step 9: 代码生成任务（指令文件）

> 本文件为 Step 9 代码生成环节的指令文件（**单仓专用**），**无条件加载**（GATE:REF 标记，同 Step 7 code-gen-principles.md 模式）。Step 9 执行每个代码生成任务时按本文件流程执行。

## Step 9 主循环

> **测试策略**：进入任务循环前，读取 tasks.md 头部的 `测试策略` 字段（tdd / test-after；如果字段不存在则默认为 test-after 策略）。

**【强制】Step 9 循环对象边界 —— tasks.md 章节归属映射**：

Step 9 的循环对象**仅限** tasks.md 的 `## 代码生成任务` 章节（1.x 任务）。tasks.md 其余章节**不属于** Step 9 循环对象，对应可配置步骤关闭时**禁止**在 Step 9 循环中执行：

| tasks.md 章节 | 任务编号 | 归属步骤 | 对应可配置键 | 关闭时行为 |
|---------------|---------|---------|-------------|-----------|
| `## 代码生成任务` | 1.x | **Step 9**（本步骤） | —（无条件加载） | 不适用——Step 9 是本循环本体 |
| `## Code Review 任务` | 2.x | Step 11 | `code_review` | 执行计划 steps 数组**不含** `config_key=code_review` 条目 → **禁止在 Step 9 循环中执行 2.x 任务**（规范检查/内存安全检查），整章节跳过 |
| `## 单元测试任务` | 3.x | Step 12 | `unit_test` | 执行计划 steps 数组**不含** `config_key=unit_test` 条目 → **禁止在 Step 9 循环中执行 3.x 任务**（UT生成/修复/覆盖率/断言/报告），整章节跳过 |

- **判定依据**：`docs/.flow_context/execution-plan-core-apply.json` 的 `steps` 数组。含对应 `config_key`（`type=built_in`，`enabled=true`）条目 → 该章节任务由对应可配置步骤（Step 11/12）在其指令文件中执行，**不是 Step 9 循环对象**；不含 → 该章节整体跳过（指令文件不 Read，章节任务亦不执行）
- **Step 9 循环内禁止**：执行 `## Code Review 任务` / `## 单元测试任务` 章节的任何 `- [ ]` 任务（包括但不限于 codecheck/cwd-audit/UT 生成等）
- **Step 9 无待办**（1.x 全部 `- [x]`）且 Step 10~14 对应可配置步骤关闭 → 直接进入下一步/结束流程，**不得**将 2.x/3.x 未完成任务作为 Step 9 循环对象执行

For each pending task in `## 代码生成任务` section:
1. **针对当前任务进行代码理解**（详见下方 9.1）
2. **解析设计锚点**（详见下方 9.2）
3. **分阶段展示设计信息**（P0 → P1 → P2，详见下方 9.3）
4. **代码生成原则自检**（对照 code-gen-principles.md C-1~C-15，详见下方 9.4）
5. 执行代码生成（详见下方 9.5；测试策略为 `test-after` 时，按照9.5.1进行执行，否则按照9.5.2执行）
6. 标记任务完成: `- [ ]` → `- [x]`
7. Continue to next task

### 9.1 代码理解

针对当前任务，有指向性地理解相关代码。不同于统一查看，任务级代码理解：
- 结合具体任务需求，只查看当前任务相关的代码
- 在不了解任务的情况下盲目查看全部代码效率低下
- 看完即用，记忆更清晰，减少上下文浪费

**9.1.1 尝试调用 CodeBase 工具**

**统一尝试调用策略**：
- 无论 OpenCode 还是 ClaudeCode，都**先尝试调用** CodeBase 工具
- 根据调用结果判断是否可用：**能获取到有效数据视为可用，否则视为不可用**
- 这样可以兼容后续 ClaudeCode 可能支持 CodeBase 的情况

**调用示例**（具体调用方式由 Agent 自行判断）：
- 尝试调用 `GetRemoteCallChain` 追溯当前任务涉及代码的调用链
- 尝试调用 `CodeSemanticSearch` 语义搜索当前任务相关实现
- 如果返回有效结果 → 继续使用
- 如果返回空结果或报错 → 回退到 read/grep/glob

**建议优先级**：

1. **GetRemoteCallChain** — 追溯任务代码的调用链
   - 参数：file_path="任务相关文件", method_name="核心方法", depth=2
   - 目的：理解任务代码的上下游依赖

2. **CodeSemanticSearch** — 语义搜索相关实现
   - 参数：query="任务功能描述（英文）"
   - 目的：定位相关代码文件

3. **GetFeatureTree** — 理解任务所属模块结构
   - 参数：label_detailed=true
   - 目的：了解模块的整体结构

**三状态判断**：
| 状态 | 条件 | 动作 |
|------|------|------|
| present | CodeBase 可用且有数据 | 使用 CodeBase 结果 |
| missing | CodeBase 可用但无数据 | 回退到 read/grep/glob |
| not_installed | CodeBase 工具不可用 | 直接使用 read/grep/glob |

**9.1.2 回退到传统工具（必须）**

**当 CodeBase 不可用或无结果时，使用以下替代**：

| CodeBase 工具 | 降级替代工具 | 使用方式 |
|---------------|--------------|----------|
| GetRemoteCallChain | grep + read | 多轮 grep 追溯调用关系 |
| CodeSemanticSearch | grep | `grep -r "关键词"` 定位文件 |
| GetFeatureTree | glob + grep | `glob "**/module/**/*.py"` + 分析 |

**9.1.3 必须通过 read 验证**

**验证要求**：
- 无论使用哪种工具，**最终必须通过 read 实际读取代码进行验证**
- CodeBase 结果只是参考，必须实际读取代码确认实现细节
- 确保理解与实际代码一致后再进行实现

### 9.2 锚点解析

```markdown
# 从任务的"设计锚点"字段解析锚点
设计锚点: #3.1 #2.2 #1.1:约束 #1.2:证据驱动 #5.x:审查流程

# 解析结果分类
- 章节锚点: #3.1, #2.2
- 关键词锚点: #1.1:约束, #1.2:证据驱动
- 通配符锚点: #5.x:审查流程 → 展开为 #5.1, #5.2, #5.3 等
```

### 9.3 分阶段展示设计信息

**P0 必须参考**（第一阶段展示）：

```
Working on task 1.1: explore-doc-reviewer Skill

【P0 必须参考 - 设计锚点解析结果】

📌 详细设计章节：
   #3.1 → 3.1 explore-doc-reviewer Skill 设计

📌 架构模块划分：
   #2.2 → 2.2 模块划分

请基于以上设计信息实现当前任务。
```

**P1 应当参考**（第二阶段展示）：

```
【P1 应当参考 - 设计约束与原则】

📌 设计约束（#1.1:约束）：
   - 新增Skill必须遵循现有Skill接口规范
   - 审查规则必须支持配置化
   - design-doc-reviewer审查不影响现有命令流程兼容

📌 设计原则（#1.2:证据驱动）：
   - 任何审查结果必须附带文件路径+行号

📌 设计原则（#1.2:不信任）：
   - 任何检测结果必须可通过代码Grep验证
```

**P2 建议参考**（第三阶段展示）：

```
【P2 建议参考 - 核心流程】

📌 审查流程（#5.x:审查流程）：
   详见 delta_design.md 5.1 节完整审查流程时序图

📌 TDD强制流程（#5.x:TDD强制流程）：
   详见 delta_design.md 5.1.2 节 TDD强制流程
```

**锚点召回优先级**：

| 优先级 | 锚点类型 | 强制参考 | 展示阶段 |
|--------|---------|---------|---------|
| P0 | `#X.X` 章节锚点 | 必须参考 | 第一阶段 |
| P0 | `#2.1` `#2.2` 架构锚点 | 必须参考 | 第一阶段 |
| P1 | `#1.1:约束` 约束锚点 | 必须参考 | 第二阶段 |
| P1 | `#1.2:原则名` 原则锚点 | 必须参考 | 第二阶段 |
| P2 | `#4.x:流程名` 流程锚点 | 建议参考 | 第三阶段 |

### 9.3.5 编排点插槽 pre-codegen（task 级，条件执行）

查执行计划 `execution-plan-core-apply.json` 的 `orchestration_points` 对象中 `pre-codegen` 插槽数组：
- **存在条目** → 按条目执行（reference 型：Read 该条目 `file` 指定的指令文件，按其中指令决策；skill 型：调用对应 skill）
- **不存在** → 直接进入 9.4（指令文件不加载，内容不进上下文）

### 9.4 代码生成原则自检

基于 Step 7 GATE 加载的 `code-gen-principles.md`，在执行代码生成前对每个任务进行原则自检：

**必检项（每个任务）**：
- C-1: 当前任务是修改现有文件还是新增文件？如果是新增，是否已论证现有文件无法扩展？
- C-5: 是否已读取并理解现有代码的入口方法、调用链、数据流？
- C-7: 是否已确认增量代码的插入点？
- C-8: 生成代码的函数是否不超过50行、行宽不超过120字符、圈复杂度不超过3？
- C-12: 生成后是否检查冗余空行/import/变量/无用方法？

**条件检项（按触发条件）**：
- C-2: 涉及已有结构体/方法修改时——是否优先在现有结构体中增加字段/在现有方法中增加逻辑分支？
- C-3: 是否搜索项目已有同类实现，避免重复？
- C-4: 新增类/文件时——该类的职责是什么？项目中是否有类似职责的文件？
- C-9: 每个import是否已验证存在和可访问性？
- C-10: 是否新增了入口点？设计文档是否有对应描述？
- C-11: 是否使用了高危API？是否保留了原始许可证声明？
- C-13: 代码中的日期是否为当前真实日期？
- C-14: 生成的方法/函数是否可被调用方触达？是否有死循环？
- C-15: 修改现有代码时，是否先理解原有逻辑？

### 9.5 执行代码生成

向 Agent 展示完整的召回信息并完成原则自检后，执行代码生成。

**Pause if:**
- Task is unclear → ask for clarification
- Implementation reveals a design issue → suggest updating artifacts
- Error or blocker encountered → report and wait for guidance
- User interrupts

#### 9.5.1 test-after（默认）

> **分支选择**：本节与 9.5.2 互斥。tasks.md 头部 `测试策略` 字段为 `test-after` 或字段不存在时执行本节；为 `tdd` 时跳过本节，执行 9.5.2。

执行代码生成任务

#### 9.5.2 tdd（测试先行）

> **分支选择**：本节与 9.5.1 互斥。tasks.md 头部 `测试策略` 字段为 `tdd` 时执行本节；为 `test-after` 或字段不存在时跳过本节，执行 9.5.1。

按 `references/red-green-tdd.md` 红-绿循环执行（加载 test-driven-development 技能，动态路径解析参见 SKILL.md Reference文件路径解析章节）：
0. **测试工程初始化**（仅第一个任务前执行一次）：按 `red-green-tdd.md`"测试工程初始化"章节，检查并创建测试目录/构建文件，确保测试命令可运行
1. 按任务"覆盖用例"字段，参考 delta_test_design.md 对应 TC，手写测试到任务指定的测试文件路径
2. 运行测试命令，确认测试因功能缺失失败（红灯，禁止跳过）
3. 实现最少代码
4. 重跑测试命令，确认全部通过（绿灯）；编译失败（代码问题）→ 修复后重编直到通过；环境不允许（找不到编译器/命令、头文件缺失 >5 个等平台不支持）→ 放弃编译，将当前代码视作最终产物，记录原因后标记完成

**纪律**：未确认测试失败不写实现代码；测试通过但未确认过失败 = 无效验证；断言失败先裁决"实现错还是断言错"（依据 delta_test_design.md 预期），禁止为通过而篡改测试意图。
**前置条件**：测试工程已初始化（见 9.5.2 步骤 0）。

任务按以下步骤严格顺序执行（关键步骤间有门控检查）：
1. **Step 9 — 代码生成任务**: 先执行 "## 代码生成任务" 下的所有任务（**仅本章节**；"## Code Review 任务"/"## 单元测试任务" 章节分别属 Step 11/Step 12，见上方章节归属映射，**禁止**在本步执行）
2. **编排点 post-codegen（change 级，条件执行）**: Step 9 之后、Step 10 之前。查执行计划 `orchestration_points` 对象的 `post-codegen` 插槽：存在条目 → 按条目执行（reference 型 Read 指令文件 / skill 型调用 skill）；不存在 → 直接进入 Step 10
3. **Step 10 — 门控检查1 L4 实现追溯验证**: 代码生成完成后、进入 Code Review 前，**必须立即**执行
4. **编排点 post-l4（change 级，条件执行）**: Step 10 之后、Step 11 之前。存在 `post-l4` 插槽条目 → 按条目执行；不存在 → 直接进入 Step 11
5. **Step 11 — Code Review 任务**: L4 验证通过后，所有语言执行规范检查，C/C++/Java/Python/Go 额外执行内存安全检查（执行 tasks.md "## Code Review 任务" 章节 2.x）
6. **编排点 post-review（change 级，条件执行）**: Step 11 之后、Step 12 之前。存在 `post-review` 插槽条目 → 按条目执行；不存在 → 直接进入 Step 12
7. **Step 12 — 单元测试任务**: Code Review 完成后，按环节分组执行 "## 单元测试任务" 下的所有任务（tasks.md 3.x）
8. **编排点 post-ut（change 级，条件执行）**: Step 12 之后、Step 13 之前。存在 `post-ut` 插槽条目 → 按条目执行；不存在 → 直接进入 Step 13
9. **Step 13 — 门控检查2 L5 UT覆盖度验证**: UT 生成完成后，**必须立即**执行UT与delta_test_design.md的覆盖度验证

**编排点通用判断**（5 个插槽统一规则）：查 `docs/.flow_context/execution-plan-core-apply.json` 的 `orchestration_points` 对象中对应插槽（`pre-codegen`/`post-codegen`/`post-l4`/`post-review`/`post-ut`）数组是否有条目。有条目 → 按条目 `type` 执行（`reference`：Read `file` 字段指令文件并按其中指令执行；`skill`：调用 `skill` 字段指定的 skill，`run_mode=subagent` 时 spawn 独立子代理执行）；无条目 → 直接进入下一步，指令文件不加载。

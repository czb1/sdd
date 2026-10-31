# Step 12: Code Review（单仓模式指令）

> 本文件为可配置步骤 `code_review` 的指令文件（单仓版）。仅在执行计划含 `key=code_review` 条目时被 Read。

**检查范围**：代码生成任务（Step 10）产出的变更文件（增量，禁止全量扫描）。

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，禁止主会话直接执行
**加载技能**: ["codecheck-for-cleancode", "cwd-audit"]
**同步/异步**: sync

根据编程语言选择对应的代码检视技能：

| 编程语言 | 规范检查 | 内存安全检查 |
|----------|---------|-------------|
| cpp/c/c++/java/python/go | `codecheck-for-cleancode` | `cwd-audit`（检测+修复） |
| javascript/typescript/other | `codecheck-for-cleancode` | 跳过 |

#### 11.1 规范加载 -- 筛选当前实现相关的规范内容

11.1.1 **筛选规范目录**
从 `docs/rule_index.md` 读取的规范目录树，识别适合当前阶段生成的代码的目录条目：

**筛选过程分为两步**：
1. 根据当前需求涉及的编程语言，只处理对应语言下的目录条目。
2. 从对应语言的目录中，挑选与代码实现细节、语法规则、编码格式相关的目录。

**【强制要求】**
- 不得选择当前需求未涉及语言的规范目录。
- 不得将不同语言的目录合并到同一列表中。
- 必须保持以语言为维度的独立目录列表。
- 只选择与 apply 阶段相关的目录：适用于具体代码实现、语法细节、编码格式、代码生成或局部实现检查的目录。
- 必须从`docs/rule_index.md`原始目录条目中选择，不得自行编造、改写或补充目录名称。
- 目录名称必须完整保留，不得只传递末级目录名称。
- 若某种相关语言下没有合适的 Apply 编码规范目录，则该语言对应的目录列表返回空数组。

Apply 阶段 通常可关注以下类型的规范：
- 具体语法规则与语言特性使用
- 命名格式、缩进、空格等代码风格
- API 具体调用方式
- 函数/方法的实现规范
- 异常捕获与处理的具体写法
- 注释规范与文档字符串
- 代码组织结构（文件/包/模块）
- 变量声明与作用域规则
- 类/接口的具体实现方式
- 代码生成、模板使用

不属于 Apply 阶段筛选范围：
- 架构层面的模块划分（Design 阶段已完成）
- 高层设计原则（如设计模式选择、架构决策）
- 整体职责划分（Apply 阶段主要执行具体实现）

例如，`docs/rule_index.md` 内容包含：
```markdown

{
  "python": [
    "华为 CleanCode Python 核心原则/核心设计原则/可读性与可维护性",
    "华为 CleanCode Python 核心原则/核心设计原则/安全性与防御式编程",
    "华为 CleanCode Python 核心原则/规则级别",
    "云核心网产品工程与IT装备部Python规范/编码风格/命名规则"
  ],
  "cpp": [
    "华为 CleanCode C++ 核心原则/架构与模块设计",
    "华为 CleanCode C++ 编码规范/格式与排版"
  ]
}
```

假设当前需求仅涉及 Python，则筛选结果可以是：
```json
{
  "python": [
    "云核心网产品工程与IT装备部Python规范/编码风格/命名规则"
  ]
}
```
不得选择：

```
    "华为 CleanCode Python 核心原则/核心设计原则/可读性与可维护性",
    "华为 CleanCode Python 核心原则/核心设计原则/安全性与防御式编程",
```

因为这些目录与当前 Apply 阶段的代码实现检查相关性底。

11.1.2 **获取具体规范内容**
将 3.0.1 步骤筛选出的目录，以json格式，按照语言分别传递给 `code-rule-content` skill，获取对应规范内容。

Invoke `code-rule-content` skill:

输入必须保持多语言独立，例如：
```json
{
  "python": [
    "云核心网产品工程与IT装备部Python规范/编码风格/命名规则"
  ],
  "cpp": [
      "华为 CleanCode C++ 编码规范/格式与排版"
  ]
}
```

**【强制要求】**

- 每种语言只传递该语言对应的目录。
- 不得将 Python、Java、C++ 等不同语言目录混合传递。
- 不得传递空目录、缩写目录或自行推测的目录。
- 必须使用 3.0.1 返回的目录名称。

`code-rule-content` 返回结果统一按语言组织，例如：
```json
{
  "python": "### 可读性与可维护性\n- 使用具有明确含义的标识符\n- 公共函数必须编写 Docstring\n",
  "cpp": "### 特殊成员函数\n- 类成员变量必须显式初始化\n- 单参数构造函数声明为 explicit\n # Cpp规范"
}
```
Agent 必须统一理解为：
> 当前需求的**语言级 Apply 规范集合（`language-specific Apply specifications`）**。

后续代码规范检查过程中以这里的输出作为检视标准。

#### 11.2 规范检查（所有语言）

调用 `codecheck-for-cleancode` 技能进行编码规范检查与修复。

**必须先检查 CodeCheckCLI 是否已安装**：在执行任何规范检查操作之前，**必须**先执行 `codecheck --version` 验证安装状态。如果命令执行失败（返回非0或提示"不是内部或外部命令"），**必须立即按照 `codecheck-for-cleancode` 技能的"兜底策略（自动安装）"章节执行安装**，包括：检测 Node.js → 配置 npm 仓库 → 安装 CodeCheckCLI → 验证安装。**严禁在未安装 CodeCheckCLI 的情况下跳过规范检查**，安装失败则分析安装失败的原因（如网络问题、Node.js 版本不兼容、npm 仓库不可达等）并反馈用户。

**检查范围**：使用代码生成任务中涉及的变更文件，通过 `--files` 参数传入。

**规范检查流程**:
1. **规范内容加载与预处理** (`11.1 规范加载`)
- 从 `docs/rule_index.md` 读取规范目录树
- 根据当前需求的编程语言，筛选 Apply 阶段相关的规范目录
- 调用 `code-rule-content` skill 获取具体规范内容
- 将获取的规范内容作为 检视标准 传递给后续检查流程

2. **pre-ai-fix 阶段** (`11.2 规范检查`)
   - 收集代码生成任务中变更的文件列表
   - 调用 `codecheck-for-cleancode` 技能的增量检查+修复流程（参考 `assets/increcheck-fix.md`）
   - 执行 pre-ai-fix：
     ```bash
     python scripts/increcheck_and_fix_workflow.py --working-dir <project_root> --files <变更文件列表> --phase pre --check-type incre
     ```
   - 读取 `.codecheckcli/codecheck-result.json` 判断是否有告警：
     - **无告警**: 标记 11.2 完成，进入下一环节（C/C++/Java/Python/Go 进入 11.3 内存安全检查，其他语言完成 Code Review 进入单元测试环节）
     - **有告警**: 进入 AI 修复

3. **AI 修复**（基于规范内容检视 + 修改)
   - 参考 `codecheck-for-cleancode` 技能的 `assets/ai-fix.md` 执行 AI 修复
   - 主要步骤：黑名单过滤 → 报告拆分 → 并行 AI 修复子 Agent → 验证

   - 检视阶段：
     - 将 11.1 加载的规范内容作为检视依据
     - 逐条对照规范内容，检查变更文件中的代码是否符合规范
     - 识别不符合规范的代码位置和具体问题
     - 生成问题清单（包括：违规位置、违反的规范条目、建议修改方案）
   - 修改阶段:
     - 参考 `codecheck-for-cleancode` 技能的 `assets/ai-fix.md` 执行 AI 修复
     - 主要步骤：黑名单过滤 → 报告拆分 → 并行 AI 修复子 Agent → 验证

4. **post-ai-fix 阶段**（AI 修复后执行）
   - 执行 post-ai-fix：
     ```bash
     python scripts/increcheck_and_fix_workflow.py --working-dir <project_root> --files <变更文件列表> --phase post --check-type incre
     ```
   - 生成最终 HTML 报告
   - 对照 11.1 的规范内容进行最终复核，确保所有规范条目已落实

**规范检查结果处理**：
- **无告警**: 删除中间文件（`.codecheckcli/` 目录等），标记 11.2 完成
- **有告警**: 进入 AI 修复，修复后重新检查，循环直到告警清零。完成后删除所有中间文件，标记 11.2 完成

#### 11.3 内存安全检查（C/C++、Java、Python、Go）

> 调用 `cwd-audit` 技能检测内存安全和资源管理问题，检测出问题后直接修复（所有语言）

1. **检测** (`11.3 内存安全检查`)
   - 调用 `cwd-audit` 技能检测代码
   - 读取检测结果判断是否有问题：
     - **无问题**: 删除中间检测报告，标记 11.3 完成，进入单元测试环节
     - **有问题**: 根据检测报告直接修复代码，修复后重新调用 `cwd-audit` 检测验证，循环直到无问题或达到最大次数（3次）。全部修复则内存安全检查完成，3次后仍有问题则标记 blocked 返回主会话由主会话上报用户
   - **必须删除中间过程产生的检测报告**

**主会话后处理**（子代理返回后执行）：
- 子代理返回 Code Review 完成 → 进入单元测试环节
- 子代理返回 blocked → 主会话上报用户处理
- 子代理执行失败 → 主会话直接执行 Code Review（降级策略）

# Phase 2: 多语言规范获取 + 筛选（B 档指令文件）

> 本文件为可配置步骤 `fetch_rules` 的指令文件（单仓/多仓通用，无模式差异）。仅在执行计划含 `key=fetch_rules` 条目时被 Read。
> **B 档语义**：`fetch_rules` 只控制 code-rule-tree → 筛选 → code-rule-content（Step 1~3）的执行，**不控制** design-principles / design-views GATE 加载——GATE 文件无条件加载（GATE:REF 标记），与 `fetch_rules` 开关正交。

**执行位置**：Phase 1（版本检查）之后、Phase 3（收集上下文）之前。

## Step 1: 获取各语言相关规范目录树

**【强制要求】**：不许自作主张合并多种语言目录，必须保持多语言独立文件

首先调用 `code-rule-tree` skill 生成规范目录树：
```
python skills/code-rule-tree/scripts/get_tree.py
```

该脚本会将结果保存到 `docs/rule_index.md`。读取该文件，按语言分隔解析出规范目录树。例如 `docs/rule_index.md` 内容为：
```json
{
    "python": [
      "华为 CleanCode Python 核心原则/核心设计原则/可读性与可维护性",
      "华为 CleanCode Python 核心原则/核心设计原则/安全性与防御式编程",
      "华为 CleanCode Python 核心原则/规则级别",
      "云核心网产品工程与IT装备部Python规范"
      ],
    "cpp": [],
    ...
}
```

## Step 2: 挑选 Design 相关的目录名称

根据 Step 1 从 `docs/rule_index.md` 读取的规范目录树，识别 **业务实现规范** 目录条目：

**筛选过程分为两步**：
1. 根据当前需求涉及的编程语言，只处理对应语言下的目录条目。
2. 从对应语言的目录中，挑选与`业务实现规范`相关的目录。

**优先级规则**
第一优先级：`业务实现规范`
- 只要有 `业务实现规范` 相关目录（如：`业务实现规范/项目结构/父项目结构`），全量拉取 该类别下的所有目录。
- 业务实现规范涵盖需求落地、业务功能实现、业务流程设计等与业务直接相关的规范。

第二优先级：Design 通用规范（仅当没有业务实现规范时）
- 如果对应语言下 没有 `业务实现规范` 目录，则参考 Design 通用规范目录名拉取 design 相关规范：
  - 核心设计原则
  - 架构与模块设计
  - 职责划分与边界设计
  - 接口与依赖设计
  - 数据模型与数据结构设计
  - 异常处理策略
  - 安全性与防御式设计
  - 并发、性能与资源管理设计
  - 可读性、可维护性与可扩展性
  - 兼容性与演进设计

**【强制要求】**
- 不得选择当前需求未涉及语言的规范目录。
- 不得将不同语言的目录合并到同一列表中。
- 必须保持以语言为维度的独立目录列表。
- 不选择仅适用于具体代码实现、语法细节、编码格式、代码生成或局部实现检查的目录。
- 必须从 Step 1 返回的原始目录条目中选择，不得自行编造、改写或补充目录名称。
- 目录名称必须完整保留，不得只传递末级目录名称。
- 若某种相关语言下没有合适的 Design 规范目录（既无业务实现规范，也无上述 Design 通用规范），则该语言对应的目录列表返回空数组。

以下类型通常不属于本步骤的筛选范围：
- 具体语法规则
- 命名格式细则
- 缩进、空格、换行等代码风格
- 单条 API 的具体调用方式
- 某个函数或代码片段的实现规则
- 代码生成、代码补全或代码改写细节
- 仅在 Coding 阶段才能判断的局部代码问题

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
    "华为 CleanCode Python 核心原则/核心设计原则/可读性与可维护性",
    "华为 CleanCode Python 核心原则/核心设计原则/安全性与防御式编程"
  ]
}
```
不得选择：

```
华为 CleanCode Python 核心原则/规则级别
云核心网产品工程与IT装备部Python规范/编码风格/命名规则
```

因为这些目录与当前 Design 阶段的方案设计关联较弱，或更适合后续 Coding、Code Review 阶段。

## Step 3: 整合多语言规范

将 Step 2 筛选出的目录，以json格式，按照语言分别传递给 `code-rule-content` skill，获取对应规范内容。

Invoke `code-rule-content` skill:

输入必须保持多语言独立，例如：
```json
{
  "python": [
    "华为 CleanCode Python 核心原则/核心设计原则/可读性与可维护性",
    "华为 CleanCode Python 核心原则/核心设计原则/安全性与防御式编程"
  ],
  "cpp": [
    "华为 CleanCode C++ 核心原则/架构与模块设计"
  ]
}
```

**【强制要求】**
- 每种语言只传递该语言对应的目录。
- 不得将 Python、Java、C++ 等不同语言目录混合传递。
- 不得传递空目录、缩写目录或自行推测的目录。
- 必须使用 Step 2 返回的目录名称。

`code-rule-content` 返回结果统一按语言组织，例如：
```json
{
  "python": "### 可读性与可维护性\n- 使用具有明确含义的标识符\n- 公共函数必须编写 Docstring\n",
  "cpp": "### 特殊成员函数\n- 类成员变量必须显式初始化\n- 单参数构造函数声明为 explicit\n # Cpp规范"
}
```
Agent 必须统一理解为：
> 当前需求的**语言级 Design 规范集合（`language-specific design specifications`）**。

## Step 3 Output

Step 3 完成后，将得到当前需求唯一使用的 Design 规范集合，例如：
```json
{
  "python": "...markdown...",
  "cpp": "......."
}
```

后续所有设计阶段均直接使用该结果。

**【强制要求】**

后续流程：
- 不再重新调用 `code-rule-tree`
- 不再重新调用 `code-rule-content`
- 不再重新读取任何 `*-rule.md`
- 不再重新筛选规范目录
- 仅使用当前需求涉及语言的规范。
- 不得跨语言应用规范。
- 规范必须结合当前需求进行应用，不得机械复制全文。
- Design 阶段只应用与设计相关的规范；Coding、Code Review 等阶段规则不得提前注入设计文档。

Step 3 返回的规范集合是 Design 阶段唯一的语言规范来源（Single Source of Truth）。

## 关闭语义

**执行计划不含 `fetch_rules` 条目时**：跳过 Step 1~3（code-rule-tree / 筛选 / code-rule-content 全部不执行），`language-specific design specifications` 为空。后续 Phase 8 生成设计文档时不注入语言级规范约束。**GATE 文件（design-principles.md / design-views.md）仍无条件加载**（GATE:REF 标记不受 `fetch_rules` 开关控制）。

**【关闭风险提示】**：关闭 `fetch_rules` 意味着设计文档不参考任何语言级 CleanCode 规范，可能导致设计与团队规范不一致。仅在用户明确表示"基于已有规范知识进行设计"时关闭。

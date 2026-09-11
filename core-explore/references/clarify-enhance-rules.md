# clarify-enhance-rules.md

> 术语对齐/决策记录的后处理规则
> 理念来源：domain-modeling（v1.2.0），采纳理念而非调用技能
> 作用范围：core-explore 阶段5.3 brainstorming 返回后的后处理阶段

---

## 一、术语对齐规则

### 1.1 理念来源

采纳 domain-modeling 技能（v1.2.0）的核心理念：

- **术语挑战**：当同一概念出现多个词时，挑战模糊词和冲突词，选最好的一个作为规范词；即使没有冲突，对模糊术语也要求精确定义
- **纯术语表**：术语表只记录"是什么"，不记录"做什么"和实现细节；通用编程概念不属于术语表
- **即时沉淀**：术语确定后写入术语表，确保后续文档使用统一术语

### 1.2 执行步骤

1. **读取 spec.md "领域术语"章节**
   - 了解已有术语定义和规范词
   - 如 spec.md 不存在或无"领域术语"章节 → 记录但跳过写入

2. **扫描 brainstorming 对话历史中的术语冲突**
   - 识别同一概念使用了不同词的对话片段
   - 识别用户已澄清的术语定义（如"'X'和'Y'是同一概念"）
   - 识别与 spec.md 已有定义冲突的用法

3. **扫描 brainstorming 对话历史中的模糊术语**
   - 识别在对话中被使用但定义不清的领域词汇（无冲突但语义模糊）
   - 识别用户在回答中含糊带过、未精确定义的项目特有概念
   - 对模糊术语补充精确定义，写入 spec.md "领域术语"章节

4. **术语确定后写入 spec.md "领域术语"章节**
   - 格式：四列表格 — 术语 / 英文 / 定义 / 避免使用
   - "避免使用"列列出被替代的同义词，可留空
   - 仅补充新术语，不覆盖已有定义

5. **可选：与代码交叉验证**
   - 当用户描述与代码实现矛盾时，记录冲突供后续阶段参考
   - 当代码中已有相关术语定义时，确认一致性

### 1.3 术语表规则

- **Be opinionated**：当多个词指同一概念时，选最好的一个作为规范词，其余列在"避免使用"列
- **Keep definitions tight**：一到两句话，定义"是什么"而非"做什么"
- **Only project-specific terms**：通用编程概念（超时、错误类型等）不属于术语表
- **No implementation details**：术语表只记录领域概念，不记录实现细节和设计决策
- **Challenge vague terms**：即使术语没有冲突（无人用其他词指代同一概念），只要定义模糊不清，就应要求精确定义

### 1.4 降级策略

- 如 brainstorming 对话历史中无术语冲突且无模糊术语 → 跳过术语对齐
- 如 spec.md 不存在 → 记录术语到 clarification_summary.json，不创建文件
- 如 brainstorming 不可用（回退到苏格拉底式澄清）→ 同样在后处理中扫描对话历史执行术语对齐

---

## 二、决策记录规则

### 2.1 理念来源

采纳 domain-modeling 技能（v1.2.0）ADR 机制的核心理念：

- **三条件稀疏记录**：只有同时满足三个条件的决策才记录，大多数 session 不产生需要记录的决策
- **ADR 三条件**：Hard to reverse + Surprising without context + Real trade-off
- **Lazy creation**：文件和章节仅在首次需要时创建

### 2.2 三条件检查（三个必须同时满足，缺一不记录）

1. **Hard to reverse**：改回来的代价大
2. **Surprising without context**：未来读者看到代码会疑惑"为什么这么做"
3. **The result of a real trade-off**：确实有多种可选方案，基于特定理由选了一个

如果任何一个条件不满足，不写入"设计决策"章节。该决策仅存在于 clarification_summary.json 中。

> "If a decision is easy to reverse, skip it: you'll just reverse it. If it's not surprising, nobody will wonder why. If there was no real alternative, there's nothing to record beyond 'we did the obvious thing.'"
>
> "A session that yields a sharper glossary and zero design decisions is working as designed."

### 2.3 执行步骤

1. **扫描 brainstorming 对话历史中的决策确认**
   - 识别用户对方案选择的回答（"选A"、"同意"、"B"）
   - 识别 brainstorming 推荐的方案及推荐理由
   - 提取每个决策的：结论、背景、替代方案

2. **三条件检查** → 满足则写入 docs/specs/design.md（项目级设计规格文档）"设计决策"章节。**注意**：此处design.md指项目级设计规格（docs/specs/design.md），不是brainstorming生成的架构设计文件（docs/superpowers/specs/下的文件）
   - 使用现有四段式格式：决策 / 背景 / 方案对比 / 理由
   - 在"理由"部分标注三条件检查结果
   - 追加到"设计决策"章节，不覆盖已有内容

3. **什么 qualifies**（对齐 grill-with-docs 标准）：
   - 架构形态、集成模式、有锁定的技术选择
   - 边界和范围决策、故意偏离显而易见的路径
   - 代码中不可见的约束、非显而易见的被拒替代方案

### 2.5 降级策略

- 如 brainstorming 对话中无决策满足三条件 → 不写入，这是正常情况
- 如 docs/specs/design.md 不存在 → 记录决策到 clarification_summary.json，不创建文件
- 如 brainstorming 不可用 → 基于苏格拉底式澄清的对话历史同样适用

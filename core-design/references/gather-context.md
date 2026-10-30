# Phase 3: Gather Context（指令文件）

> 本文件为 Phase 3 收集上下文的指令文件（单仓/多仓通用，无模式差异）。GATE:REF 无条件加载。

**动作**：生成设计文档前，SKILL 层必须收集上下文。

## 1. Read delta_spec.md

Read `docs/changes/<change-name>/delta_spec.md` - Requirement delta (MUST)
- This is the frozen specification from explore phase
- Contains ADDED/MODIFIED/REMOVED requirements

## 2. Read language-specific design specifications

Read `language-specific design specifications` resolved in Step 3 - Design stage specification constraints (multi-language)
- Company, product_line, pdu, department, team specs
- Must ensure design complies with these rules
- If `language-specific design specifications` contain skill usage descriptions (e.g., "Use /huawei-cleancode-java to query CleanCode rules"), include them in delta_design.md

## 3. Read Global Spec and Design Documents（必须）

**判断环境类型（第一步）**：
- 读取 `docs/relationship.md` 检查是否为多仓环境
- 如果是**单仓环境**：继续读取根目录全局文档
- 如果是**多仓环境**：详见 references/multi-repo.md M-1/M-2

### 【单仓环境】全局文档读取

| 优先级 | 文档 | 路径 | 用途 |
|--------|------|------|------|
| P0 | 项目级 spec.md | `docs/specs/spec.md` | 了解全局规格，全局功能划分，与其他模块的关系 |
| P0 | 项目级 design.md | `docs/specs/design.md` | 了解全局架构、技术选型、模块依赖关系 |
| P0 | 多仓库依赖关系 | `docs/relationship.md` | 了解各子仓库间的依赖关系和调用链（由 core-init 生成） |
| P0 | 多仓环境说明 | `proposal.md` 多仓环境说明章节（存在性校验，不固定章节号） | 校验 explore 阶段确认的仓库范围、实现顺序、接口契约 |
| P1 | 相关模块级 design.md | `docs/specs/<module-name>/design.md` | 了解受影响模块的设计细节 |
| P1 | 相关模块级 spec.md | `docs/specs/<module-name>/spec.md` | 了解受影响模块的接口和约束 |

### 【多仓环境】子仓文档读取和校验

详见 references/multi-repo.md M-2（各仓按仓生成中的文档读取与校验）

### 读取策略

- 如果 `docs/specs/` 目录不存在或全局文档为空，则跳过
- 如果全局文档存在，**必须**读取后再进行设计
- 根据 delta_spec.md 中识别的"受影响模块"，选择性读取对应模块的文档

### 全局文档的作用

- **设计一致性**：确保 delta_design.md 与全局架构保持一致
- **技术选型参考**：参照项目级 design.md 的技术栈进行选型
- **避免重复设计**：了解现有模块能力，避免重复造轮子
- **接口兼容性**：确保新设计与现有模块接口兼容
- **术语约束**：delta_design.md 中所有术语必须与 spec.md "领域术语"保持一致；如需引入新术语，必须同时更新 spec.md "领域术语"章节
- **决策约束**：设计必须遵守 design.md "设计决策"中已有记录；如设计需要推翻已有决策，必须在 delta_design.md 的"设计决策"章节显式标注推翻理由

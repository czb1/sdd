# Phase 5: 读取相似需求参考（指令文件）

> 本文件为可配置步骤 `read_similar` 的指令文件（单仓/多仓通用，无模式差异）。仅在执行计划含 `key=read_similar` 条目时被 Read。

**执行位置**：Phase 4（代码理解）之后、Phase 6（读取 brainstorming design.md）之前。

**动作**：读取 delta_spec.md 中 "Similar Requirements Reference" 章节指向的归档文件，按引用路径读取归档目录下的 `delta_design.md` 和 `delta_spec.md` 作为参考。

## 执行步骤

1. Read `docs/changes/<change-name>/delta_spec.md`
2. Check for "Similar Requirements Reference" section
3. If exists: Read referenced similar changes' files:
   - **归档目录下的引用**（由 core-explore 打分筛选后写入）：读取归档路径下的 `delta_design.md`（技术方案参考）和 `delta_spec.md`（需求变更参考）

**Similar Changes Reference Format**:
```markdown
## Similar Requirements Reference

- [版本/日期-需求名](归档路径): 简要说明相似点
- [Change-Name-1]: Description of similarity
```

**归档引用解析规则**：
- 引用中包含路径（如 `docs/archive/...`）→ 按路径读取归档目录下的 `delta_design.md` 和 `delta_spec.md`
- **单仓环境**：路径直接指向当前项目 `docs/archive/`
- **多仓环境**：路径可能指向子仓（如 `repoA/docs/archive/...`），需按路径读取对应子仓的归档文件

## 关闭语义

**执行计划不含 `read_similar` 条目时**：跳过相似需求参考读取，Phase 6 不依赖此步骤的输出。关闭此步骤仅意味着设计时不参考历史相似实现，不影响后续流程。纯增益步骤，关闭风险低。

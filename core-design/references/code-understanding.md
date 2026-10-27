# Phase 4: 代码理解（指令文件）

> 本文件为 Phase 4 代码理解的指令文件（单仓/多仓通用，无模式差异）。GATE:REF 无条件加载。

**动作**：Agent 通过 CodeBase 工具（如可用）或传统工具（read/grep/glob）理解代码，为设计文档生成提供代码上下文。

## 重要说明

- CodeBase 工具是 Agent 内置能力，具体可用性需尝试调用判断
- 目标代码需要提前在 CodeBase 平台构建才有数据
- 具体调用方式由 Agent 自行判断，SKILL.md 只提供建议
- **统一尝试调用**：无论 OpenCode 还是 ClaudeCode，都应先尝试调用
- **回退策略**：CodeBase 不可用或无结果时，必须回退到 read/grep/glob

## 4.1 尝试调用 CodeBase 工具

**统一尝试调用策略**：
- 无论 OpenCode 还是 ClaudeCode，都**先尝试调用** CodeBase 工具
- 根据调用结果判断是否可用：**能获取到有效数据视为可用，否则视为不可用**
- 这样可以兼容后续 ClaudeCode 可能支持 CodeBase 的情况

**调用示例**（具体调用方式由 Agent 自行判断）：
- 尝试调用 `CodeSemanticSearch` 进行语义搜索
- 尝试调用 `GetFeatureTree` 获取项目结构
- 如果返回有效结果 → 继续使用
- 如果返回空结果或报错 → 回退到 read/grep/glob

## 4.2 尝试使用 CodeBase 工具（如果可用）

**建议优先级**：

1. **GetFeatureTree** — 获取项目功能结构
   - 参数：label_detailed=true, description_detailed=true
   - 目的：了解项目的模块划分和接口层级

2. **CodeSemanticSearch** — 语义搜索核心功能
   - 参数：query="需求核心功能描述（英文）"
   - 目的：快速定位核心实现文件

3. **ComprehensiveSearch** — 理解业务调用链
   - 参数：codeQuery="功能锚点", chainQuery="业务主流程"
   - 目的：获取完整的业务调用路径

4. **GetRemoteCallChain** — 追溯关键方法调用链
   - 参数：file_path="关键文件", method_name="核心方法", depth=2
   - 目的：理解设计决策的上下游影响

**三状态判断**：
| 状态 | 条件 | 动作 |
|------|------|------|
| present | CodeBase 可用且有数据 | 使用 CodeBase 结果 |
| missing | CodeBase 可用但无数据 | 回退到 read/grep/glob |
| not_installed | CodeBase 工具不可用 | 直接使用 read/grep/glob |

## 4.3 回退到传统工具（必须）

**当 CodeBase 不可用或无结果时，使用以下替代**：

| CodeBase 工具 | 降级替代工具 | 使用方式 |
|---------------|--------------|----------|
| GetFeatureTree | glob + grep | `glob "**/*.{py,java,ts}"` + 分析模块结构 |
| CodeSemanticSearch | grep | `grep -r "关键词" --include="*.py"` |
| ComprehensiveSearch | grep + read | grep 定位 + read 理解调用链 |
| GetRemoteCallChain | grep + read | 多轮 grep 追溯调用关系 |

## 4.4 必须通过 read 验证

**验证要求**：
- 无论使用哪种工具，**最终必须通过 read 实际读取代码进行验证**
- CodeBase 只是辅助定位，不能替代实际代码阅读
- 验证 CodeBase 定位的文件是否确实与设计相关
- 补充 CodeBase 可能遗漏的边界情况

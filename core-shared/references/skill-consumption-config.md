# 任务 Skill 消费配置

本仓库维护 core-design / core-apply 的指令文件，不包含完整 CoreSpec 的 `core-shared/scripts/flow_config.py`、`main.py` 或运行时测试。本次使用开发指导 §5 的**自定义 reference 步骤**接入已有编排点，默认不声明，不新增内置布尔键、固定步骤或编排点注册。

## 配置与默认行为

| 命名空间 | 自定义步骤键 | 已有编排点 | 指令文件（相对该 Skill 安装目录） | 默认 |
|---|---|---|---|---|
| `core-design` | `skill_consumption` | `post-generate` | `references/skill-consumption.md` | 关闭（声明缺失或整块注释） |
| `core-apply` | `skill_consumption` | `pre-codegen` | `references/skill-consumption.md` | 关闭（声明缺失或整块注释） |

两个命名空间独立：只开启 design 时仅生成能力关联；apply 仍不自动读取或消费这些关联。只开启 apply 时可按需准备并消费能力。`expert_experience` 只控制原有设计经验准备，不会开启此新增步骤；`--query`、已有 Skill 字段和本地目录也不能隐式开启。

## 开启与关闭

1. 使用现有 CoreSpec 的 `flow-config --init --skill <name>` 初始化所需命名空间（已有时保留）。运行时原模板不会自动包含本仓库新增的示例。
2. 参考 [默认关闭示例](../../examples/flow-config.skill-consumption.jsonc)，将需要的 `skill_consumption` 注释块合并到 `~/.corespec/flow-config.json` 的对应命名空间，保留其他键与注释；已有其他键时按 JSONC 对象语法补逗号。不要整文件覆盖用户配置。
3. **开启**：取消所需对象全部行的注释。**关闭**：将该对象整块注释。沿用框架的注释软删除 / 恢复机制；不要写 `skill_consumption: true/false`，它是 reference 对象，不是未注册的内置布尔键。也不要添加 reference 类型不支持的 `run_mode` / `args`。
4. 重新运行相应 Skill 的 Step 0：`main.py flow-config --json --skill core-design` 或 `main.py flow-config --json --skill core-apply`，并按原流程确认。首次配置和配置变更仍使用既有确认规则，不由候选选择的默认规则代替。
5. 检查生成计划：对应 `orchestration_points` 插槽中有 `key=skill_consumption`、`type=reference`、`file=references/skill-consumption.md` 的有效条目才执行。关闭后该条目必须消失；不要手工修改生成计划、skipped 文件或仅凭配置源猜测结果。旧计划未重建不代表关闭已生效。

仅开启两个消费阶段的配置示意如下；合并时保留其他步骤：

```json
{
  "core-design": {
    "skill_consumption": {
      "type": "reference",
      "file": "references/skill-consumption.md",
      "at": "post-generate",
      "order": 1,
      "description": "任务形成后关联 Skill 与经验"
    }
  },
  "core-apply": {
    "skill_consumption": {
      "type": "reference",
      "file": "references/skill-consumption.md",
      "at": "pre-codegen",
      "order": 1,
      "description": "代码生成前消费任务能力"
    }
  }
}
```

## 执行位置与关闭语义

- **design / 单仓**：Phase 8 完整生成任务及其他产物后，在 post-generate 中执行一次，再进入追溯验证。
- **design / 多仓**：M-2 全部仓完成后由主会话调度同一 post-generate；候选按“仓名 + 任务编号”汇总，主会话统一确认，再按仓安装并回写。M-2 生成代理不提前检索或下载。
- **apply / 单仓**：pre-codegen 中存在本条目时，任务循环前按专属指令完成一次批量准备，每任务在 9.3.5 读取锁定内容；不重复整批检索或逐任务确认。
- **apply / 多仓**：主会话按根执行计划在代码生成代理启动前准备；子代理只按下发片段中同一条目执行 task 级消费。缺少条目不得通过本仓配置或 design 计划补开启。
- **关闭**：不加载专属或共享消费指令，不检索、询问产品 / 候选、下载、读取任务关联能力内容或改写 Skill / 经验关联字段。原有任务文件读取、设计 / 代码生成、checkbox 更新、独立设计经验准备及其他编排条目继续执行；保留已有字段和本地内容，清理仍保护被引用文件。
- **独立依赖**：本步骤不依赖 `expert_experience`、审查或 UT 开关；关闭它不删除同插槽中的其他自定义步骤。

## 指令文件与交付范围

消费细节只放在阶段专属的 `core-design/references/skill-consumption.md`、`core-apply/references/skill-consumption.md` 及 [共享规则](skill-consumption.md)。SKILL.md 只保留启用条件、GATE 和执行指针。

部署这些指令到现有 CoreSpec 时，同时合入两个阶段指令与 `core-shared/references/skill-consumption.md`；共享规则通过 `config_dir / 'skills/core-shared/references/skill-consumption.md'` 定位。配置示例是人工合并参考，不自动覆盖配置或替代运行时的 `TEMPLATE_JSONC`。

若后续在完整框架中改为内置布尔步骤，应按开发指导同步修改注册表（`default: false`）、固定步骤挂载位序、`TEMPLATE_JSONC`、用户指南及运行时测试；不能只在文档中声明布尔键而不接入框架。

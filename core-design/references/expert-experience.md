# Phase 7: 获取专家经验（指令文件）

> 本文件为可配置步骤 `expert_experience` 的指令文件（单仓/多仓通用，无模式差异）。仅在执行计划含 `key=expert_experience` 条目时被 Read。

**执行位置**：Phase 6（读取 brainstorming design.md）之后、Phase 8（生成设计文档）之前。

**动作**：调用 paradigm-exp-use skill 获取专家知识，辅助设计决策。

## 执行步骤

**脚本路径获取方式**（与 core_paths.py 路径解析一致）：
- 优先使用 `OPENCODE_CONFIG` 环境变量
- 回退到 `~/.config/opencode` (OpenCode) 或 `~/.cac` (ClaudeCode)

调用 paradigm-exp-use skill 获取专家知识：

```bash
# Dynamic path resolution (supports both OpenCode and ClaudeCode)
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([
    sys.executable,
    config_dir / 'skills' / 'paradigm-exp-use' / 'scripts' / 'fetch_experiences.py',
    '<query>', 'expert_experience.md'
])
sys.exit(result.returncode)
"
```

**Save Location**: `docs/changes/<change-name>/expert_experience.md`

**Query Strategy**:
- If `--query` provided: use user-specified keywords
- If no `--query`: derive keywords from:
  - "Similar Requirements Reference" in delta_spec.md
  - Core requirements from delta_spec.md
  - Use those changes' design patterns as search queries

**Expert Experience Integration**:
- Expert knowledge saved to `expert_experience.md`
- Read and inject into `delta_design.md` design decisions section
- Used for technical approach and technology selection guidance

**After using expert experience** (Phase 8 完成后):
1. Delete `expert_experience.md` to keep the change directory clean
2. Clean up workflow directory if it exists:
   ```python
   import shutil
   from pathlib import Path
   workflow_dir = Path(project_root) / 'workflow'
   if workflow_dir.exists():
       shutil.rmtree(workflow_dir)
   ```

## 关闭语义

**执行计划不含 `expert_experience` 条目时**：跳过 paradigm-exp-use 调用，不生成 `expert_experience.md`。Phase 8 生成设计文档时不注入专家经验。纯增益步骤——delta_design.md 仍可生成，仅少"技术选型参考"，关闭风险低。

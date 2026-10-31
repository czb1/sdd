# Phase 11: 清理临时文件（单仓模式指令文件）

> 本文件为可配置步骤 `cleanup` 的指令文件（单仓版）。仅在执行计划含 `key=cleanup` 条目时被 Read。

**执行位置**：Phase 10（design-doc-reviewer 审查）完成后执行。如 Phase 9/10 被关闭，则 Phase 8 完成后执行。

**动作**：清理 core-explore 阶段保留的跨阶段引用文件和 brainstorming 临时文件。 仅删除已确认的临时产物；仍被持久文档引用的文件必须保留，含保留文件的目录不得整目录删除，下方删除示例及清理验证均须排除这些保留项。

## 清理清单

### 1. 检查元数据文件

- 读取 `docs/changes/<change-name>/.brainstorming_output` 元数据文件
- 如果文件不存在，说明 brainstorming 未执行，跳过 design.md 清理（但仍需清理 clarification_summary.json）

### 2. 清理 design.md

- 如果元数据文件存在，解析获取 `design_doc_path`
- 删除 design.md 文件和元数据文件本身
- 使用 Python 脚本清理：
  ```python
  import json
  from pathlib import Path

  change_dir = Path("docs/changes/<change-name>")
  output_meta = change_dir / ".brainstorming_output"

  if output_meta.exists():
      with open(output_meta) as f:
          meta = json.load(f)
      design_path = Path(meta["design_doc_path"])
      if design_path.exists():
          design_path.unlink()
          print(f"Deleted: {design_path}")
      output_meta.unlink()
      print(f"Deleted: {output_meta}")
  ```

### 3. 清理 clarification_summary.json

- 删除 `docs/changes/<change-name>/clarification_summary.json`（brainstorming 澄清阶段生成的决策摘要文件）
- 该文件在 core-explore 阶段生成，已被本阶段的 design-doc-reviewer 用于决策保真审查，现在可以安全清理
- 使用 Python 脚本清理：
  ```python
  from pathlib import Path

  change_dir = Path("docs/changes/<change-name>")
  clarification_file = change_dir / "clarification_summary.json"

  if clarification_file.exists():
      clarification_file.unlink()
      print(f"Deleted: {clarification_file}")
  ```

### 4. 清理 expert_experience.md

- 删除 `docs/changes/<change-name>/expert_experience.md`（旧流程遗留的临时经验文件；仅在未被任务引用时清理）
- 该文件即使已注入 delta_design.md，也必须先确认未被 tasks.md 引用；仍被任务引用时保留并跳过以下删除脚本
- 使用 Python 脚本清理：
  ```python
  from pathlib import Path

  change_dir = Path("docs/changes/<change-name>")
  expert_file = change_dir / "expert_experience.md"

  if expert_file.exists():
      expert_file.unlink()
      print(f"Deleted: {expert_file}")
  ```

### 5. 清理 workflow 目录

- 删除 `workflow/` 目录（历史流程可能创建的临时目录）
- 使用 Python 脚本清理：
  ```python
  import shutil
  from pathlib import Path

  workflow_dir = Path(project_root) / 'workflow'
  if workflow_dir.exists():
      shutil.rmtree(workflow_dir)
      print(f"Deleted: {workflow_dir}")
  ```

### 6. 清理 downloads/ 目录

- 删除 `docs/changes/<change-name>/downloads/` 整个目录（包含 IDP/DBOX 附件、媒体文件等）
- **【强制】使用 rm -rf 删除整个 downloads/ 目录**（禁止逐个删除文件而保留目录）
- 使用 Python 脚本清理：
  ```python
  import shutil
  from pathlib import Path

  change_dir = Path("docs/changes/<change-name>")
  downloads_dir = change_dir / "downloads"

  if downloads_dir.exists():
      shutil.rmtree(downloads_dir)
      print(f"Deleted: {downloads_dir}")
  ```

### 7. 清理验证（必须执行）

- Glob 列出变更目录文件清单，确认无 downloads/ 目录、无 expert_experience.md
- Glob 验证 `**/downloads/*` 返回空
- 确认保留文件存在：proposal.md、delta_spec.md、delta_design.md、tasks.md、delta_test_design.md、.templates/resolved/（M3/M5b 物化模板，GATE:REF 依赖）

### 8. 执行时机

- 在 Phase 10 完成后执行（如 Phase 10 被关闭，则 Phase 9 完成后执行；如 Phase 9/10 均被关闭，则 Phase 8 完成后执行）
- 确保 design.md 被用于生成 delta_design.md 后再清理
- 确保 clarification_summary.json 已被 design-doc-reviewer 读取后再清理（如 design_review 被关闭，则可直接清理）

## 关闭语义

**执行计划不含 `cleanup` 条目时**：跳过所有清理操作，临时文件残留（.brainstorming_output / design.md / clarification_summary.json / expert_experience.md / downloads/ / workflow/）。"Phase 11 是最后一步禁止跳过"强制位随关闭豁免。

**【关闭风险提示】**：关闭 cleanup 意味着临时文件保留不清理。残留文件是 explore/design 阶段产物，不导致 core-apply 断链（core-apply 禁止删除列表本来要求保留部分文件），但会污染 change 目录。需显式记录"cleanup 已关闭，临时文件残留"后输出执行总结并宣布流程完毕。

# Phase 12: 清理临时文件（多仓模式指令文件）

> 本文件为可配置步骤 `cleanup` 的指令文件（多仓版）。仅在执行计划含 `key=cleanup` 条目时被 Read。

**执行位置**：M-3b（各仓 design-doc-reviewer 审查）完成后执行。如 M-3a/M-3b 被关闭，则 M-2 完成后执行。

**动作**：清理项目级变更目录 + 各仓变更目录的临时文件。多仓模式下为**双层清理**（项目级 + 各仓级）。 仅删除已确认的临时产物；仍被持久文档引用的文件必须保留，含保留文件的目录不得整目录删除，下方删除示例及清理验证均须排除这些保留项。

## 项目级清理

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

- 删除 `docs/changes/<change-name>/clarification_summary.json`
- 使用 Python 脚本清理：
  ```python
  from pathlib import Path

  change_dir = Path("docs/changes/<change-name>")
  clarification_file = change_dir / "clarification_summary.json"

  if clarification_file.exists():
      clarification_file.unlink()
      print(f"Deleted: {clarification_file}")
  ```

### 4. 清理 drafts 目录（多仓专属）

- 删除 `docs/changes/<change-name>/drafts/` 目录下的所有文件
- drafts/{repo}.md（各仓探索蒸馏文件）和 drafts/ambiguities_{repo}.md（各仓模糊点清单）在 core-design M-2 阶段已被读取，信息已融入 delta_design.md，可以安全清理
- 使用 Python 脚本清理：
  ```python
  import shutil
  from pathlib import Path

  change_dir = Path("docs/changes/<change-name>")
  drafts_dir = change_dir / "drafts"

  if drafts_dir.exists():
      shutil.rmtree(drafts_dir)
      print(f"Deleted: {drafts_dir}")
  ```

### 5. 清理 shared_context.md（多仓专属）

- 删除 `docs/changes/<change-name>/shared_context.md`
- shared_context.md 在 core-design M-2 各仓设计文档生成阶段已被读取，信息已融入各仓 delta_design.md，可以安全清理
- 使用 Python 脚本清理：
  ```python
  from pathlib import Path

  change_dir = Path("docs/changes/<change-name>")
  shared_context = change_dir / "shared_context.md"

  if shared_context.exists():
      shared_context.unlink()
      print(f"Deleted: {shared_context}")
  ```

### 6. 清理 impl_questions_for_design.json

- 删除 `docs/changes/<change-name>/impl_questions_for_design.json`（core-explore 阶段生成、本阶段 M-2 步骤 3 消费的实现层面延迟问题文件）
- 该文件在 M-2 步骤 3 已被逐条确认，确认结果已融入各仓 delta_design.md，可以安全清理
- 使用 Python 脚本清理：
  ```python
  from pathlib import Path

  change_dir = Path("docs/changes/<change-name>")
  impl_questions_file = change_dir / "impl_questions_for_design.json"

  if impl_questions_file.exists():
      impl_questions_file.unlink()
      print(f"Deleted: {impl_questions_file}")
  ```

### 7. 清理 downloads/ 目录

- 删除 `docs/changes/<change-name>/downloads/` 整个目录（包含 IDP/DBOX 附件、媒体文件等）
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

## 各仓级清理

对每个涉及仓 `{repo}/docs/changes/<change>/`：

- **必须保留**：`proposal.md`、`delta_spec.md`、`delta_design.md`、`tasks.md`、`delta_test_design.md`
- **【禁止】删除以下跨阶段引用文件**（core-apply 仍需消费）：
  - `repo_assignments.json` — core-apply M-1 多仓检测依赖此文件
  - `clarifications/cross_repo_contracts.json` — core-apply 拓扑排序各仓执行顺序依赖此文件
- 清理各仓变更目录下的 `downloads/` 子目录（如存在）

## 清理验证（必须执行）

- Glob 列出项目级变更目录文件清单，确认无 downloads/ 目录、无 impl_questions_for_design.json、无 drafts/ 目录、无 shared_context.md
- 多仓模式下 Glob 列出各仓变更目录文件清单，确认无 downloads/ 子目录
- Glob 验证 `**/downloads/*` 返回空
- 确认保留文件存在：
  - 项目级：proposal.md、delta_spec.md、repo_assignments.json、clarifications/cross_repo_contracts.json
  - 各仓级：proposal.md、delta_spec.md、delta_design.md、tasks.md、delta_test_design.md

## 执行时机

- 在 M-3b 完成后执行（如 M-3b 被关闭，则 M-3a 完成后执行；如 M-3a/M-3b 均被关闭，则 M-2 完成后执行）
- 确保 design.md 被用于生成 delta_design.md 后再清理
- 确保 clarification_summary.json 已被 design-doc-reviewer 读取后再清理（如 design_review 被关闭，则可直接清理）
- 确保 drafts 目录已被 M-2 各仓按仓生成阶段读取后再清理
- 确保 shared_context.md 已被 M-2 各仓按仓生成阶段读取后再清理

## 关闭语义

**执行计划不含 `cleanup` 条目时**：跳过所有清理操作（项目级 + 各仓级），临时文件残留。"Phase 12 是最后一步禁止跳过"强制位随关闭豁免。需显式记录"cleanup 已关闭，临时文件残留"后输出执行总结并宣布流程完毕（残留由用户或后续人工处理）。

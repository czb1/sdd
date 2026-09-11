#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
delta_spec.md 生成器
按照 spec工程规范.md 1.5.2 要求生成 delta_spec.md
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


def generate_delta_spec(
    requirement_id: str,
    proposal_data: Dict[str, Any],
    similar_requirements: List[Dict[str, str]] = None,
    output_dir: str = "."
) -> str:
    """
    生成 delta_spec.md 文件

    Args:
        requirement_id: 需求ID
        proposal_data: proposal数据
        similar_requirements: 相似需求列表
        output_dir: 输出目录

    Returns:
        生成的文件路径
    """
    output_path = Path(output_dir) / "delta_spec.md"

    content = _build_delta_spec_content(requirement_id, proposal_data, similar_requirements)

    # 写入文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    return str(output_path)


def _build_delta_spec_content(
    requirement_id: str,
    proposal_data: Dict[str, Any],
    similar_requirements: List[Dict[str, str]] = None
) -> str:
    """
    构建 delta_spec.md 内容

    按照 spec工程规范.md 1.5.2 要求:
    1. ADDED Requirements（新增的业务规则）
    2. MODIFIED Requirements（修改的业务规则）
    3. REMOVED Requirements（删除的业务规则）
    4. 数据约束变更（按ADDED / MODIFIED / REMOVED分类）
    5. 术语变更（按ADDED / MODIFIED分类）
    6. 合并检查清单
    """
    if similar_requirements is None:
        similar_requirements = []

    e2e_id = proposal_data.get("e2e_id", requirement_id)
    description = proposal_data.get("description", "")

    content_lines = [
        f"# Delta Spec: {e2e_id}",
        "",
        f"**创建日期**: {datetime.now().strftime('%Y-%m-%d')}",
        f"**需求ID**: {e2e_id}",
        f"**类型**: ADDED",  # 根据实际情况调整
        "",
        "---",
        "",
        "## 1. ADDED Requirements（新增的业务规则）",
        "",
        "### 1.1 功能需求",
        "",
        "| 序号 | 业务规则 | 验收条件 | 备注 |",
        "|------|----------|----------|------|",
        "| 1.1.1 | (新增的业务规则描述) | 触发场景 → 预期行为 | |",
        "",
        "### 1.2 业务规则详细说明",
        "",
        "**规则 1.1.1**: (规则名称)",
        "",
        "- **描述**: (规则详细描述)",
        "- **验收条件**:",
        "  - 输入 (条件) → 输出 (预期结果)",
        "",
        "---",
        "",
        "## 2. MODIFIED Requirements（修改的业务规则）",
        "",
        "| 序号 | 原规则 | 修改后规则 | 变更原因 |",
        "|------|--------|------------|----------|",
        "| 2.1.1 | (原规则描述) | (修改后规则描述) | (变更原因) |",
        "",
        "← (原为: [原描述])",
        "",
        "---",
        "",
        "## 3. REMOVED Requirements（删除的业务规则）",
        "",
        "| 序号 | 原规则 | 删除原因 | 迁移方案 |",
        "|------|--------|----------|----------|",
        "| 3.1.1 | (原规则描述) | (删除原因) | (如有迁移方案) |",
        "",
        "---",
        "",
        "## 4. 数据约束变更",
        "",
        "### 4.1 ADDED 数据约束",
        "",
        "| 约束对象 | 约束类型 | 约束内容 | 备注 |",
        "|----------|----------|----------|------|",
        "| (对象名) | (类型) | (约束内容) | |",
        "",
        "### 4.2 MODIFIED 数据约束",
        "",
        "| 约束对象 | 原约束 | 修改后约束 | 变更原因 |",
        "|----------|--------|------------|----------|",
        "| (对象名) | (原约束) | (修改后约束) | (原因) |",
        "",
        "← (原为: [原约束])",
        "",
        "### 4.3 REMOVED 数据约束",
        "",
        "| 约束对象 | 原约束 | 删除原因 |",
        "|----------|--------|----------|",
        "| (对象名) | (原约束) | (原因) |",
        "",
        "---",
        "",
        "## 5. 术语变更",
        "",
        "### 5.1 ADDED 术语",
        "",
        "| 术语 | 定义 | 备注 |",
        "|------|------|------|",
        "| (术语) | (定义) | |",
        "",
        "### 5.2 MODIFIED 术语",
        "",
        "| 术语 | 原定义 | 修改后定义 |",
        "|------|--------|------------|",
        "| (术语) | (原定义) | (修改后定义) |",
        "",
        "← (原为: [原定义])",
        "",
        "---",
        "",
        "## 6. 合并检查清单",
        "",
        "- [ ] 所有 ADDED 规则已附带验收条件",
        "- [ ] 所有 MODIFIED 变更包含原始内容标注",
        "- [ ] 所有 REMOVED 变更包含删除原因",
        "- [ ] 数据约束变更与业务规则一致",
        "- [ ] 术语变更与业务规则一致",
        "- [ ] 已审查与现有 SPEC.md 的兼容性",
        "- [ ] 如有破坏性变更，已声明并提供迁移方案",
        "",
    ]

    # 如果有相似需求，添加参考
    if similar_requirements:
        content_lines.extend([
            "---",
            "",
            "## 7. 参考相似需求",
            "",
        ])
        for similar in similar_requirements:
            sim_id = similar.get("id", "unknown")
            sim_path = similar.get("path", "")
            content_lines.append(f"- [{sim_id}]({sim_path})")

    return "\n".join(content_lines)


def parse_requirement_for_delta_spec(description: str) -> Dict[str, Any]:
    """
    从需求描述中提取关键信息，用于生成 delta_spec

    Args:
        description: 需求描述文本

    Returns:
        提取的信息字典
    """
    result = {
        "requirements": [],
        "data_constraints": [],
        "terms": []
    }

    # 简单的关键词提取
    keywords = ["支持", "实现", "提供", "增加", "修改", "删除"]
    for keyword in keywords:
        if keyword in description:
            result["requirements"].append({
                "keyword": keyword,
                "context": description
            })

    return result


def main():
    """测试入口"""
    import argparse

    parser = argparse.ArgumentParser(description="delta_spec生成器")
    parser.add_argument("--id", "-i", required=True, help="需求ID")
    parser.add_argument("--output", "-o", default=".", help="输出目录")
    parser.add_argument("--desc", "-d", default="测试描述", help="需求描述")

    args = parser.parse_args()

    proposal_data = {
        "e2e_id": args.id,
        "description": args.desc,
        "doc_info": []
    }

    file_path = generate_delta_spec(args.id, proposal_data, [], args.output)
    print(f"已生成: {file_path}")


if __name__ == "__main__":
    main()
